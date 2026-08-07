# HBD Specifications

Source of truth for the HBD (HomeBroker Data) Python client specification. Each spec defines the full behavior of one capability domain.

## Spec Registry

| Spec | Domain | Status | Source File |
|------|--------|--------|-------------|
| [auth-session](auth-session/spec.md) | Session management | Active | `src/hbd/auth/session.py` |
| [market-data-polling](market-data-polling/spec.md) | Market data via HTTP polling | Active | `src/hbd/online/polling.py` |
| [historical-data](historical-data/spec.md) | Daily historical prices | Active | `src/hbd/history/history.py` |
| [common-infrastructure](common-infrastructure/spec.md) | Brokers, exceptions, helpers | Active | `src/hbd/common/` |

## Conventions

- **Column names**: English only (`price`, `volume`, `close`, `open`, `high`, `low`, `settlement`, `currency`, `date`, `symbol`)
- **Settlements**: `spot`→`1`, `24hs`→`2`; `48hs` is deprecated and not supported
- **Errors**: Strict exceptions — no `False`/`None` returns, no `print()`/`exit()`
- **Returns**: Always `pd.DataFrame` for data methods
- **Synchronous only**: No async in Tier 1
- **RFC 2119 keywords**: MUST, SHALL, SHOULD, MAY
- **Scenarios**: Given/When/Then format, testably executable

## Related Artifacts

| Artifact | Path |
|----------|------|
| Change proposal | `openspec/changes/hbd-initial-client/proposal.md` |
| Exploration | `openspec/changes/hbd-initial-client/exploration.md` |
| Config | `openspec/config.yaml` |
