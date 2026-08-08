"""Unit tests for the Auth session — Phase 2 T2.1, T2.2, T2.3, T2.4.

Covers:
  T2.1 — Auth.__init__ stores config + client, is_logged_in/ip_address defaults
  T2.2 — login() with MockTransport: success, failure, ConnectError, HTTP 500 fallback
  T2.3 — logout() clears state
  T2.4 — ip_address property (covered via login + logout)
"""

from __future__ import annotations

import httpx
import pytest

from homebroker_data.auth import Auth
from homebroker_data.common import (
    BrokerConfig,
    ServerException,
    SessionException,
)


def _make_client(
    handler: httpx.MockTransport | None = None,
) -> httpx.Client:
    """Create an httpx.Client with MockTransport for testing."""
    if handler is None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html></html>")
    return httpx.Client(
        base_url="https://operarhb.bavsa.com",
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        headers=Auth.DEFAULT_HEADERS,
    )


# ---------------------------------------------------------------------------
# T2.1 — Auth initialization + properties
# ---------------------------------------------------------------------------

BROKER_CONFIG: BrokerConfig = {
    "broker_id": 12,
    "name": "Buenos Aires Valores S.A.",
    "page": "https://operarhb.bavsa.com",
}


class TestAuthInit:
    """Strict TDD T2.1: Auth.__init__ stores broker_config + client; defaults."""

    def test_stores_broker_config(self):
        """Auth must store the broker_config passed at construction."""
        client = _make_client()
        auth = Auth(BROKER_CONFIG, client)
        assert auth._broker_config == BROKER_CONFIG

    def test_stores_client(self):
        """Auth must store the httpx.Client passed at construction."""
        client = _make_client()
        auth = Auth(BROKER_CONFIG, client)
        assert auth._client is client

    def test_is_logged_in_false_initially(self):
        """A freshly constructed Auth must report is_logged_in=False."""
        auth = Auth(BROKER_CONFIG, _make_client())
        assert auth.is_logged_in is False

    def test_ip_address_none_initially(self):
        """A freshly constructed Auth must have ip_address=None."""
        auth = Auth(BROKER_CONFIG, _make_client())
        assert auth.ip_address is None

    def test_is_logged_in_is_read_only(self):
        """is_logged_in is a read-only property — assignment must fail."""
        auth = Auth(BROKER_CONFIG, _make_client())
        with pytest.raises(AttributeError):
            auth.is_logged_in = True  # type: ignore[misc]

    def test_ip_address_is_read_only(self):
        """ip_address is a read-only property — assignment must fail."""
        auth = Auth(BROKER_CONFIG, _make_client())
        with pytest.raises(AttributeError):
            auth.ip_address = "1.2.3.4"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# T2.2 — Login
# ---------------------------------------------------------------------------

class TestLoginSuccess:
    """login() with a successful MockTransport response."""

    def test_login_success_returns_true(self):
        """Successful login returns True and sets is_logged_in."""
        call_log: list[tuple[str, str]] = []

        def handler(req: httpx.Request) -> httpx.Response:
            call_log.append((req.method, req.url.path))
            if req.url.host == "api.ipify.org":
                return httpx.Response(200, json={"ip": "203.0.113.5"})
            if req.url.path == "/" or req.url.path == "":
                return httpx.Response(200, text="<html><body>welcome</body></html>")
            if req.url.path == "/Login/Ingresar":
                return httpx.Response(
                    200,
                    text='<html><div id="usuarioLogueado">user123</div></html>',
                )
            return httpx.Response(404, text="not found")

        auth = Auth(BROKER_CONFIG, _make_client(handler))
        result = auth.login(dni="12345678", user="testuser", password="testpass")

        assert result is True
        assert auth.is_logged_in is True

    def test_login_captures_ip(self):
        """login() must capture the public IP from ipify."""
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.ipify.org":
                return httpx.Response(200, json={"ip": "198.51.100.42"})
            if req.url.path == "/" or req.url.path == "":
                return httpx.Response(200, text="<html></html>")
            if req.url.path == "/Login/Ingresar":
                return httpx.Response(
                    200,
                    text='<html><div id="usuarioLogueado">user</div></html>',
                )
            return httpx.Response(404)

        auth = Auth(BROKER_CONFIG, _make_client(handler))
        auth.login(dni="12345678", user="testuser", password="testpass")
        assert auth.ip_address == "198.51.100.42"

    def test_login_post_includes_form_fields(self):
        """The login POST must include Dni, Usuario, Password, IpAddress form fields."""
        captured: list[dict[str, str]] = []

        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.path == "/Login/Ingresar" and req.method == "POST":
                content_type = req.headers.get("content-type", "")
                if "form-urlencoded" in content_type:
                    body = req.content.decode()
                    captured.append(dict(pair.split("=") for pair in body.split("&")))
            if req.url.host == "api.ipify.org":
                return httpx.Response(200, json={"ip": "1.2.3.4"})
            if req.url.path == "/" or req.url.path == "":
                return httpx.Response(200, text="<html></html>")
            if req.url.path == "/Login/Ingresar" and req.method == "POST":
                return httpx.Response(
                    200,
                    text='<html><div id="usuarioLogueado">ok</div></html>',
                )
            return httpx.Response(404)

        auth = Auth(BROKER_CONFIG, _make_client(handler))
        auth.login(dni="12345678", user="testuser", password="testpass")

        assert len(captured) == 1
        fields = captured[0]
        assert "IpAddress" in fields
        assert "Dni" in fields
        assert "Usuario" in fields
        assert "Password" in fields
        assert fields["Dni"] == "12345678"
        assert fields["Usuario"] == "testuser"


