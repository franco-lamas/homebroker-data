# Exploration: HBD Initial Client — Legacy Codebase Analysis

## Executive Summary

The HBD project must rebuild a HomeBroker (BYMA) client for the Argentine stock broker platform. Two legacy codebases exist as reference: **pyhomebroker v1** (v0.55, Apache 2.0, Python 3.6–3.8) and **SHD v2** (v0.0.4-rc4, GPL V3, Python 3.8–3.12). pyhomebroker is a mature, modular library with 13 source files across four functional subpackages (auth, online, orders, history) and full real-time SignalR streaming support. It covers the broadest feature set: authentication, real-time market data via SignalR + HTTP scraping, order placement/cancellation, and historical data (daily + intraday). SHD is a monolithic 636-line single-class rewrite (1 file, no subpackages) that supports only HTTP polling of market boards and portfolio data — no orders, no real-time streaming, no intraday history.

pyhomebroker uses a clean Facade pattern: `HomeBroker` (home_broker.py:28) delegates to `HomeBrokerSession` (auth), `Online` (real-time), `History` (historical), and `Orders`. It raises proper exceptions (`SessionException`, `ServerException`, `DataException`), supports proxy configuration throughout, and returns pandas DataFrames with normalized, documented column names. SHD collapses everything into the `SHDA` class (SHDA.py:19) with login performed eagerly in `__init__`, uses `print()` + `exit()` for error handling (e.g., SHDA.py:78–80, 156–158), and returns DataFrames with raw API column names (e.g., `IMPO`, `ESPE`, `TICK`). Both projects have **zero tests** — no test directories, no CI test steps, no mocking.

The new HBD project (Apache 2.0, Python 3.12, strict TDD) starts from a clean slate with empty `src/hbd/__init__.py` and `tests/__init__.py`. The rebuild should adopt pyhomebroker's modular architecture and exception-based error handling, modernize the transport (httpx instead of requests, typed models via pydantic), and drop the fragile SignalR dependency by offering a polling-based fallback for real-time data. Key decisions will be whether to support real-time streaming at all in v1 and whether to include the orders module (which pyhomebroker itself labels "alpha stage, use at your own risk").

## Module-by-Module Breakdown

### pyhomebroker v1

```
pyhomebroker/
├── __init__.py               # v0.55. Exports HomeBroker (line 25)
├── home_broker.py            # 128 lines. Facade: HomeBroker class (line 28)
├── home_broker_session.py    # 181 lines. Auth: HomeBrokerSession (line 31)
├── common/
│   ├── __init__.py           # Exports brokers, user_agent, helpers, exceptions
│   ├── brokers.py            # 108 lines. 16-broker config list (line 22)
│   ├── exceptions.py         # 33 lines. 4 exception types (lines 22–32)
│   ├── helpers.py            # 30 lines. convert_to_numeric_columns (line 25)
│   └── user_agent.py         # 43 lines. Random UA list (line 24)
├── online/
│   ├── __init__.py           # Exports OnlineCore, OnlineScrapping, OnlineSignalR, Online
│   ├── online_core.py        # 206 lines. ABC: OnlineCore (line 30), DataFrame processors
│   ├── online.py             # 599 lines. Online facade (line 29), connect/disconnect/subscibe
│   ├── online_scrapping.py   # 283 lines. HTTP polling: OnlineScrapping (line 29)
│   └── online_signalr.py     # 445 lines. SignalR real-time: OnlineSignalR (line 36)
├── orders/
│   ├── __init__.py           # Exports Orders
│   └── orders.py             # 536 lines. Orders (line 31): status, buy, sell, cancel
└── history/
    ├── __init__.py           # Exports History
    └── history.py            # 170 lines. History (line 30): daily + intraday
```

**home_broker.py** (Facade — line 28): `HomeBroker.__init__(broker_id, on_open, on_personal_portfolio, ..., proxy_url)` resolves the broker via `__get_broker_data` (line 120, list comprehension lookup in `brokers`), then instantiates four sub-objects: `auth` (HomeBrokerSession), `online` (Online), `history` (History), `orders` (Orders). All receive the same `broker` dict and `proxy_url`.

