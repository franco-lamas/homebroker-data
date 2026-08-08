"""Strict TDD tests for OnlineSnapshot (market data polling)."""

from __future__ import annotations

import httpx
import pandas as pd
import pytest

from homebroker_data.auth import Auth
from homebroker_data.common import BrokerConfig
from homebroker_data.common.exceptions import (
    DataException,
    ServerException,
    SessionException,
)
from homebroker_data.online import OnlineSnapshot

BROKER_CONFIG: BrokerConfig = {
    "broker_id": 12,
    "name": "Buenos Aires Valores S.A.",
    "page": "https://operarhb.bavsa.com",
}


def _make_client(handler) -> httpx.Client:
    """Create an httpx.Client with MockTransport."""
    return httpx.Client(
        base_url=BROKER_CONFIG["page"],
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        headers=Auth.DEFAULT_HEADERS,
    )


def _make_logged_in_snapshot(handler) -> OnlineSnapshot:
    client = _make_client(handler)
    auth = Auth(BROKER_CONFIG, client)
    auth._is_logged_in = True  # bypass login for testing
    auth._ip_address = "203.0.113.1"
    return OnlineSnapshot(auth, BROKER_CONFIG, client)


# ---------------------------------------------------------------------------
# T3.1 — OnlineSnapshot initialization
# ---------------------------------------------------------------------------


class TestOnlineSnapshotInit:
    def test_injection_works(self):
        client = _make_client(lambda req: httpx.Response(200))
        auth = Auth(BROKER_CONFIG, client)
        snapshot = OnlineSnapshot(auth, BROKER_CONFIG, client)
        assert snapshot.auth is auth
        assert snapshot.client is client
        assert snapshot.broker_config == BROKER_CONFIG


# ---------------------------------------------------------------------------
# T3.2 — get_securities
# ---------------------------------------------------------------------------


class TestGetSecurities:
    def test_bluechips_returns_dataframe(self):
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(202, json={
                "Success": True,
                "Result": {"Stocks": [
                    {"Simbolo": "GGAL", "Precio": 12345.6, "Volumen": 100}
                ]},
            })
        snapshot = _make_logged_in_snapshot(handler)
        df = snapshot.get_securities("bluechips", "spot")
        assert not df.empty
        assert "symbol" in df.columns
        assert "price" in df.columns

    def test_settlement_mapping_spot(self):
        captured: list[dict[str, str]] = []
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.path == "/Prices/GetByPanel" and req.method == "POST":
                body = req.content.decode()
                captured.append(dict(pair.split("=") for pair in body.split("&")))
            return httpx.Response(202, json={"Success": True, "Result": {"Stocks": []}})
        snapshot = _make_logged_in_snapshot(handler)
        snapshot.get_securities("bluechips", "spot")
        assert captured[0]["term"] == "1"

    def test_settlement_mapping_24hs(self):
        captured: list[dict[str, str]] = []
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.path == "/Prices/GetByPanel" and req.method == "POST":
                body = req.content.decode()
                captured.append(dict(pair.split("=") for pair in body.split("&")))
            return httpx.Response(202, json={"Success": True, "Result": {"Stocks": []}})
        snapshot = _make_logged_in_snapshot(handler)
        snapshot.get_securities("general_board", "24hs")
        assert captured[0]["term"] == "2"

    def test_invalid_board_raises_data_exception(self):
        snapshot = _make_logged_in_snapshot(
            lambda req: httpx.Response(202, json={"Success": True, "Result": {"Stocks": []}})
        )
        with pytest.raises(DataException, match="Unknown board"):
            snapshot.get_securities("invalid_board", "spot")

    def test_deprecated_48hs_raises_data_exception(self):
        snapshot = _make_logged_in_snapshot(
            lambda req: httpx.Response(202, json={"Success": True, "Result": {"Stocks": []}})
        )
        with pytest.raises(DataException):
            snapshot.get_securities("bluechips", "48hs")

    def test_not_logged_in_raises_session_exception(self):
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(202, json={"Success": True, "Result": {"Stocks": []}})
        client = _make_client(handler)
        auth = Auth(BROKER_CONFIG, client)
        snapshot = OnlineSnapshot(auth, BROKER_CONFIG, client)
        with pytest.raises(SessionException, match="Not logged in"):
            snapshot.get_securities("bluechips", "spot")

    def test_success_false_raises_data_exception(self):
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(202, json={
                "Success": False,
                "Error": {"Descripcion": "API error"},
            })
        snapshot = _make_logged_in_snapshot(handler)
        with pytest.raises(DataException, match="API error"):
            snapshot.get_securities("bluechips", "spot")

    def test_http_error_raises_server_exception(self):
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal server error")
        snapshot = _make_logged_in_snapshot(handler)
        with pytest.raises(ServerException):
            snapshot.get_securities("bluechips", "spot")


