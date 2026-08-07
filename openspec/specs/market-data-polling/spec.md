# Market Data Polling Specification

## Purpose
Poll all BYMA market boards (securities, options, repos, indices, personal portfolio, Level 2 order book) over HTTP, returning normalized `pd.DataFrame` objects with English column names.

## Scope

**In:** 6 boards, options, repos, indices, personal portfolio, Level 2 order book via POST `/Prices/GetByPanel` and `/Prices/GetByStock`.

**Out:** Real-time SignalR, orders, async, proxy — all Tier 2/excluded.

## API

| Method | Signature |
|--------|-----------|
| `get_securities` | `Online.snapshot.get_securities(board: str, settlement: str) -> pd.DataFrame` |
| `get_options` | `Online.snapshot.get_options() -> pd.DataFrame` |
| `get_repos` | `Online.snapshot.get_repos() -> pd.DataFrame` |
| `get_indices` | `Online.snapshot.get_indices() -> pd.DataFrame` |
| `get_personal_portfolio` | `Online.snapshot.get_personal_portfolio() -> pd.DataFrame` |
| `get_order_book` | `Online.snapshot.get_order_book(symbol: str, settlement: str) -> pd.DataFrame` |
| `get_market_snapshot` | `Online.snapshot.get_market_snapshot() -> dict[str, pd.DataFrame]` |

## Mappings

| HBD board | API panel | | HBD settlement | API term |
|-----------|-----------|-|-----------------|----------|
| `bluechips` | `accionesLideres` | | `spot` | `1` |
| `general_board` | `panelGeneral` | | `24hs` | `2` |
| `cedears` | `cedears` | | `48hs` | — (deprecated) |
| `government_bonds` | `rentaFija` | | | |
| `short_term_government_bonds` | `letes` | | | |
| `corporate_bonds` | `obligaciones` | | | |

Other panels: `opciones`, `cauciones`, `indices`.

## Requirements

| # | Requirement | RFC 2119 |
|---|-------------|----------|
| 1 | POST JSON `{panel, term}` to `/Prices/GetByPanel` for securities, options, repos, indices | MUST |
| 2 | POST JSON `{symbol, term}` to `/Prices/GetByStock` for order book | MUST |
| 3 | GET `/Prices/GetFavoritos` for personal portfolio | MUST |
| 4 | Normalize raw API columns to HBD English set via `normalize_columns` | MUST |
| 5 | Apply `convert_to_numeric_columns` for locale quirks on all numeric columns | MUST |
| 6 | Raise `DataException` when `Success: false` in response | MUST |
| 7 | Raise `DataException` when required columns missing after normalization | MUST |
| 8 | Return empty DataFrame with correct columns when no data | MUST |
| 9 | `get_market_snapshot()` aggregates all boards into a dict keyed by name | SHOULD |

## Scenarios

#### Scenario: Securities by board and settlement
- GIVEN board `bluechips`, settlement `spot`, logged-in session
- WHEN `get_securities()` POSTs `{panel: "accionesLideres", term: "1"}` to `/Prices/GetByPanel`
- THEN a DataFrame with normalized English columns is returned

#### Scenario: Options board
- GIVEN a logged-in session
- WHEN `get_options()` POSTs `{panel: "opciones", term: ""}` to `/Prices/GetByPanel`
- THEN a DataFrame with options data (symbol, price, strike, kind) is returned

#### Scenario: API returns Success false
- GIVEN the server returns `{Success: false, Error: {Descripcion: "..."}}`
- WHEN any polling method is called
- THEN `DataException` is raised with the server's error description

#### Scenario: HTTP transport error
- GIVEN a network failure or 5xx response
- WHEN any polling method is called
- THEN `ServerException` is raised

#### Scenario: Empty response
- GIVEN `Result.Stocks` is null or empty
- WHEN `get_securities()` is called
- THEN an empty DataFrame with all normalized columns is returned

#### Scenario: Order book (Level 2)
- GIVEN symbol `PAMP`, settlement `24hs`
- WHEN `get_order_book()` POSTs `{symbol: "PAMP", term: "2"}` to `/Prices/GetByStock`
- THEN a DataFrame with bid/ask price/size and position columns is returned

## Error Handling

| Condition | Exception |
|-----------|-----------|
| `Success: false` in response | `DataException` |
| Required columns missing | `DataException` |
| HTTP transport error | `ServerException` |
| Not logged in | `SessionException` |
| Invalid board name | `DataException` |
| Invalid settlement (`48hs`) | `DataException` |

## Data Formats

**Response envelope:** `{Success: bool, Result: {Stocks: list[dict] \| null}, Error: {Descripcion: str}}`

**Order book request (`GetByStock`):** `{symbol: str, term: str}`

**Normalized columns:** `symbol`, `settlement`, `price`, `open`, `high`, `low`, `close`, `volume`, `currency`, `date`.

## Dependencies

- `Auth` session (logged in, provides cookies + broker page URL)
- `common.helpers`: `convert_to_numeric_columns`, `normalize_columns`, `setup_settlement`
- `common.exceptions`: `DataException`, `ServerException`, `SessionException`
- `httpx.Client`, `pandas`, `numpy`
