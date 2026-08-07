# Proposal: HBD Initial Client — Python 3.12 BYMA Client (Tier 1)

## Intent

Rebuild a modern Python 3.12 BYMA/HomeBroker client as an Apache 2.0-licensed library with strict TDD. Both legacy codebases (pyhomebroker v1 Apache 2.0, SHD v2 GPL V3) lack tests entirely; SHD additionally uses `print()` + `exit()` for errors, making it unsuitable as a library API. Clean-slate rewrite using httpx + pydantic + pandas + numpy, adopting pyhomebroker's modular Facade architecture while dropping the fragile `signalr-client-threads` dependency (deferred to Tier 3).

## Scope

### In Scope (Tier 1 — Must Have)
- **Auth** (`auth/session.py`): `Auth.login(dni, user, password)` POST `/Login/Ingresar`, fallback `/Login/IngresarModal` on HTTP 500, `logout()`, IP capture via `api.ipify.org`, exception-based errors
- **Market Data** (`online/polling.py`): 6 boards (bluechips, general_board, cedears, government_bonds, short_term_government_bonds, corporate_bonds), options, repos, indices/MERVAL, personal portfolio, order book Level 2 — all via HTTP polling to `/Prices/*` endpoints, returns `pd.DataFrame`
- **History** (`history/history.py`): daily (`resolution=D`) + intraday (`resolution=1`) from `/HistoricoPrecios/history` and `/Intradiario/history`, UTC→Argentina time conversion
- **Common** (`common/`): BrokerConfig NamedTuple + `get_broker()` lookup (Gallo, broker_id=0), 4 exception types, DataFrame normalization helpers
- **Testing**: pytest with `--strict-markers`, `--strict-config`, `pytest-cov` (80% target), `pytest-xdist` parallel execution, `pytest-httpx` for HTTP mocking, `tests/unit/` + `tests/integration/`

### Out of Scope
- **Orders module** (Tier 2): buy/sell/cancel — deferred due to financial risk
- **SignalR streaming** (Tier 3): real-time WebSocket — deferred due to fragile dependency
- **Account/portfolio positions** (`proceso: 22/10/91`) — deferred to Tier 2
- **Proxy support** — omitted; no need for BYMA/Gallo proxies
- **Async support** — synchronous-only for v1

## ADR: Modular Facade Architecture

**Status**: Accepted. **Context**: pyhomebroker uses a clean Facade pattern — `HomeBroker` delegates to `HomeBrokerSession`, `Online`, `History`, `Orders` — with proper exceptions and injectable sessions. SHD is monolithic with `print()`+`exit()` and 17-line header dicts copy-pasted across 10+ methods. **Decision**: Adopt pyhomebroker's modular structure: `HBD` facade (`src/hbd/__init__.py`) composing `Auth`, `Online` (polling-only), `History`, and `Common` infrastructure. Transport via httpx (enables `MockTransport` and `pytest-httpx` for clean testability). Pydantic for typed response models. Exception-based error handling throughout; no `exit()` calls. **Consequences**: Clean sub-modules, easy to test/extend, no GPL V3 license contamination.

## API Surface

```python
from hbd import HBD

broker = HBD(broker=0, dni="12345678", user="user", password="pass")
broker.auth.login()
bolsas = broker.online.get_securities("bluechips", "spot")
historico = broker.history.get_daily_history("GGAL", "2024-01-01", "2024-01-31")
portafolio = broker.online.get_personal_portfolio()
broker.auth.logout()
```

## Capabilities

### New Capabilities
- `auth-session`: Authentication session management (login, logout, IP capture, cookie handling, fallback login on HTTP 500)
- `market-data-polling`: HTTP polling market data — 6 boards, options, repos, indices, personal portfolio, Level 2 order book — returning normalized DataFrames
- `historical-data`: Daily and intraday historical price data with UTC→Argentina time conversion
- `common-infrastructure`: Broker configuration lookup, exception hierarchy, DataFrame normalization utilities

### Modified Capabilities
None — greenfield project, no existing specs to modify.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/hbd/__init__.py` | New | Facade entry point `HBD` composing sub-modules |
| `src/hbd/auth/session.py` | New | Auth class: login/logout, cookie/IP management |
| `src/hbd/online/polling.py` | New | Online class: HTTP polling for all market data |
| `src/hbd/history/history.py` | New | History class: daily + intraday data |
| `src/hbd/common/` | New | `brokers.py`, `exceptions.py`, `helpers.py` |
| `tests/unit/`, `tests/integration/` | New | Test suite for all Tier 1 modules |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| License contamination (SHD GPL V3) | Low | Clean-slate; only API patterns adopted, no code copied |
| Orders deferred (financial risk) | N/A | Explicitly excluded from Tier 1 |
| `pytest-httpx` not installed in venv | Medium | Add to `pyproject.toml` dev dependencies before apply phase |
| Intraday history endpoint availability | Uncertain | Must verify BYMA `/Intradiario/history` returns data in testing |
| Column naming convention | Medium | Product question — Spanish abbreviations vs English |

## Rollback Plan

1. Remove affected modules under `src/hbd/{auth/,online/,history/,common/}`
2. Remove corresponding test files under `tests/`
3. Revert `pyproject.toml` dependency changes
4. No persistent state — auth/logout are runtime-only (cookies in memory)

## Dependencies

- **httpx** — transport layer + HTTP mocking (`MockTransport`/`pytest-httpx`)
- **pydantic** — typed response models
- **pandas** — DataFrame return types
- **numpy** — numeric processing in helpers
- **pytest-httpx** — HTTP mocking (NOT yet installed — must add to dev deps)

## Success Criteria

- [ ] ≥80% test coverage on `src/hbd/` via `pytest --cov`
- [ ] All 6 market data boards return normalized DataFrames
- [ ] Auth login/logout cycle tested with mock HTTP
- [ ] Historical data returns DataFrames with date/open/high/low/close/volume
- [ ] Strict exception-based error handling (no `exit()` calls)
- [ ] `--strict-markers` and `--strict-config` pass
- [ ] Tests run in parallel via `pytest-xdist`

## Open Questions (Product — Answer Before Spec Phase)

1. **Broker list**: Start with ONLY Gallo (broker_id=0, public/demo) or include all 16 brokers from pyhomebroker?
2. **Column naming**: pyhomebroker uses Spanish abbreviations (`PREC`, `VOLU`, `TICK`). Use those or English column names (`price`, `volume`, `close`)?
3. **Error handling**: Should `Auth.login()` raise an exception on failure (strict) or return `False`/`None`?
4. **Return type**: Strictly `pd.DataFrame` or support optional `dict` return for lightweight use?
5. **Async**: Plan for async support in v1 or stay synchronous-only?
6. **Intraday history**: Does BYMA/Gallo provide intraday data via the same `/Intradiario/history` endpoint as pyhomebroker?
