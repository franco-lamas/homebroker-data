"""Unit tests for the HomeBroker facade — Phase 2 T2.5.

Verifies that HomeBroker:
    * resolves the broker via get_broker() (rejects unknown brokers)
    * creates or accepts a shared httpx.Client
    * injects that same client into Auth
"""

from __future__ import annotations

import httpx
import pytest

from homebroker_data.auth import Auth
from homebroker_data.client import HomeBroker
from homebroker_data.common import BrokerNotSupportedException


class TestHomeBrokerFacade:
    """Strict TDD T2.5: HomeBroker facade + client injection."""

    def test_homebroker_injects_shared_client(self):
        """HomeBroker must pass the SAME httpx.Client instance to Auth."""
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, text="<html></html>")
        )
        client = httpx.Client(
            base_url="https://operarhb.bavsa.com",
            transport=transport,
            follow_redirects=True,
        )

        broker = HomeBroker(
            broker=12, dni="12345678", user="testuser", password="testpass",
            client=client,
        )

        assert isinstance(broker.auth, Auth)
        assert broker.auth._client is client

    def test_homebroker_unknown_broker_raises(self):
        """Unknown broker_id must raise BrokerNotSupportedException at construction."""
        with pytest.raises(BrokerNotSupportedException):
            HomeBroker(
                broker=999, dni="12345678", user="testuser",
                password="testpass",
            )

    def test_homebroker_creates_client_when_none_provided(self):
        """HomeBroker must create its own client with proper base_url when none injected."""
        broker = HomeBroker(
            broker=12, dni="12345678", user="testuser",
            password="testpass",
        )
        # Verify client is created with broker's page as base_url
        assert broker.client.base_url == "https://operarhb.bavsa.com"
        assert broker.auth._client is broker.client

    def test_homebroker_auth_property_returns_auth(self):
        """The .auth property must return the Auth instance."""
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, text="<html></html>")
        )
        client = httpx.Client(
            base_url="https://operarhb.bavsa.com",
            transport=transport,
            follow_redirects=True,
        )
        broker = HomeBroker(
            broker=12, dni="12345678", user="testuser", password="testpass",
            client=client,
        )
        assert broker.auth._client is client
