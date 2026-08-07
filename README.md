# homebroker-data — Modern Python Client for BYMA

Apache 2.0 | Python 3.12+ | Strict TDD

Modern Python client for the BYMA Home Broker platform (Argentine stock brokers).
Built with strict TDD, type safety, and a modular facade architecture.

> **Status**: Alpha — under active development with strict TDD.

## Quick Start

```bash
# Development setup
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest
```

## Install

```bash
pip install homebroker-data
```

## Usage

```python
from homebroker_data import HomeBroker

hb = HomeBroker(broker=0, dni="12345678", user="user", password="pass")
hb.auth.login()

data = hb.online.get_securities("bluechips", "spot")
history = hb.history.get_daily_history("GGAL", "2024-01-01", "2024-01-31")

hb.auth.logout()
```

## License

Apache-2.0