# ---------------------------------------------------------------------------
# T3.3 — get_options, get_repos, get_indices
# ---------------------------------------------------------------------------


class TestMarketBoards:
    @pytest.mark.parametrize("method,panel", [
        ("get_options", "opciones"),
        ("get_repos", "cauciones"),
        ("get_indices", "indices"),
    ])
    def test_board_resolves_panel(self, method, panel):
        captured: list[str] = []
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.path == "/Prices/GetByPanel" and req.method == "POST":
                body = req.content.decode()
                captured.append(dict(pair.split("=") for pair in body.split("&")))
            return httpx.Response(202, json={"Success": True, "Result": {"Stocks": []}})
        snapshot = _make_logged_in_snapshot(handler)
        getattr(snapshot, method)()
        assert captured[0]["panel"] == panel

    def test_empty_response_returns_empty_dataframe(self):
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(202, json={"Success": True, "Result": {"Stocks": []}})
        snapshot = _make_logged_in_snapshot(handler)
        df = snapshot.get_options()
        assert df.empty


# ---------------------------------------------------------------------------
# T3.4 — get_personal_portfolio
# ---------------------------------------------------------------------------


class TestPersonalPortfolio:
    def test_get_personal_portfolio(self):
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.path == "/Prices/GetFavoritos":
                return httpx.Response(202, json={
                    "Success": True,
                    "Result": {"Stocks": [{"Simbolo": "GGAL", "Precio": 12345.6}]},
                })
            return httpx.Response(202, json={"Success": True, "Result": {"Stocks": []}})
        snapshot = _make_logged_in_snapshot(handler)
        df = snapshot.get_personal_portfolio()
        assert not df.empty
        assert "symbol" in df.columns


# ---------------------------------------------------------------------------
# T3.5 — get_order_book
# ---------------------------------------------------------------------------


class TestOrderBook:
    def test_get_order_book_symbol_and_settlement(self):
        captured: list[dict[str, str]] = []
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.path == "/Prices/GetByStock" and req.method == "POST":
                body = req.content.decode()
                captured.append(dict(pair.split("=") for pair in body.split("&")))
            return httpx.Response(202, json={
                "Success": True,
                "Result": {"Stocks": [{"Simbolo": "GGAL", "Precio": 12345.6}]},
            })
        snapshot = _make_logged_in_snapshot(handler)
        snapshot.get_order_book("PAMP", "spot")
        assert captured[0]["symbol"] == "PAMP"
        assert captured[0]["term"] == "1"


# ---------------------------------------------------------------------------
# T3.6 — get_market_snapshot
# ---------------------------------------------------------------------------


class TestMarketSnapshot:
    def test_returns_all_nine_boards(self):
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(202, json={"Success": True, "Result": {"Stocks": []}})
        snapshot = _make_logged_in_snapshot(handler)
        result = snapshot.get_market_snapshot()
        assert set(result.keys()) == {
            "bluechips", "general_board", "cedears", "government_bonds",
            "short_term_government_bonds", "corporate_bonds",
            "options", "repos", "indices",
        }
        for df in result.values():
            assert isinstance(df, pd.DataFrame)
