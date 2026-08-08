"""DataFrame / settlement helpers for the HBD client.

Provides:
    * ``SETTLEMENT_MAP`` / ``SETTLEMENT_REVERSE_MAP`` — settlement constants
    * ``setup_settlement`` — settlement string → API term value
    * ``convert_to_numeric_columns`` — locale-aware numeric coercion
    * ``normalize_columns`` — raw API keys → HBD English column names

Spec ref: common-infrastructure spec §"Error Handling", §"Broker Configuration",
§"Column Normalization Mapping", §"Requirements" (#4, #5, #6), §"Data Formats".
"""

from __future__ import annotations

from typing import ClassVar

import pandas as pd

from .exceptions import DataException

# ---------------------------------------------------------------------------
# Settlement constants
# ---------------------------------------------------------------------------

#: Forward settlement map — human-readable string → BYMA API ``term`` value.
SETTLEMENT_MAP: dict[str, str] = {
    "spot": "1",
    "24hs": "2",
}

#: Reverse settlement map — API ``term`` value → human-readable string.
SETTLEMENT_REVERSE_MAP: dict[str, str] = {
    value: key for key, value in SETTLEMENT_MAP.items()
}


def setup_settlement(settlement: str) -> str:
    """Map a settlement name to the integer-string term expected by the API.

    Args:
        settlement: ``'spot'`` or ``'24hs'``.

    Returns:
        ``'1'`` for *spot*, ``'2'`` for *24hs*.

    Raises:
        DataException: If *settlement* is ``'48hs'`` (deprecated) or any
            unrecognized value.
    """
    if settlement == "48hs":
        raise DataException("Settlement '48hs' is deprecated and not supported.")
    if settlement in SETTLEMENT_MAP:
        return SETTLEMENT_MAP[settlement]
    raise DataException(
        f"Invalid settlement '{settlement}'. Use 'spot' or '24hs'."
    )


# ---------------------------------------------------------------------------
# Numeric conversion
# ---------------------------------------------------------------------------


def convert_to_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Coerce *columns* in *df* to numeric, fixing Argentine locale quirks.

    Handles the three transformations required by spec req #4:
        * Strip thousands-separator dots: ``"1.234"`` → ``"1234"``
        * Comma → dot for decimal separator: ``"1234,56"`` → ``"1234.56"``
        * Dash sentinel → NaN: ``"-"`` → ``NaN``

    Args:
        df: Input DataFrame (modified in place, returned for chaining).
        columns: Column names to coerce to numeric.
    """
    for col in columns:
        if col not in df.columns:
            continue
        # Step 1: strip thousands dots and swap comma→dot on string cells
        df[col] = df[col].apply(
            lambda x: x.replace(".", "").replace(",", ".") if isinstance(x, str) else x
        )
        # Step 2: convert to numeric; '-' and any non-numeric → NaN
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Column normalization
# ---------------------------------------------------------------------------


class ColumnNormalizer:
    """Class-level constants mapping raw API column names to HBD English names.

    Mirrors pyhomebroker's ``OnlineCore`` class-level column constants.
    Supports two raw key formats:
        * BYMA API PascalCase (``Symbol``, ``LastPrice``, …)
        * Spanish abbreviations (``PREC``, ``VOLU``, …)
    """

    COLUMN_MAP: ClassVar[dict[str, str]] = {
        # --- BYMA API PascalCase keys ---
        "Symbol": "symbol",
        "Simbolo": "symbol",
        "LastPrice": "price",
        "Precio": "price",
        "StartPrice": "open",
        "Apertura": "open",
        "APERT": "open",
        "MaxPrice": "high",
        "Maximo": "high",
        "MAX": "high",
        "MinPrice": "low",
        "Minimo": "low",
        "MIN": "low",
        "ClosePrice": "close",
        "Cierre": "close",
        "CIERRE": "close",
        "TotalQuantityTraded": "volume",
        "Volumen": "volume",
        "VOLU": "volume",
        "Term": "settlement",
        "ESPE": "settlement",
        "TradeDate": "date",
        "FECHA": "date",
        "Panel": "group",
        # --- Currency ---
        "Moneda": "currency",
        "MON": "currency",
        # --- Spanish abbreviation keys ---
        "PREC": "price",
        "TICK": "tick",
        "IMPU": "impulse",
        "CANT": "quantity",
        # --- Order book (GetByStock) keys ---
        "Pos": "position",
        "BuyPrice": "bid",
        "BuyQuantity": "bid_size",
        "SellPrice": "ask",
        "SellQuantity": "ask_size",
        "NumberOfOrders": "offers_count",
    }


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename raw API columns to HBD English names and ensure ``currency`` exists.

    Columns present in :attr:`ColumnNormalizer.COLUMN_MAP` are renamed in
    place; all other columns pass through unchanged.  If no ``currency``
    column exists after renaming, one is added with a default of ``"ARS"``
    (spec: "currency column added by HBD (defaults to ARS)").

    Args:
        df: DataFrame with raw API column names.

    Returns:
        A new DataFrame with renamed columns.
    """
    df = df.rename(columns=ColumnNormalizer.COLUMN_MAP)
    if "currency" not in df.columns:
        df["currency"] = "ARS"
    return df
