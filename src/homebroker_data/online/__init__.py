"""Online market data module — HTTP polling (Tier 1) + future SignalR (Tier 3)."""

from .snapshot import OnlineSnapshot

__all__ = ["OnlineSnapshot"]
