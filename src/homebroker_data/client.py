"""HomeBroker facade — single entry point for the HBD client.

Resolves the broker configuration, creates (or accepts) a shared ``httpx.Client``
with cookie persistence, and injects it into the ``Auth`` session manager.
"""

from __future__ import annotations

import httpx

from .auth import Auth
from .common import BrokerConfig, get_broker

__all__ = ["HomeBroker"]


class HomeBroker:
    """Facade that wires together a shared HTTP client and the Auth session.

    Parameters
    ----------
    broker:
        Broker ID (1-284, one of the 17 supported brokers).
    dni:
        User's national document ID.
    user:
        Username on the BYMA platform.
    password:
        User's password.
    client:
        Optional pre-configured ``httpx.Client``.  When *None* a new client
        is created with sensible defaults (base URL, 30 s timeout,
        redirect following, default headers).  This enables ``MockTransport``
        injection in tests.
    """

    def __init__(
        self,
        broker: int,
        dni: str,
        user: str,
        password: str,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._broker_config: BrokerConfig = get_broker(broker)
        self._dni = dni
        self._user = user
        self._password = password

        if client is not None:
            self._client = client
        else:
            self._client = httpx.Client(
                base_url=self._broker_config["page"],
                timeout=30.0,
                follow_redirects=True,
                headers=Auth.DEFAULT_HEADERS,
            )

        self._auth = Auth(self._broker_config, self._client)

    @property
    def auth(self) -> Auth:
        return self._auth

    @property
    def broker_config(self) -> BrokerConfig:
        return self._broker_config

    @property
    def client(self) -> httpx.Client:
        return self._client
