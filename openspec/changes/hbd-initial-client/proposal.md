# Proposal: HBD Initial Client — Python 3.12 BYMA Client (Tier 1)

## Intent

Rebuild a modern Python 3.12 BYMA/HomeBroker client as an Apache 2.0-licensed library with strict TDD. Both legacy codebases (pyhomebroker v1 Apache 2.0, SHD v2 GPL V3) lack tests; SHD additionally uses `print()`+`exit()` for errors, making it unsuitable as a library API. Clean-slate rewrite using httpx + pydantic + pandas + numpy, adopting pyhomebroker's modular Facade architecture while dropping the fragile `signalr-client-threads` dependency (deferred to Tier 3).

## Goals & Non-Goals

**Goals (Tier 1 — Must Have)**
- pyhomebroker API-compatible drop-in client (`HBD` → `auth`, `online`, `history`, `common`)
- Strict exception-based error handling (no `print()`/`exit()`)
- Strict TDD: ≥80% coverage, `pytest-httpx` mocking, parallel `pytest-xdist`
- All **16** brokers supported (matching pyhomebroker, incl. Industrial Valores id 122)

**Non-Goals (Tier 2/3 — Deferred)**
- Orders module (buy/sell/cancel) — financial risk
- Real-time SignalR streaming — fragile dependency
- Intraday history — deferred to Tier 2
- Proxy support — not needed for BYMA/Gallo
- Async support — synchronous only

## ADR: Modular Facade + API Compatibility

**Status**: Accepted. **Context**: pyhomebroker uses a clean Facade (`HomeBroker` → `HomeBrokerSession`, `Online`, `History`, `Orders`) with proper exceptions; SHD is monolithic with copy-pasted 17-line headers and `print()`+`exit()`. **Decision**: Adopt pyhomebroker's structure. `HBD` facade composes `Auth`, `Online` (polling-only), `History` (daily), `Common`. httpx transport enables `MockTransport`/`pytest-httpx` for clean testability; pydantic for typed response models; exceptions throughout. License Apache 2.0 — clean-slate, no GPL V3 contamination. **Consequences**: Easy to test/extend; drop-in compatible with pyhomebroker consumers.

## API Surface — pyhomebroker Compatibility Matrix

| Feature | pyhomebroker | HBD | Status |
|---|---|---|---|
| Init | `HomeBroker(broker_id, proxy_url)` | `HBD(broker=0, dni, user, password)` | ✅ |
| Login | `hb.auth.login(dni, user, pass)` | `broker.auth.login()` (lazy) | ✅ |
| Logout | `hb.auth.logout()` | `broker.auth.logout()` | ✅ |
| Securities | `get_securities(board, settlement)` | `get_securities(board, settlement)` | ✅ |
| Options | `get_options()` | `get_options()` | ✅ |
| Repos | `get_repos()` | `get_repos()` | ✅ |
| Portfolio | `get_personal_portfolio()` | `get_personal_portfolio()` | ✅ |
| Order book | `get_order_book(symbol, settl)` | `get_order_book(symbol, settl)` | ✅ |
| Snapshot | `get_market_snapshot()` | `get_market_snapshot()` | ✅ |
| Daily hist | `get_daily_history(sym, f, t)` | `get_daily_history(sym, f, t)` | ✅ |
| Intraday | `get_intraday_history(...)` | — | ❌ Deferred |
| Orders | `hb.orders.*` | — | ❌ Deferred |
| Real-time | `subscribe_*` | — | ❌ Deferred |

Boards: `bluechips`, `general_board`, `cedears`, `government_bonds`, `short_term_government_bonds`, `corporate_bonds`. Settlements: `spot`, `24hs` (`48hs` deprecated — not in use by BYMA as of 2025).

## Column Naming Strategy

Columns will be in **English only** (matching pyhomebroker and SHD legacy):
- `price`, `volume`, `tick`, `date`, `open`, `high`, `low`, `close`, `currency`, `settlement`
- No Spanish abbreviations — clean English column names for consistency across both legacy codebases.

## Testing Strategy

- **Framework**: pytest (9.x), `--strict-markers`, `--strict-config`
- **Coverage**: ≥80% on `src/hbd/` via `pytest-cov`; `tests/unit/` + `tests/integration/`
- **HTTP mocking**: `pytest-httpx` via httpx `MockTransport` — installed in venv, added to `pyproject.toml` dev deps
- **Parallelism**: `pytest-xdist`
- **Quality**: ruff (line 100), mypy strict (python 3.12)

