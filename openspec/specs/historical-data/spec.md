# Historical Data Specification

## Purpose
Retrieve daily historical price data for BYMA-listed securities via the `/HistoricoPrecios/history` endpoint, returning a normalized `pd.DataFrame`.

## Scope

**In:**
- `get_daily_history(symbol, from_date, to_date)` — daily only (`resolution=D`)
- Epoch conversion for `from`/`to` date parameters
- Date column converted to `datetime` objects
- Empty response handling (returns empty DataFrame with correct columns)
- Volume as integer type

**Out:**
- Intraday history (deferred — Decision #10)
- Options or repos history (not in Tier 1)
- Real-time or streaming history

## API

| Method | Signature |
|--------|-----------|
| `get_daily_history` | `History.get_daily_history(symbol: str, from_date: datetime, to_date: datetime) -> pd.DataFrame` |

## Requirements

| # | Requirement | RFC 2119 |
|---|-------------|----------|
| 1 | Convert `from_date` and `to_date` to Unix epoch seconds before sending | MUST |
| 2 | GET `/HistoricoPrecios/history?symbol={}&resolution=D&from={}&to={}` | MUST |
| 3 | Return DataFrame with columns: `date`, `open`, `high`, `low`, `close`, `volume` | MUST |
| 4 | Convert `date` column from epoch seconds to `datetime` objects | MUST |
| 5 | Cast `volume` to integer type | MUST |
| 6 | Return empty DataFrame with correct columns on empty API response | MUST |
| 7 | Raise `DataException` on invalid symbol or date range | MUST |
| 8 | Raise `ServerException` on HTTP transport errors | MUST |
| 9 | Accept both `str` (`YYYY-MM-DD`) and `datetime.date` inputs for dates | SHOULD |

## Scenarios

#### Scenario: Daily history success
- GIVEN symbol `AAPL`, `from_date=2024-01-01`, `to_date=2024-01-31`, and a logged-in session
- WHEN `get_daily_history()` GETs the history endpoint with epoch values
- THEN a DataFrame with `date`, `open`, `high`, `low`, `close`, `volume` is returned, with `date` as datetime and `volume` as int

#### Scenario: String date input
- GIVEN `from_date="2024-01-01"` as a string
- WHEN `get_daily_history()` is called
- THEN the string is parsed to a `datetime.date` before epoch conversion

#### Scenario: Empty response
- GIVEN the API returns `{t: [], o: [], h: [], l: [], c: [], v: []}`
- WHEN `get_daily_history()` processes the response
- THEN an empty DataFrame with columns `date, open, high, low, close, volume` is returned (no exception)

#### Scenario: Invalid symbol
- GIVEN a symbol not traded on BYMA (e.g., `NOTAREAL`)
- WHEN `get_daily_history()` is called
- THEN `DataException` is raised

#### Scenario: HTTP transport error
- GIVEN the server returns a 5xx error
- WHEN `get_daily_history()` is called
- THEN `ServerException` is raised

#### Scenario: Date range validation
- GIVEN `from_date > to_date`
- WHEN `get_daily_history()` is called
- THEN `DataException` is raised (invalid date range)

## Error Handling

| Condition | Exception |
|-----------|-----------|
| HTTP transport error | `ServerException` |
| Invalid symbol | `DataException` |
| Invalid date range (`from > to`) | `DataException` |
| Not logged in | `SessionException` |

## Data Formats

**Request URL:**
```
GET {broker_page}/HistoricoPrecios/history?symbol={SYMBOL}&resolution=D&from={EPOCH_FROM}&to={EPOCH_TO}
```

**Response (JSON):**
| Field | Type | Description |
|-------|------|-------------|
| `t` | list[int] | Timestamps (epoch seconds) |
| `o` | list[float] | Open prices |
| `h` | list[float] | High prices |
| `l` | list[float] | Low prices |
| `c` | list[float] | Close prices |
| `v` | list[int] | Volumes |

**Output DataFrame columns:** `date` (datetime), `open` (float), `high` (float), `low` (float), `close` (float), `volume` (int).

## Dependencies

- `Auth` session — must be logged in, provides broker page URL + cookies
- `common.exceptions.DataException`, `ServerException`, `SessionException`
- `httpx.Client` — GET transport
- `pandas` — DataFrame construction
- `datetime` — epoch conversion (`toordinal` or `timestamp()`)