class TestLoginFailure:
    """login() failure and edge cases."""

    def test_login_without_usuario_logueado_raises_session(self):
        """HTML without #usuarioLogueado must raise SessionException."""
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.ipify.org":
                return httpx.Response(200, json={"ip": "1.2.3.4"})
            if req.url.path == "/" or req.url.path == "":
                return httpx.Response(200, text="<html></html>")
            if req.url.path == "/Login/Ingresar":
                return httpx.Response(200, text="<html><body>invalid credentials</body></html>")
            return httpx.Response(404)

        auth = Auth(BROKER_CONFIG, _make_client(handler))
        with pytest.raises(SessionException, match="Login failed"):
            auth.login(dni="12345678", user="testuser", password="testpass")
        assert auth.is_logged_in is False

    def test_login_connect_error_raises_server(self):
        """httpx.ConnectError must surface as ServerException."""
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.ipify.org":
                return httpx.Response(200, json={"ip": "1.2.3.4"})
            if req.url.path == "/" or req.url.path == "":
                return httpx.Response(200, text="<html></html>")
            if req.url.path == "/Login/Ingresar":
                raise httpx.ConnectError("connection refused")
            return httpx.Response(404)

        auth = Auth(BROKER_CONFIG, _make_client(handler))
        with pytest.raises(ServerException):
            auth.login(dni="12345678", user="testuser", password="testpass")

    def test_login_http_500_fallback_to_modal(self):
        """HTTP 500 on /Login/Ingresar triggers fallback to /Login/IngresarModal."""
        posts: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.ipify.org":
                return httpx.Response(200, json={"ip": "1.2.3.4"})
            if req.url.path == "/" or req.url.path == "":
                return httpx.Response(200, text="<html></html>")
            if req.url.path == "/Login/Ingresar" and req.method == "POST":
                posts.append("Ingresar")
                return httpx.Response(500, text="internal server error")
            if req.url.path == "/Login/IngresarModal" and req.method == "POST":
                posts.append("IngresarModal")
                return httpx.Response(
                    200,
                    text='<html><div id="usuarioLogueado">fallback_ok</div></html>',
                )
            return httpx.Response(404)

        auth = Auth(BROKER_CONFIG, _make_client(handler))
        result = auth.login(dni="12345678", user="testuser", password="testpass")

        assert result is True
        assert "Ingresar" in posts
        assert "IngresarModal" in posts

    def test_login_http_500_both_fail_raises_session(self):
        """If both primary and fallback return no usuarioLogueado, raise SessionException."""
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.ipify.org":
                return httpx.Response(200, json={"ip": "1.2.3.4"})
            if req.url.path == "/" or req.url.path == "":
                return httpx.Response(200, text="<html></html>")
            if req.url.path == "/Login/Ingresar" and req.method == "POST":
                return httpx.Response(500, text="server error")
            if req.url.path == "/Login/IngresarModal" and req.method == "POST":
                return httpx.Response(
                    200, text="<html><body>no user section</body></html>"
                )
            return httpx.Response(404)

        auth = Auth(BROKER_CONFIG, _make_client(handler))
        with pytest.raises(SessionException):
            auth.login(dni="12345678", user="testuser", password="testpass")


# ---------------------------------------------------------------------------
# T2.3 — Logout
# ---------------------------------------------------------------------------

class TestLogout:
    """Strict TDD T2.3: logout() clears session state."""

    def test_logout_resets_is_logged_in(self):
        """After logout, is_logged_in must be False."""
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.ipify.org":
                return httpx.Response(200, json={"ip": "1.2.3.4"})
            if req.url.path == "/" or req.url.path == "":
                return httpx.Response(200, text="<html></html>")
            if req.url.path == "/Login/Ingresar":
                return httpx.Response(200, text='<html><div id="usuarioLogueado">u</div></html>')
            return httpx.Response(404)

        auth = Auth(BROKER_CONFIG, _make_client(handler))
        auth.login(dni="12345678", user="testuser", password="testpass")
        assert auth.is_logged_in is True

        auth.logout()
        assert auth.is_logged_in is False

    def test_logout_resets_ip_address(self):
        """After logout, ip_address must be None."""
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.ipify.org":
                return httpx.Response(200, json={"ip": "1.2.3.4"})
            if req.url.path == "/" or req.url.path == "":
                return httpx.Response(200, text="<html></html>")
            if req.url.path == "/Login/Ingresar":
                return httpx.Response(200, text='<html><div id="usuarioLogueado">u</div></html>')
            return httpx.Response(404)

        auth = Auth(BROKER_CONFIG, _make_client(handler))
        auth.login(dni="12345678", user="testuser", password="testpass")
        assert auth.ip_address == "1.2.3.4"

        auth.logout()
        assert auth.ip_address is None
