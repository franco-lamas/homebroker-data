"""Unit tests for homebroker_data.common — Phase 1: Common Infrastructure.

Covers:
  T1.1 — exception hierarchy
  T1.2 — broker config + get_broker lookup
  T1.3 — settlement mapping, numeric conversion, column normalization
"""

from __future__ import annotations

import pandas as pd
import pytest

from homebroker_data.common.brokers import BROKERS, BrokerConfig, get_broker
from homebroker_data.common.exceptions import (
    BrokerNotSupportedException,
    DataException,
    HBDException,
    ServerException,
    SessionException,
)
from homebroker_data.common.helpers import (
    SETTLEMENT_MAP,
    SETTLEMENT_REVERSE_MAP,
    convert_to_numeric_columns,
    normalize_columns,
    setup_settlement,
)

# ---------------------------------------------------------------------------
# T1.1 — Exception Hierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Strict TDD T1.1: HBDException base + 4 typed subtypes.

    Spec ref: common-infrastructure spec §"Error Handling", req #3.
    """

    def test_hbd_exception_is_subclass_of_exception(self):
        """HBDException must inherit from the built-in Exception."""
        assert issubclass(HBDException, Exception)

    def test_session_exception_is_subclass_of_hbd_exception(self):
        assert issubclass(SessionException, HBDException)

    def test_broker_exception_is_subclass_of_hbd_exception(self):
        assert issubclass(BrokerNotSupportedException, HBDException)

    def test_server_exception_is_subclass_of_hbd_exception(self):
        assert issubclass(ServerException, HBDException)

    def test_data_exception_is_subclass_of_hbd_exception(self):
        assert issubclass(DataException, HBDException)

    @pytest.mark.parametrize(
        "exc_cls",
        [SessionException, BrokerNotSupportedException, ServerException, DataException],
    )
    def test_subtype_is_catchable_as_base(self, exc_cls):
        """Every subtype must be catchable via the HBDException base."""
        try:
            raise exc_cls("boom")
        except HBDException:
            pass  # expected
        else:
            pytest.fail(f"{exc_cls.__name__} was not caught by HBDException")

    @pytest.mark.parametrize(
        "exc_cls",
        [SessionException, BrokerNotSupportedException, ServerException, DataException],
    )
    def test_exception_carries_message(self, exc_cls):
        """Each exception type must preserve its message string."""
        msg = f"{exc_cls.__name__} specific detail"
        exc = exc_cls(msg)
        assert str(exc) == msg


# ---------------------------------------------------------------------------
# T1.2 — Broker Configuration & Lookup
# ---------------------------------------------------------------------------

# All 17 brokers from the common-infrastructure spec broker table.
ALL_BROKERS = [
    (12, "Buenos Aires Valores S.A.", "https://operarhb.bavsa.com"),
    (20, "Proficio Investment S.A.", "https://newsystem.proficioinvestment.com.ar"),
    (81, "Tomar Inversiones S.A", "https://clientes2.tminversiones.com.ar"),
    (88, "Bell Investments S.A.", "https://operar.bellbursatil.com"),
    (91, "RIG Valores S.A.", "https://rigvaloresweb.com/"),
    (94, "Soluciones Financieras S.A.", "https://sistemag.solfin.com.ar"),
    (122, "Industrial Valores S.A.", "https://inversiones.bind.com.ar/Clientes"),
    (127, "Maestro y Huerres S.A", "https://operar.maestroyhuerres.com"),
    (153, "Bolsa de Comercio del Chaco", "https://clientes.bcch.org.ar"),
    (163, "Prosecurities S.A.", "http://operar.psec.com.ar"),
    (186, "Servente y Cia. S.A.", "http://clientes.serventeycia.com"),
    (201, "Alfy Inversiones S.A.", "https://acceso.alfyinversiones.com.ar"),
    (203, "Invertir en Bolsa S.A.", "https://clientesv2.invertirenbolsa.com.ar"),
    (209, "Futuro Bursátil S.A.", "https://homebroker.futurobursatil.com.ar"),
    (233, "Sailing S.A.", "https://login.sailinginversiones.com"),
    (265, "Negocios Financieros y Bursátiles", "https://cocoscap.com"),
    (284, "Veta Capital S.A.", "http://cuentas.vetacapital.com.ar"),
]


class TestBrokers:
    """Strict TDD T1.2: 17-broker config + get_broker lookup.

    Spec ref: common-infrastructure spec §"Broker Configuration", req #1, #2.
    """

    def test_broker_count_is_17(self):
        """BROKERS list must contain exactly 17 entries (pyhomebroker count)."""
        assert len(BROKERS) == 17

    @pytest.mark.parametrize("broker_id, name, page", ALL_BROKERS)
    def test_each_broker_resolves(self, broker_id, name, page):
        """Every one of the 17 broker IDs must resolve to its config.

        Triangulation: 17 different inputs, all exercising the same
        lookup code path but with distinct expected outputs.
        """
        config = get_broker(broker_id)
        assert config["broker_id"] == broker_id
        assert config["name"] == name
        assert config["page"] == page

    def test_unknown_broker_raises(self):
        """Broker ID 999 must raise BrokerNotSupportedException.

        Spec scenario: 'BrokerNotSupportedException is raised listing supported IDs'.
        """
        with pytest.raises(BrokerNotSupportedException, match="999"):
            get_broker(999)

    def test_get_broker_returns_dict(self):
        """get_broker must return a mapping with the three required keys."""
        config = get_broker(122)
        assert isinstance(config, dict)
        assert set(config.keys()) == {"broker_id", "name", "page"}

    def test_broker_config_typeddict_fields(self):
        """BrokerConfig TypedDict must declare broker_id, name, page."""
        hints = BrokerConfig.__annotations__ if hasattr(BrokerConfig, "__annotations__") else {}
        assert set(hints.keys()) == {"broker_id", "name", "page"}

    def test_broker_not_supported_is_hbd_exception(self):
        """BrokerNotSupportedException raised by get_broker must be HBDException-based."""
        try:
            get_broker(999)
        except HBDException:
            pass
        except Exception as exc:
            pytest.fail(f"get_broker(999) raised {type(exc).__name__}, not HBDException")
        else:
            pytest.fail("get_broker(999) did not raise")


# ---------------------------------------------------------------------------
# T1.3 — Helpers: settlement, numeric conversion, column normalization
# ---------------------------------------------------------------------------


class TestSettlementMap:
    """Strict TDD T1.3 — settlement constants.

    Spec ref: common-infrastructure spec §"Data Formats" (Settlement map),
    §"Requirements" req #5, §"Scenarios" (Settlement mapping, 48hs).
    """

    def test_settlement_map_contents(self):
        """SETTLEMENT_MAP must be {spot→'1', 24hs→'2'} (string values per spec)."""
        assert SETTLEMENT_MAP == {"spot": "1", "24hs": "2"}

    def test_reverse_map_contents(self):
        """SETTLEMENT_REVERSE_MAP must invert the forward map."""
        assert SETTLEMENT_REVERSE_MAP == {"1": "spot", "2": "24hs"}


class TestSetupSettlement:
    """setup_settlement maps settlement strings to API term values; 48hs is deprecated."""

    @pytest.mark.parametrize(
        "settlement, expected",
        [("spot", "1"), ("24hs", "2")],
    )
    def test_valid_settlements(self, settlement, expected):
        """spot→'1', 24hs→'2' (string values matching BYMA API term field)."""
        assert setup_settlement(settlement) == expected
        assert isinstance(setup_settlement(settlement), str)

    def test_48hs_raises_data_exception(self):
        """48hs is deprecated and must raise DataException."""
        with pytest.raises(DataException, match="48hs"):
            setup_settlement("48hs")

    def test_unknown_settlement_raises_data_exception(self):
        """Any unrecognized settlement string must raise DataException."""
        with pytest.raises(DataException):
            setup_settlement("unknown")


class TestConvertToNumericColumns:
    """convert_to_numeric_columns: locale-aware numeric coercion.

    Spec ref: req #4 — strip dots, comma→dot, dash→NaN.
    """

    def test_locale_number_with_comma_decimal(self):
        """'1.234,56' (Argentine format) → 1234.56."""
        df = pd.DataFrame({"price": ["1.234,56"]})
        result = convert_to_numeric_columns(df, ["price"])
        assert result["price"].iloc[0] == pytest.approx(1234.56)

    def test_dash_becomes_nan(self):
        """'-' sentinel → NaN."""
        df = pd.DataFrame({"volume": ["-"]})
        result = convert_to_numeric_columns(df, ["volume"])
        assert pd.isna(result["volume"].iloc[0])

    def test_integer_string_strip_dots(self):
        """'1.234' (thousands separator) → 1234."""
        df = pd.DataFrame({"volume": ["1.234"]})
        result = convert_to_numeric_columns(df, ["volume"])
        assert result["volume"].iloc[0] == 1234

    def test_numeric_passes_through(self):
        """Already-numeric values are unaffected (different code path)."""
        df = pd.DataFrame({"price": [305.50]})
        result = convert_to_numeric_columns(df, ["price"])
        assert result["price"].iloc[0] == pytest.approx(305.50)

    def test_mixed_series(self):
        """A column with locale strings, dash, and plain integer mixed."""
        df = pd.DataFrame({"price": ["1.234,56", "-", "500"]})
        result = convert_to_numeric_columns(df, ["price"])
        assert result["price"].iloc[0] == pytest.approx(1234.56)
        assert pd.isna(result["price"].iloc[1])
        assert result["price"].iloc[2] == pytest.approx(500)

    def test_missing_column_is_skipped(self):
        """Columns not present in the DataFrame must not raise KeyError."""
        df = pd.DataFrame({"price": ["1.234,56"]})
        result = convert_to_numeric_columns(df, ["price", "nonexistent_col"])
        assert result["price"].iloc[0] == pytest.approx(1234.56)


class TestNormalizeColumns:
    """normalize_columns: raw API keys → HBD English column names.

    Spec ref: common-infrastructure spec §"Column Normalization Mapping",
    §"Requirements" req #6; market-data spec normalized columns list.
    """

    def test_pascalcase_columns_mapped(self):
        """PascalCase BYMA API keys are renamed to HBD English names."""
        df = pd.DataFrame(
            [{
                "Symbol": "PAMP",
                "LastPrice": "250,50",
                "StartPrice": "240,00",
                "MaxPrice": "255,00",
                "MinPrice": "238,00",
                "ClosePrice": "248,00",
                "TotalQuantityTraded": "1.000",
                "Term": "1",
                "TradeDate": "20240115",
                "Panel": "accionesLideres",
            }]
        )
        result = normalize_columns(df)
        assert "symbol" in result.columns
        assert "price" in result.columns
        assert "open" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        assert "close" in result.columns
        assert "volume" in result.columns
        assert "settlement" in result.columns
        assert "date" in result.columns
        assert "group" in result.columns

    def test_spanish_abbrev_columns_mapped(self):
        """Spanish abbreviation keys (PREC, VOLU, etc.) are renamed too."""
        df = pd.DataFrame(
            [{
                "PREC": "250,50",
                "VOLU": "1.000",
                "TICK": "PAMP",
                "FECHA": "20240115",
                "APERT": "240,00",
                "MAX": "255,00",
                "MIN": "238,00",
                "CIERRE": "248,00",
                "ESPE": "spot",
                "IMPU": "1.5",
                "CANT": "100",
            }]
        )
        result = normalize_columns(df)
        assert "price" in result.columns
        assert "volume" in result.columns
        assert "tick" in result.columns
        assert "date" in result.columns
        assert "open" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        assert "close" in result.columns
        assert "settlement" in result.columns
        assert "impulse" in result.columns
        assert "quantity" in result.columns

    def test_currency_default_ars(self):
        """If no currency column exists, default to 'ARS'."""
        df = pd.DataFrame([{"price": "250,50"}])
        result = normalize_columns(df)
        assert "currency" in result.columns
        assert result["currency"].iloc[0] == "ARS"

    def test_currency_from_mon_column(self):
        """The Spanish 'MON' key maps to 'currency'."""
        df = pd.DataFrame([{"MON": "USD", "PREC": "100"}])
        result = normalize_columns(df)
        assert "currency" in result.columns
        assert "MON" not in result.columns
        assert result["currency"].iloc[0] == "USD"

    def test_no_columns_lost(self):
        """normalize_columns must not drop columns that have no mapping."""
        df = pd.DataFrame([{"Symbol": "PAMP", "UnknownCol": "value"}])
        result = normalize_columns(df)
        assert "symbol" in result.columns
        assert "UnknownCol" in result.columns  # unmapped columns pass through

    def test_order_book_columns_mapped(self):
        """Order book raw keys → English names (Pos→position, BuyPrice→bid, etc.)."""
        df = pd.DataFrame([{
            "Pos": 1,
            "BuyPrice": "250,00",
            "BuyQuantity": "100",
            "SellPrice": "251,00",
            "SellQuantity": "150",
            "NumberOfOrders": 5,
        }])
        result = normalize_columns(df)
        assert "position" in result.columns
        assert "bid" in result.columns
        assert "bid_size" in result.columns
        assert "ask" in result.columns
        assert "ask_size" in result.columns
        assert "offers_count" in result.columns

