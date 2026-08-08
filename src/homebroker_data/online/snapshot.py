"""HTTP polling market data client for the HBD client."""

from __future__ import annotations

from typing import Any

import httpx
import pandas as pd
from pydantic import BaseModel, Field

from ..auth.session import Auth
from ..common.brokers import BrokerConfig
from ..common.exceptions import DataException, ServerException, SessionException
from ..common.helpers import normalize_columns, setup_settlement

_BOARD_MAP: dict[str, str] = {
    "bluechips": "accionesLideres",
    "general_board": "panelGeneral",
    "cedears": "cedears",
    "government_bonds": "rentaFija",
    "short_term_government_bonds": "letes",
    "corporate_bonds": "obligaciones",
    "options": "opciones",
    "repos": "cauciones",
    "indices": "indices",
}

_SUPPORTED_BOARDS = frozenset(_BOARD_MAP.keys())


class _PriceEnvelope(BaseModel):
    """Pydantic model for the BYMA /Prices/GetByPanel response envelope."""

    Success: bool
    Result: dict[str, Any] = Field(default_factory=dict)
    Error: dict[str, str] = Field(default_factory=dict)


class OnlineSnapshot:
    """HTTP polling market data for BYMA.

    All methods share the same ``httpx.Client`` injected from the
    :class:`~homebroker_data.client.HomeBroker` facade so that session
    cookies are persisted automatically.
    """

    def __init__(
        self,
        auth: Auth,
        broker_config: BrokerConfig,
        client: httpx.Client,
    ) -> None:
        self._auth = auth
        self._broker_config = broker_config
        self._client = client

    @property
    def auth(self) -> Auth:
        return self._auth

    @property
    def client(self) -> httpx.Client:
        return self._client

    @property
    def broker_config(self) -> BrokerConfig:
        return self._broker_config

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_auth(self) -> None:
        if not self._auth.is_logged_in:
            raise SessionException("Not logged in — call auth.login() first")

    def _post_panel(
        self, panel: str, settlement: str | None = None
    ) -> pd.DataFrame:
        """POST to /Prices/GetByPanel and return a normalized DataFrame."""
        self._check_auth()

        term = setup_settlement(settlement) if settlement else ""
        resp = self._client.post(
            "/Prices/GetByPanel",
            data={"panel": panel, "term": str(term)},
        )
        return self._envelope_to_df(resp)

    def _get_favoritos(self) -> pd.DataFrame:
        self._check_auth()
        resp = self._client.get("/Prices/GetFavoritos")
        return self._envelope_to_df(resp)

    def _envelope_to_df(self, resp: httpx.Response) -> pd.DataFrame:
        if resp.status_code >= 400:
            raise ServerException(
                f"BYMA API error: HTTP {resp.status_code} — {resp.text[:200]}"
            )
        envelope = _PriceEnvelope.model_validate_json(resp.text)
        if not envelope.Success:
            desc = envelope.Error.get("Descripcion", "Unknown API error")
            raise DataException(f"BYMA API error: {desc}")

        stocks = envelope.Result.get("Stocks") or []
        if not stocks:
            return pd.DataFrame()

        df = pd.DataFrame(stocks)
        df = normalize_columns(df)
        return df

    # ------------------------------------------------------------------
    # Public API — market data
    # ------------------------------------------------------------------

    def get_securities(self, board: str, settlement: str) -> pd.DataFrame:
        if board not in _SUPPORTED_BOARDS:
            raise DataException(
                f"Unknown board '{board}'. Supported: {sorted(_SUPPORTED_BOARDS)}"
            )
        panel = _BOARD_MAP[board]
        return self._post_panel(panel, settlement)

    def get_options(self) -> pd.DataFrame:
        return self._post_panel("opciones")

    def get_repos(self) -> pd.DataFrame:
        return self._post_panel("cauciones")

    def get_indices(self) -> pd.DataFrame:
        return self._post_panel("indices")

    def get_personal_portfolio(self) -> pd.DataFrame:
        return self._get_favoritos()

    def get_order_book(self, symbol: str, settlement: str) -> pd.DataFrame:
        self._check_auth()
        term = setup_settlement(settlement)
        resp = self._client.post(
            "/Prices/GetByStock",
            data={"symbol": symbol, "term": str(term)},
        )
        return self._envelope_to_df(resp)

    def get_market_snapshot(self) -> dict[str, pd.DataFrame]:
        """Fetch all boards in one call and return a dict keyed by board name."""
        snapshots: dict[str, pd.DataFrame] = {}
        settlement = "spot"
        for board_name in _SUPPORTED_BOARDS:
            panel = _BOARD_MAP[board_name]
            snapshots[board_name] = self._post_panel(panel, settlement)
        return snapshots