**home_broker_session.py** (Auth — line 31): `HomeBrokerSession.__init__(broker, proxy_url)`. State: `is_user_logged_in` (bool), `cookies` (dict). `login(dni, user, password, raise_exception)` (line 62): creates a `requests.Session`, tries primary login at `{page}/Login/Ingresar` (line 151), falls back to alternative login at `{page}/Login/IngresarModal` (line 174) on HTTP 500. Parses HTML response with PyQuery (`#usuarioLogueado` check, line 100). Fetches public IP via `api.ipify.org` (line 179). `logout()` (line 119) clears state.

**online/online.py** (Online facade — line 29): `Online.__init__(auth, on_open, ..., proxy_url)`. Composes `OnlineScrapping` (line 102) and `OnlineSignalR` (line 106). Public API: `connect()` / `disconnect()` / `is_connected()` (lines 124–159), subscribe/unsubscribe for personal portfolio (161–214), securities boards (216–301), options (303–346), repos (348–391), order book (393–464), and `get_market_snapshot()` (466–510). All subscribe methods first call `OnlineScrapping` to fetch a snapshot, then call `OnlineSignalR.join_group` to subscribe for real-time updates. Callbacks are wired through name-mangled `__internal_on_*` methods (lines 515–559).

**online/online_core.py** (ABC — line 30): `OnlineCore` with `metaclass=ABCMeta`. Holds all DataFrame column mappings as class-level constants (lines 32–70). Contains shared `process_personal_portfolio` (line 75), `process_securities` (104), `process_options` (124), `process_repos` (146), `process_order_book` (164), `process_order_books` (187). These transform raw API JSON/dict into normalized DataFrames.

**online/online_scrapping.py** (HTTP polling — line 29): `OnlineScrapping(OnlineCore)`. Public methods: `get_personal_portfolio()` (line 55), `get_securities(board, settlement)` (81), `get_options()` (115), `get_repos()` (138), `get_order_book(symbol, settlement)` (161). Private methods: `__get_personal_portfolio` (206, URL `{page}/Prices/GetFavoritos`), `__get_predefined_portfolio` (229, URL `{page}/Prices/GetByPanel`), `__get_asset` (257, URL `{page}/Prices/GetByStock`).

**online/online_signalr.py** (Real-time — line 36): `OnlineSignalR(OnlineCore)`. Uses `signalr.Connection` (line 136, from `signalr-client-threads` library). Connects to `{page}/signalr/hubs`, registers hub `stockpriceshub` (line 137), subscribes to callbacks: `broadcast` → `__internal_securities_options_repos`, `sendStartStockFavoritos`/`sendStockFavoritos` → `__internal_personal_portfolio`, `sendStartStockPuntas`/`sendStockPuntas` → `__internal_order_book` (lines 139–145). Uses a worker thread (line 158, `__worker_thread_run` at 241) with lock-protected queues to decouple event reception from DataFrame processing. `join_group`/`quit_group` (lines 192–236) invoke SignalR `JoinGroup`/`QuitGroup` server methods.

**orders/orders.py** (Orders — line 31): `Orders.__init__(auth, proxy_url)`. `get_orders_status(account_id)` (82): POST `{page}/Consultas/GetConsulta` with `proceso: '121'` (line 309), filters `listaDetalleTiker` → `ORDE` list. `send_buy_order`/`send_sell_order` (110/162): two-step validation+confirmation via `ValidarCargaOrdenAsync` (line 408) then `EnviarOrdenConfirmadaAsyc` (line 447), with optional `EnviarOrdenReconfirmada` (478) for reconfirmation. `cancel_order`/`cancel_all_orders` (214/256): uses `EnviarCancelacionAsyc` (496) + `EnviarOrdenCanceladaAsyc` (529). Thread-safe via `__orders_send_lock` (line 56).

**history/history.py** (History — line 30): `History.__init__(auth, proxy_url)`. `get_daily_history(symbol, from_date, to_date)` (59): GET `{page}/HistoricoPrecios/history?symbol={...}&resolution=D&...` (line 89), returns DataFrame with date/open/high/low/close/volume. `get_intraday_history(symbol, from_date, to_date)` (105): GET `{page}/Intradiario/history?symbol={...}&resolution=1&...` (line 144), converts timestamps from UTC to Argentina time (offset 3 hours, line 33).

