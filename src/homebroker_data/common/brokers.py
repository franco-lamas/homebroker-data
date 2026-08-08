"""Broker configuration for the HBD client.

Provides the 17 broker definitions supported by the BYMA/HomeBroker platform
and a lookup function :func:`get_broker` that returns the matching
:class:`BrokerConfig`.

Spec ref: common-infrastructure spec §"Broker Configuration", req #1, #2.
"""

from __future__ import annotations

from typing import TypedDict

from .exceptions import BrokerNotSupportedException


class BrokerConfig(TypedDict):
    """Structured configuration for a single BYMA broker."""

    broker_id: int
    name: str
    page: str


BROKERS: list[BrokerConfig] = [
    {"broker_id": 12, "name": "Buenos Aires Valores S.A.", "page": "https://operarhb.bavsa.com"},
    {"broker_id": 20, "name": "Proficio Investment S.A.", "page": "https://newsystem.proficioinvestment.com.ar"},
    {"broker_id": 81, "name": "Tomar Inversiones S.A", "page": "https://clientes2.tminversiones.com.ar"},
    {"broker_id": 88, "name": "Bell Investments S.A.", "page": "https://operar.bellbursatil.com"},
    {"broker_id": 91, "name": "RIG Valores S.A.", "page": "https://rigvaloresweb.com/"},
    {"broker_id": 94, "name": "Soluciones Financieras S.A.", "page": "https://sistemag.solfin.com.ar"},
    {"broker_id": 122, "name": "Industrial Valores S.A.", "page": "https://inversiones.bind.com.ar/Clientes"},
    {"broker_id": 127, "name": "Maestro y Huerres S.A", "page": "https://operar.maestroyhuerres.com"},
    {"broker_id": 153, "name": "Bolsa de Comercio del Chaco", "page": "https://clientes.bcch.org.ar"},
    {"broker_id": 163, "name": "Prosecurities S.A.", "page": "http://operar.psec.com.ar"},
    {"broker_id": 186, "name": "Servente y Cia. S.A.", "page": "http://clientes.serventeycia.com"},
    {"broker_id": 201, "name": "Alfy Inversiones S.A.", "page": "https://acceso.alfyinversiones.com.ar"},
    {"broker_id": 203, "name": "Invertir en Bolsa S.A.", "page": "https://clientesv2.invertirenbolsa.com.ar"},
    {"broker_id": 209, "name": "Futuro Bursátil S.A.", "page": "https://homebroker.futurobursatil.com.ar"},
    {"broker_id": 233, "name": "Sailing S.A.", "page": "https://login.sailinginversiones.com"},
    {"broker_id": 265, "name": "Negocios Financieros y Bursátiles", "page": "https://cocoscap.com"},
    {"broker_id": 284, "name": "Veta Capital S.A.", "page": "http://cuentas.vetacapital.com.ar"},
]

# Pre-compute the set of supported IDs for O(1) lookup and error messages.
_SUPPORTED_IDS: list[int] = [b["broker_id"] for b in BROKERS]


def get_broker(broker_id: int) -> BrokerConfig:
    """Return the :class:`BrokerConfig` for *broker_id*.

    Raises:
        BrokerNotSupportedException: If *broker_id* is not one of the 17
            supported brokers.  The exception message lists the supported IDs.
    """
    for broker in BROKERS:
        if broker["broker_id"] == broker_id:
            return broker
    raise BrokerNotSupportedException(
        f"Broker '{broker_id}' is not supported. "
        f"Supported broker IDs: {_SUPPORTED_IDS}"
    )
