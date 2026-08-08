"""Authentication session for the HBD client.

Wraps a shared ``httpx.Client`` to perform BYMA login/logout, IP capture,
and cookie persistence.
"""

from __future__ import annotations

from typing import ClassVar

import httpx

from ..common.brokers import BrokerConfig
from ..common.exceptions import (
    ServerException,
    SessionException,
)


class Auth:
    """Manages login, logout, and session state for a BYMA broker.

    A single ``httpx.Client`` is injected so that login cookies are
    automatically persisted across all subsequent data requests.
    """

    #: Default headers applied to the shared client.
    DEFAULT_HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }

    def __init__(self, broker_config: BrokerConfig, client: httpx.Client) -> None:
        self._broker_config = broker_config
        self._client = client
        self._is_logged_in = False
        self._ip_address: str | None = None

    @property
    def is_logged_in(self) -> bool:
        return self._is_logged_in

    @property
    def ip_address(self) -> str | None:
        return self._ip_address

    def login(self, dni: str, user: str, password: str) -> bool:
        """Log in to the BYMA broker platform.

        Performs the following steps in order:
        1. Fetch client IP from ipify.
        2. POST form data to ``/Login/Ingresar`` with broker credentials + IP.
        3. Parse the HTML response for ``usuarioLogueado``.
        4. On HTTP 500, retry with ``/Login/IngresarModal``.

        :param dni: User DNI (8 digits)
        :param user: Username / trading account
        :param password: Password
        :returns: ``True`` on successful login
        :raises SessionException: if login fails (no ``usuarioLogueado`` found)
        :raises ServerException: on HTTP/transport errors
        """
        # Step 1: Fetch IP address from ipify
        try:
            ip_resp = self._client.get("https://api.ipify.org?format=json")
            ip_resp.raise_for_status()
            self._ip_address = ip_resp.json()["ip"]
        except (httpx.HTTPError, KeyError) as exc:
            raise ServerException(f"Failed to capture IP address: {exc}") from exc

        # Step 2: Fetch main page first to retrieve any required cookies (pyhomebroker pattern)
        try:
            self._client.get(self._broker_config["page"], headers=Auth.DEFAULT_HEADERS)
        except httpx.HTTPError as exc:
            raise ServerException(f"Failed to initialize session: {exc}") from exc

        # Step 3: Attempt primary login with BYMA form field names
        form_data = {
            "IpAddress": self._ip_address,
            "Dni": dni,
            "Usuario": user,
            "Password": password,
        }
        try:
            resp = self._client.post(
                f"{self._broker_config['page']}/Login/Ingresar",
                data=form_data,
                headers=Auth.DEFAULT_HEADERS,
            )
        except httpx.HTTPError as exc:
            raise ServerException(f"Login request failed: {exc}") from exc

        # Step 4: Check for HTTP 500 → fallback to modal login
        if resp.status_code == 500:
            resp = self._fallback_login(form_data)

        # Step 5: Parse HTML response
        if self._is_logged_in_response(resp):
            self._is_logged_in = True
            return True

        raise SessionException("Login failed — usuarioLogueado not found in response")

    def _fallback_login(self, form_data: dict[str, str]) -> httpx.Response:
        """Retry login via the modal endpoint."""
        try:
            resp = self._client.post(
                f"{self._broker_config['page']}/Login/IngresarModal",
                data=form_data,
                headers=Auth.DEFAULT_HEADERS,
            )
        except httpx.HTTPError as exc:
            raise ServerException(f"Fallback login failed: {exc}") from exc

        return resp

    def _is_logged_in_response(self, resp: httpx.Response) -> bool:
        """Check if the login response contains usuarioLogueado."""
        # Handle empty 500 responses (both login paths failed)
        if resp.status_code >= 400:
            raise ServerException(
                f"Login endpoint returned HTTP {resp.status_code}: {resp.text[:200]}"
            )

        # Parse HTML response for usuarioLogueado element
        # Using stdlib html.parser — no extra dependency
        html_content = resp.text
        if not html_content or "usuarioLogueado" not in html_content:
            return False

        # Verify the element is present as a DOM node (not just in a comment)
        return self._has_usuario_logueado_element(html_content)

    def _has_usuario_logueado_element(self, html: str) -> bool:
        """Parse HTML to verify usuarioLogueado is an actual element."""
        from html.parser import HTMLParser

        class LoginChecker(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.found = False

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                attrs_dict = dict(attrs)
                if attrs_dict.get("id") == "usuarioLogueado":
                    self.found = True

        checker = LoginChecker()
        checker.feed(html)
        return checker.found

    def logout(self) -> None:
        """Log out by clearing cookies and resetting session state."""
        self._client.cookies.clear()
        self._is_logged_in = False
        self._ip_address = None