**common/brokers.py** (line 22): List of 16 dicts, each with `broker_id` (int), `name` (str), `page` (full URL like `https://operarhb.bavsa.com`). Used by both `HomeBroker` and `HomeBrokerSession`.

**common/exceptions.py** (lines 22–32): `SessionException`, `BrokerNotSupportedException`, `ServerException`, `DataException`.

**common/helpers.py** (line 25): `convert_to_numeric_columns(df, columns)` — handles locale-quirk number formatting (strips `.`, replaces `,` with `.`, converts `-` to `NaN`).

**common/user_agent.py** (line 24): `user_agent` — random choice from 18 browser User-Agent strings.

### SHD v2

```
SHDA/
├── __init__.py               # v0.0.4-rc4. Exports * from SHDA (line 17)
├── SHDA.py                   # 636 lines. Monolithic SHDA class (line 19)
├── common/
│   ├── __init__.py           # Exports brokers, helpers, exceptions
│   ├── brokers.py            # 102 lines. 15-broker config list (line 22)
│   ├── exceptions.py         # 33 lines. Same 4 exception types
│   └── helpers.py            # 32 lines. Same convert_to_numeric_columns
└── portfolio/
    ├── __init__.py           # Exports Portfolio (line 1)
    └── portfolio.py          # 112 lines. Portfolio class (line 5)
```

**SHDA.py** (line 19): Everything in one class. Class-level constants (lines 20–54): settlement maps, board maps, column definitions for personal portfolio, repos, securities, options, MERVAL/indexes. `__init__(broker, dni, user, password)` (line 55): creates `requests.session()`, looks up broker host, performs login immediately (lines 76–127), then instantiates `Portfolio` (line 128 — `self.get_portfolio = Portfolio(...)`). Uses `print()` + `exit()` for errors (e.g., lines 78–80, 156–158, 367–368).

Market data methods (all follow same pattern — inline headers dict, POST to `{host}/Prices/GetByPanel` with `panel` + `term` payload):
- `get_bluechips(settlement)` (line 131) — panel `accionesLideres`
- `get_galpones(settlement)` (line 170) — panel `panelGeneral`
- `get_cedear(settlement)` (line 209) — panel `cedears`
- `get_bonds(settlement)` (line 248) — panel `rentaFija`
- `get_short_term_bonds(settlement)` (line 287) — panel `letes`
- `get_corporate_bonds(settlement)` (line 326) — panel `obligaciones`
- `get_options()` (line 393) — panel `opciones`
- `get_repos()` (line 537) — panel `cauciones`
- `get_MERVAL()` (line 448) — panel `indices`
- `get_personal_portfolio()` (line 484) — GET `{host}/Prices/GetFavoritos`

Account/portfolio:
- `account(comitente)` (line 365) — POST `{host}/Consultas/GetConsulta` with `proceso: '22'` (line 372). Returns DataFrame with raw columns (`IMPO`, `ESPE`, `TESP`, `NERE`, `GTOS`, `DETA`, `TIPO`, `Hora`, `AMPL`, `DIVI`, `TICK`, `CANT`, `PCIO`, `CAN3`, `CAN2`, `CAN0`). Note: hardcoded `consolida: '0'`, `proceso: '22'`, and date fields set to `None`.

History:
- `get_daily_history(symbol, from_date, to_date)` (line 587) — GET `https://{host}/HistoricoPrecios/history?symbol=...` (line 598). Same endpoint as pyhomebroker but no cookie authentication (session created in constructor).

**portfolio/portfolio.py** (line 5): `Portfolio.__init__(headers, host, session)`. Has `by_date(comitente, date, moneda)` (line 29) — POST `{host}/Consultas/GetConsulta` with `proceso: 10` for ARS or `proceso: 91` for USD (line 56). Returns a DataFrame with normalized keys (`symbol`, `description`, `position_size`, `position_price`, `date_close`, `position`, `PNL`, `group`). **Note**: This class is instantiated as `self.get_portfolio` in SHDA.__init__ (line 128) but the `account()` method does NOT use it — it reimplements the same logic inline with different `proceso` value ('22' vs '10'/'91'). This is an incomplete refactoring.

