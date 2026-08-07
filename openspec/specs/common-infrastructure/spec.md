# Common Infrastructure Specification

## Purpose
Shared foundation for all HBD modules: 17-broker config, exception hierarchy, and DataFrame helpers for numeric conversion, column normalization, and settlement mapping.

> Broker count: 17 in pyhomebroker (SHD had 16, dropped id 122).

## Scope

**In:** 17 brokers, `get_broker()`, 4 exceptions + `HBDException` base, numeric/column/settlement helpers.

**Out:** Proxy support (Tier 2), orders helpers (deferred).

## API

| Function | Signature |
|----------|-----------|
| `get_broker` | `get_broker(broker_id: int) -> dict[str, str]` |
| `convert_to_numeric_columns` | `convert_to_numeric_columns(df, columns) -> pd.DataFrame` |
| `normalize_columns` | `normalize_columns(df) -> pd.DataFrame` |
| `setup_settlement` | `setup_settlement(settlement: str) -> str` |

## Broker Configuration

| ID | Name | Page |
|----|------|------|
| 12 | Buenos Aires Valores S.A. | `https://operarhb.bavsa.com` |
| 20 | Proficio Investment S.A. | `https://newsystem.proficioinvestment.com.ar` |
| 81 | Tomar Inversiones S.A | `https://clientes2.tminversiones.com.ar` |
| 88 | Bell Investments S.A. | `https://operar.bellbursatil.com` |
| 91 | RIG Valores S.A. | `https://rigvaloresweb.com/` |
| 94 | Soluciones Financieras S.A. | `https://sistemag.solfin.com.ar` |
| 122 | Industrial Valores S.A. | `https://inversiones.bind.com.ar/Clientes` |
| 127 | Maestro y Huerres S.A | `https://operar.maestroyhuerres.com` |
| 153 | Bolsa de Comercio del Chaco | `https://clientes.bcch.org.ar` |
| 163 | Prosecurities S.A. | `http://operar.psec.com.ar` |
| 186 | Servente y Cia. S.A. | `http://clientes.serventeycia.com` |
| 201 | Alfy Inversiones S.A. | `https://acceso.alfyinversiones.com.ar` |
| 203 | Invertir en Bolsa S.A. | `https://clientesv2.invertirenbolsa.com.ar` |
| 209 | Futuro Bursátil S.A. | `https://homebroker.futurobursatil.com.ar` |
| 233 | Sailing S.A. | `https://login.sailinginversiones.com` |
| 265 | Negocios Financieros y Bursátiles | `https://cocoscap.com` |
| 284 | Veta Capital S.A. | `http://cuentas.vetacapital.com.ar` |

## Column Normalization Mapping

| Raw API key | HBD | | Raw API key | HBD |
|-------------|-----|-|-------------|-----|
| `Symbol` | `symbol` | | `StartPrice` | `open` |
| `LastPrice` | `price` | | `MaxPrice` | `high` |
| `MinPrice` | `low` | | `ClosePrice` | `close` |
| `TotalQuantityTraded` | `volume` | | `Term` | `settlement` |
| `TradeDate` | `date` | | `Panel`/`group` | (derived) |

> `currency` column added by HBD (defaults to `ARS`); not in legacy code.

## Requirements

| # | Requirement | RFC 2119 |
|---|-------------|----------|
| 1 | `get_broker()` returns `{broker_id, name, page}` for valid IDs | MUST |
| 2 | `get_broker()` raises `BrokerNotSupportedException` for unknown IDs | MUST |
| 3 | All 4 exceptions inherit from `HBDException` base | MUST |
| 4 | `convert_to_numeric_columns` strips dots, comma→dot, `-`→`NaN` | MUST |
| 5 | `setup_settlement` maps `spot`→`1`, `24hs`→`2`, raises `DataException` for `48hs` | MUST |
| 6 | `normalize_columns` maps all known raw API keys to HBD English names | MUST |

## Scenarios

#### Scenario: Valid broker lookup
- GIVEN `broker_id=122`
- WHEN `get_broker(122)` is called
- THEN the matching broker dict is returned

#### Scenario: Unknown broker
- GIVEN `broker_id=999`
- WHEN `get_broker(999)` is called
- THEN `BrokerNotSupportedException` is raised listing supported IDs

#### Scenario: Locale numeric conversion
- GIVEN a DataFrame cell `"1.234,56"` (Argentine locale)
- WHEN `convert_to_numeric_columns(df, ['price'])` is called
- THEN the value becomes numeric `1234.56`

#### Scenario: Dash to NaN
- GIVEN a DataFrame cell `"-"`
- WHEN `convert_to_numeric_columns` processes it
- THEN the value becomes `NaN`

#### Scenario: Settlement mapping
- GIVEN `settlement` of `spot` or `24hs`
- WHEN `setup_settlement()` is called for each
- THEN `spot`→`"1"`, `24hs`→`"2"` are returned

#### Scenario: Deprecated 48hs settlement
- GIVEN `settlement="48hs"`
- WHEN `setup_settlement("48hs")` is called
- THEN `DataException` is raised

## Error Handling

| Condition | Exception |
|-----------|-----------|
| Unknown broker_id | `BrokerNotSupportedException` |
| Invalid settlement (`48hs`) | `DataException` |
| All base exception | `HBDException` |

## Data Formats

**Broker dict:** `{broker_id: int, name: str, page: str}` · **Settlement map:** `{"spot": "1", "24hs": "2"}`

**Exception hierarchy:**
```
HBDException → SessionException, BrokerNotSupportedException, ServerException, DataException
```

## Dependencies

- `pandas`, `numpy` — no internal HBD dependencies (base layer)
