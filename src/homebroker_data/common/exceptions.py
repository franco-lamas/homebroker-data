"""Exception hierarchy for the HBD (HomeBroker Data) client.

All library errors derive from a single :class:`HBDException` base so callers
can catch any HBD-related failure with one ``except`` clause while still
distinguishing between session, broker, server, and data problems.

Spec ref: common-infrastructure spec §"Error Handling", req #3.
"""

from __future__ import annotations


class HBDException(Exception):
    """Base exception for all HBD client errors.

    Every domain-specific exception inherits from this class so that
    ``except HBDException`` catches every HBD failure.
    """


class SessionException(HBDException):
    """Raised when an authenticated session is required but not active."""


class BrokerNotSupportedException(HBDException):
    """Raised when a broker ID is not in the supported broker list."""


class ServerException(HBDException):
    """Raised on HTTP transport errors or 5xx server responses."""


class DataException(HBDException):
    """Raised when API response data is invalid, malformed, or incomplete."""