**common/brokers.py** (line 22): List of 15 dicts. Notable: **missing** broker_id 122 (Industrial Valores S.A.) that pyhomebroker includes. `page` field is a bare hostname (e.g., `operarhb.bavsa.com`) without `https://` prefix — requiring URL construction with f-strings everywhere (e.g., SHDA.py:76, 109, 154).

## Functionality Matrix

| Feature | pyhomebroker v1 | SHD v2 |
|---|---|---|
| **Authentication** | `hb.auth.login(dni, user, password)` + `.logout()` — separate session class | Login in `SHDA.__init__(broker, dni, user, password)` — no logout |
| **Session state** | `is_user_logged_in` + `cookies` dict on `HomeBrokerSession` | `__is_user_logged_in` on `SHDA` |
| **Proxy support** | Yes — `proxy_url` threaded through all constructors | No |
| **IP address capture** | Yes — `api.ipify.org` (home_broker_session.py:179) | No |
| **Alternative login** | Yes — fallback to `Login/IngresarModal` on HTTP 500 (line 94) | No |
| **Real-time streaming** | Yes — SignalR (`OnlineSignalR`, online_signalr.py:36) | No |
| **HTTP polling (scrapping)** | Yes — `OnlineScrapping` (online_scrapping.py:29) | Yes — inline in each method |
| **Personal portfolio (favorites)** | `subscribe_personal_portfolio()` (real-time) + `get_personal_portfolio()` (snapshots) | `get_personal_portfolio()` (snapshot only) |
| **Securities boards** | `subscribe_securities(board, settlement)` — 6 boards via SignalR | `get_bluechips`, `get_galpones`, `get_cedear`, `get_bonds`, `get_short_term_bonds`, `get_corporate_bonds` |
| **Options** | `subscribe_options()` (real-time) + `get_options()` (snapshots) | `get_options()` |
| **Repos** | `subscribe_repos()` (real-time) + `get_repos()` (snapshots) | `get_repos()` |
| **Indices/MERVAL** | Part of `get_market_snapshot()` | `get_MERVAL()` |
| **Order book (Level 2)** | `subscribe_order_book(symbol, settlement)` + `get_order_book(symbol, settlement)` | No |
| **Orders — status** | `hb.orders.get_orders_status(account_id)` — `proceso: '121'` | No |
| **Orders — send buy** | `hb.orders.send_buy_order(...)` | No |
| **Orders — send sell** | `hb.orders.send_sell_order(...)` | No |
| **Orders — cancel** | `hb.orders.cancel_order`, `cancel_all_orders` | No |
| **Daily history** | `hb.history.get_daily_history(symbol, from, to)` | `hb.get_daily_history(symbol, from, to)` |
| **Intraday history** | `hb.history.get_intraday_history(symbol, from, to)` | No |
| **Account/portfolio positions** | Via `get_orders_status` (proceso 121) or `get_personal_portfolio` | `account(comitente)` (proceso 22) + `Portfolio.by_date` (proceso 10/91) |
| **Market snapshot** | `hb.online.get_market_snapshot()` — all boards in one call | No (must call each board method separately) |
| **Error handling** | Exceptions (`SessionException`, `ServerException`, `DataException`) | `print()` + `exit()` — unrecoverable |
| **Settlements** | `spot`, `24hs`, `48hs` (string) mapped to `1`, `2`, `3` (int) | `spot`, `24hs`, `48hs` mapped to `1`, `2`, `3` (int) |
| **Data format** | pandas DataFrame with normalized columns, indexed by (symbol, settlement) | pandas DataFrame with raw/mixed column names |

## Key Patterns Identified

### 1. Broker Abstraction (both projects)
Both use a static `brokers` list of dicts. pyhomebroker (common/brokers.py:22) has 16 entries with `broker_id` (int), `name`, and `page` (full URL). SHD (common/brokers.py:22) has 15 entries — missing `Industrial Valores S.A.` (id 122) — and uses bare hostnames without `https://`. Lookup is done by list comprehension filtering on `broker_id` (pyhomebroker home_broker.py:122, SHD SHDA.py:628).

### 2. Facade Pattern (pyhomebroker) vs Monolithic (SHD)
pyhomebroker's `HomeBroker` (home_broker.py:28) is a clean facade composing four focused sub-objects. SHD's `SHDA` class (SHDA.py:19) does everything: login in constructor, 10+ HTTP methods inline, no sub-objects (except an unused `Portfolio` instance at line 128).

