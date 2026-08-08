"""Common infrastructure for the HBD (HomeBroker Data) client.

Public API:
    HBDException            — base exception (catch all HBD errors)
    SessionException        — not logged in / session expired
    BrokerNotSupportedException — unknown broker ID
    ServerException         — HTTP transport / 5xx errors
    DataException           — invalid or unexpected API response data

    BrokerConfig            — TypedDict for a broker configuration
    BROKERS                 — list of all 17 supported brokers
    get_broker              — lookup a broker by ID

    SETTLEMENT_MAP          — settlement string → API term value
    SETTLEMENT_REVERSE_MAP  — API term value → settlement string
    setup_settlement        — resolve settlement name to term value
    convert_to_numeric_columns — locale-aware numeric coercion
    normalize_columns       — raw API keys → HBD English column names
"""

from __future__ import annotations

from .brokers import BROKERS, BrokerConfig, get_broker
from .exceptions import (
    BrokerNotSupportedException,
    DataException,
    HBDException,
    ServerException,
    SessionException,
)
from .helpers import (
    SETTLEMENT_MAP,
    SETTLEMENT_REVERSE_MAP,
    ColumnNormalizer,
    convert_to_numeric_columns,
    normalize_columns,
    setup_settlement,
)

__all__ = [
    "BROKERS",
    # helpers
    "SETTLEMENT_MAP",
    "SETTLEMENT_REVERSE_MAP",
    # brokers
    "BrokerConfig",
    "BrokerNotSupportedException",
    "ColumnNormalizer",
    "DataException",
    # exceptions
    "HBDException",
    "ServerException",
    "SessionException",
    "convert_to_numeric_columns",
    "get_broker",
    "normalize_columns",
    "setup_settlement",
]