## Capabilities

### New Capabilities
- `auth-session`: login/logout, IP capture via ipify, cookie management, fallback login on HTTP 500
- `market-data-polling`: 6 boards + options + repos + indices/MERVAL + personal portfolio + Level 2 order book via HTTP polling to `/Prices/*` endpoints, normalized DataFrames
- `historical-data`: daily history only from `/HistoricoPrecios/history` (intraday deferred)
- `common-infrastructure`: all 16 broker configs + `get_broker()` lookup, 4-type exception hierarchy, DataFrame numeric normalization helpers

### Modified Capabilities
None — greenfield project, no existing specs to modify.

## Approach

Clean-slate implementation. httpx `Client` at the transport layer enables `MockTransport`/response mocking — no live network in tests. Auth cookies held in-memory on the `Auth` session object; `logout()` clears them.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `src/hbd/__init__.py` | New | `HBD` facade composing sub-modules |
| `src/hbd/auth/session.py` | New | `Auth`: login/logout, IP, cookies, fallback |
| `src/hbd/online/polling.py` | New | `Online`: HTTP polling for all market data |
| `src/hbd/history/history.py` | New | `History`: daily history only |
| `src/hbd/common/` | New | `brokers.py` (16), `exceptions.py`, `helpers.py` |
| `pyproject.toml` | Modified | Added `pytest-httpx>=0.30` to dev deps |
| `tests/unit/`, `tests/integration/` | New | Test suite, mocked HTTP via pytest-httpx |

## Dependencies

- **httpx** — transport layer + HTTP mocking (`MockTransport`/`pytest-httpx`)
- **pydantic** — typed response models
- **pandas** — DataFrame return types
- **numpy** — numeric processing in helpers
- **pytest-httpx** — HTTP mocking (NOT yet installed; must add to dev deps before apply)

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| License contamination (SHD GPL V3) | Low | Clean-slate; only API/endpoint patterns, no code copied |
| `pytest-httpx` not yet installed | Medium | Add to dev deps in apply phase; block merge until tests pass |
| Column aliasing breaks pyhomebroker consumers | Low | Both Spanish + English keys present; aliases are additive |
| Broker endpoint URL drift (16 brokers) | Med | Verify all 16 `page` URLs against pyhomebroker source in spec phase |
| Orders deferred (financial risk) | N/A | Explicitly excluded from Tier 1 |

## Rollback Plan

1. Remove `src/hbd/{auth/,online/,history/,common/}` modules and `tests/unit/`, `tests/integration/`
2. Revert `pyproject.toml` dev-dep additions
3. No persistent state — auth cookies are in-memory only; `logout()` clears them

## Success Criteria

- [ ] ≥80% test coverage on `src/hbd/` via `pytest --cov`
- [ ] All 6 boards + options + repos + MERVAL + portfolio + order book return normalized DataFrames
- [ ] Auth login/logout cycle passes with mock HTTP (pytest-httpx)
- [ ] Daily history returns DataFrame with date/open/high/low/close/volume (+ Spanish aliases)
- [ ] Strict exception-based errors (no `exit()`/`print()`)
- [ ] `--strict-markers` + `--strict-config` pass
- [ ] Tests run in parallel via pytest-xdist

## Resolved Decisions (12 product decisions)

1. **Architecture**: Modular Facade (`HBD` → `Auth`/`Online`/`History`/`Common`) — pyhomebroker compatible
2. **Python**: 3.12+ via uv (isolated from system 3.10)
3. **Strict TDD**: Enabled — `--strict-markers`, `--strict-config`, `--cov=src/hbd`
4. **License**: Apache 2.0 (NOT GPL) — compatible with pyhomebroker, no SHD contamination
5. **Brokers**: ALL 16 from pyhomebroker (incl. Industrial Valores id 122)
6. **Columns**: English only — `price`, `volume`, `close`, … (consistent with both pyhomebroker and SHD)
7. **Errors**: Strict exceptions (no `False`/`None` returns)
8. **Returns**: Strictly `pd.DataFrame` (no dict)
9. **Async**: Synchronous only (v1)
10. **Intraday history**: Excluded from Tier 1 (deferred to Tier 2)
11. **Proxy**: Excluded (not needed for BYMA/Gallo)
12. **Orders**: Deferred to Tier 2 (financial risk)