### 3. Online Strategy Pattern (pyhomebroker only)
`OnlineCore` (online_core.py:30) is an ABC with shared DataFrame processors. `OnlineScrapping` (online_scrapping.py:29) and `OnlineSignalR` (online_signalr.py:36) both inherit from it. The `Online` facade (online.py:29) composes both — snapshot is fetched via scrapping, real-time updates via SignalR. This is a clean Strategy/Composition pattern.

### 4. Thread-Driven Event Processing (pyhomebroker only)
`OnlineSignalR` uses a background worker thread (line 158) with lock-protected queues (`__personal_portfolio_queue`, `__securities_options_repos_queue`, `__order_book_queue`) to decouple SignalR event callbacks from DataFrame processing. This prevents user callback code from blocking the WebSocket event loop.

### 5. Two-Step Order Operations
pyhomebroker's order flow (orders.py:110): `__send_order_validation` → `__send_order_confirmation` → optionally `__send_order_reconfirmation` → return order number. Cancel flow (orders.py:214): fetch status, find order, `__send_cancel_validation` → `__send_cancel_confirmation`. Thread-safe via `Lock` (line 56).

### 6. DataFrame Normalization Pipeline
Both projects follow the same pattern: raw API JSON → `pd.DataFrame(data)` → filter/rename columns → `convert_to_numeric_columns` → set index → return. pyhomebroker's `process_*` methods (online_core.py:75–206) are more thorough — they handle datetime parsing, settlement mapping, call/put mapping, empty dataframe fallbacks, and consistent column naming. SHD's methods (SHDA.py:160–168) do similar but with less robust null/empty handling.

### 7. Error Handling
**pyhomebroker**: Proper exceptions with `raise_exception` flag on login (line 62). HTTP errors via `response.raise_for_status()`. API errors via `response['Success']` check (online_scrapping.py:224, orders.py:318). All public methods raise typed exceptions documented in docstrings.

**SHD**: Uses `print("message")` + `exit()` for errors (SHDA.py:76–80, 156–158, 188–189). This is unrecoverable and untestable. Only `Portfolio.by_date` (portfolio.py:76) raises `ValueError` properly.

### 8. Class-Level Column Constants
Both use class-level `__` attributes for column mappings (pyhomebroker online_core.py:50–70; SHD SHDA.py:25–54). These are name-mangled private class attributes in pyhomebroker but plain class attributes in SHD (no `__` prefix, so no name mangling).

### 9. Headers/Request Duplication
**pyhomebroker**: Headers are constructed inline in each private method but centralized in `user_agent.py`. 18 random User-Agent strings (user_agent.py:24).

**SHD**: The exact same 17-header dict is copy-pasted verbatim across 10+ methods (SHDA.py:135–151, 174–190, 213–230, etc.). This is severe code duplication — a maintenance nightmare.

## Dependency List (Ranked by Importance)

### pyhomebroker
| Rank | Dependency | Version | Purpose | Source |
|---|---|---|---|---|
| 1 | **pandas** | >=1.0.0 | Primary data structure — all market data returned as DataFrames | requirements.txt:2 |
| 2 | **requests** | >=2.21.0 | HTTP client for all REST/HTTPS calls (login, scrapping, orders, history) | requirements.txt:5 |
| 3 | **signalr-client-threads** | >=0.0.12 | SignalR real-time WebSocket connection for live market data | requirements.txt:4 |
| 4 | **pyquery** | >=1.2 | HTML parsing of login page response to detect `#usuarioLogueado` element | requirements.txt:3 |
| 5 | **numpy** | >=1.18.1 | Numeric type conversion, NaN handling in `convert_to_numeric_columns` | requirements.txt:1 |

### SHD
| Rank | Dependency | Version | Purpose | Notes |
|---|---|---|---|---|
| 1 | **pandas** | ==2.2.2 | DataFrame returns for all market data | requirements.txt:7 |
| 2 | **numpy** | ==2.0.1 | Numeric processing (`np.nan` in helpers.py) | requirements.txt:6 |
| 3 | **Requests** | ==2.32.3 | HTTP client for all endpoints | requirements.txt:11 |
| 4 | **pyquery** | ==2.0.0 | HTML parsing for login page | requirements.txt:8 |
| 5 | **lxml** | ==4.9.4 | XML/HTML parser backing pyquery | requirements.txt:5 — transitive dep of pyquery |
| 6 | **cssselect** | ==1.2.0 | CSS selector support for pyquery | requirements.txt:3 — transitive dep |
| 7–14 | certifi, charset-normalizer, idna, urllib3, python-dateutil, pytz, six, tzdata | pinned | Transitive deps of requests/pandas | requirements.txt:1–14 |

**Notable: SHD has NO signalr-client dependency**, confirming no real-time streaming support. SHD's requirements.txt is fully pinned (exact versions) while pyhomebroker uses minimum version constraints.

## Testing Status

**Neither project has any tests.** No test directories, no test files, no pytest configuration, no test steps in CI.

### pyhomebroker
- **No test files exist** — searched entire repository, zero test files found.
- **CI**: Only `.github/FUNDING.yml` exists (no workflows directory). No automated testing.
- **Testability concerns**: `HomeBrokerSession.login` (home_broker_session.py:89) uses a context manager `with rq.Session() as sess:` making it harder to inject mock sessions. `OnlineSignalR.connect` (online_signalr.py:128) creates a new `rq.Session()` internally and passes it to `signalr.Connection` (line 136), making real-time connection testing very difficult without significant refactoring. Network calls are direct `rq.post`/`rq.get` calls with no injectable HTTP adapter.
- **Mocking**: No mock infrastructure exists. The `requests.Session` is created internally in methods, not injected.

### SHD
- **No test files exist** — searched entire repository, zero test files found.
- **CI**: `.gitlab-ci.yml` only builds and uploads to PyPI — no test step (lines 1–8 of the YAML).
- **Testability concerns**: `SHDA.__init__` (SHDA.py:55) performs login immediately — constructing a `SHDA` instance requires network access to a broker's login endpoint. This makes even basic unit testing impossible without either a mock broker or constructor refactoring. Furthermore, error paths use `exit()` (line 80, 126, 158), which calls `sys.exit()` and terminates the process — unrecoverable and untestable.

### HBD Project (current state)
- **Empty** — `src/hbd/__init__.py` is 0 bytes, `tests/__init__.py` is 0 bytes.
- **Configured for strict TDD** — `pyproject.toml` has pytest with `--cov=src/hbd`, `--strict-markers`, `--strict-config`.
- **Dependencies**: pydantic, httpx, pandas, numpy — modern alternatives to the legacy `requests`, `pyquery`, `signalr-client-threads`.

## API Endpoint Reference

Both projects target the same BYMA/HomeBroker web API endpoints:

| Endpoint | Method | pyhomebroker location | SHD location | Purpose |
|---|---|---|---|---|
| `/Login/Ingresar` | POST | home_broker_session.py:151 | SHDA.py:109 | Primary login |
| `/Login/IngresarModal` | POST | home_broker_session.py:161 | — | Fallback login (HTTP 500) |
| `/signalr/hubs` | GET | online_signalr.py:126 | — | SignalR negotiation |
| `/Prices/GetFavoritos` | POST | online_scrapping.py:217 | SHDA.py:507 | Personal portfolio/favorites |
| `/Prices/GetByPanel` | POST | online_scrapping.py:240 | SHDA.py:154 | Market boards by panel name |
| `/Prices/GetByStock` | POST | online_scrapping.py:268 | — | Order book for specific symbol |
| `/Consultas/GetConsulta` | POST | orders.py:304 | SHDA.py:379 | Orders status (proceso 121), portfolio (proceso 22) |
| `/Order/ValidarCargaOrdenAsync` | POST | orders.py:408 | — | Validate new order |
| `/Order/EnviarOrdenConfirmadaAsyc` | POST | orders.py:447 | — | Confirm/submit order |
| `/Order/EnviarOrdenReconfirmada` | POST | orders.py:478 | — | Reconfirm order (risk) |
| `/Order/EnviarCancelacionAsyc` | POST | orders.py:496 | — | Cancel validation |
| `/Order/EnviarOrdenCanceladaAsyc` | POST | orders.py:529 | — | Cancel confirmation |
| `/HistoricoPrecios/history` | GET | history.py:89 | SHDA.py:598 | Daily historical data |
| `/Intradiario/history` | GET | history.py:144 | — | Intraday historical data |

**Key `proceso` values**: `121` = orders status (pyhomebroker), `22` = account/portfolio (SHD), `10` = portfolio in ARS (SHD Portfolio.by_date), `91` = portfolio in USD (SHD Portfolio.by_date).

## Risks

1. **License contamination**: SHD is GPL V3. Direct code copying into the Apache 2.0-licensed HBD project would create licensing conflicts. Only API endpoint patterns and architectural ideas can be safely adopted.
2. **No test infrastructure**: Neither legacy project has tests, mocks, or CI testing. All network interactions are hardcoded `requests` calls with no dependency injection, making testing extremely difficult without architectural refactoring.
3. **`exit()` calls in SHD**: `print()` + `exit()` (SHD SHDA.py:80, 126, 158) terminates the process on errors — unacceptable for a library API and impossible to test.
4. **SignalR dependency fragility**: pyhomebroker relies on `signalr-client-threads` (v0.0.12, last released years ago) which lacks proxy support for WebSocket connections (documented in README:217). The real-time streaming subsystem is the most complex and brittle part of pyhomebroker.
5. **Code duplication in SHD**: The same 17-line headers dict is copy-pasted across 10+ methods (SHD SHDA.py:135–151 repeated at 174, 213, 248, 288, 310, 328, 397, 452, 488, 542). Any header change requires 10+ edits.
6. **Incomplete refactoring in SHD**: `Portfolio` class (portfolio/portfolio.py:5) is instantiated at SHDA.py:128 but never used — `account()` method reimplements the same logic inline with different `proceso` value. Dead code / incomplete migration.
7. **Broker list drift**: SHD's brokers.py (102 lines) has 15 entries — missing `Industrial Valores S.A.` (id 122) — while pyhomebroker has 16. Also SHD uses bare hostnames while pyhomebroker uses full URLs, requiring every SHD caller to construct `f"https://{self.__host}/..."` (error-prone).
8. **Orders module is alpha**: pyhomebroker's own README (line 189) states order methods "may have errors" and "It is NOT recommended to use them if you don't know enough about the market." The order flow involves financial risk.
9. **No intraday history in SHD**: SHD's `get_daily_history` (SHDA.py:587) duplicates pyhomebroker's history.py:59 but SHD lacks the intraday counterpart (history.py:105), limiting backtesting capability.

## Recommendation

For the HBD v1 initial client, adopt pyhomebroker's **modular Facade architecture** as the structural blueprint:
- Separate sub-objects: `auth` (session), `online` (market data), `history` (historical data), and optionally `orders` (defer to a later phase due to risk).
- Use proper exception-based error handling (learn from pyhomebroker, avoid SHD's `exit()` anti-pattern).
- Return pandas DataFrames with normalized column names (pyhomebroker's approach in online_core.py:50–70).
- Modernize the transport layer: use `httpx` (already in pyproject.toml) instead of `requests` for better HTTP client API, and `pydantic` for API response parsing/models.
- **Defer real-time SignalR streaming** to a later phase — start with HTTP polling (like SHD and pyhomebroker's `OnlineScrapping`) and add SignalR as a separate `OnlineSignalR` class later. This reduces initial complexity and avoids the fragile `signalr-client-threads` dependency.
- **Defer the orders module** — pyhomebroker itself labels it alpha-stage.

## Ready for Proposal
**Yes** — The exploration is comprehensive. The proposal phase (`sdd-propose`) should define scope tiers:
- **Tier 1 (must-have)**: Authentication (login/logout with IP capture, cookie management), connection establishment, market data boards (bluechips, general_board, cedears, government_bonds, short_term_government_bonds, corporate_bonds, options, repos, MERVAL), personal portfolio (favorites), order book (level 2), daily + intraday history. All via HTTP polling with exception-based errors.
- **Tier 2 (phase 2)**: Orders (get status, send buy/sell, cancel) — with appropriate risk warnings.
- **Tier 3 (phase 3)**: Real-time SignalR streaming with the thread-queue pattern from pyhomebroker.

The `strict_tdd` flag and pytest config are already in place. The next recommended phase is `sdd-propose`.
