# Auth Session Specification

## Purpose
Authenticate HBD users with the BYMA broker platform via HTTP form-based login, manage session cookies, capture the public IP, and provide a fallback login path when the primary endpoint returns HTTP 500.

## Scope

**In:**
- Login via `/Login/Ingresar` (form-urlencoded) and fallback `/Login/IngresarModal` (JSON) on HTTP 500
- Public IP capture via `api.ipify.org` on successful login
- Cookie persistence on an `httpx.Client` session
- `is_logged_in` boolean state
- `logout()` clearing all session state
- Broker validation via `get_broker()` before login

**Out:**
- Proxy support (explicitly excluded — Decision #13)
- Async login (sync only — Decision #11)
- Orders or real-time streaming (deferred to Tier 2)

## API

| Method | Signature |
|--------|-----------|
| `login` | `Auth.login(dni: int, user: str, password: str, raise_exception: bool = False) -> bool` |
| `logout` | `Auth.logout() -> None` |
| `is_logged_in` | `Auth.is_logged_in: bool` (read-only property) |
| `ip_address` | `Auth.ip_address: str \| None` (read-only property) |

## Requirements

| # | Requirement | RFC 2119 |
|---|-------------|----------|
| 1 | Pre-fetch the broker page before login to capture session cookies | MUST |
| 2 | POST form data `{IpAddress, Dni, Usuario, Password}` to `/Login/Ingresar` | MUST |
| 3 | On HTTP 500 from primary endpoint, POST JSON to `/Login/IngresarModal` | MUST |
| 4 | Capture public IP from `api.ipify.org/?format=json` and cache it | MUST |
| 5 | Validate login success by checking for `#usuarioLogueado` element in HTML response | MUST |
| 6 | Persist response cookies on the httpx client for subsequent requests | MUST |
| 7 | Set `is_logged_in = True` only on successful validation | MUST |
| 8 | `logout()` clears cookies, `is_logged_in = False`, and resets IP cache | MUST |
| 9 | Validate broker_id via `get_broker()` before login; reject unknown brokers | MUST |

## Scenarios

#### Scenario: Successful login via primary endpoint
- GIVEN a valid broker_id, dni, user, and password
- WHEN the user calls `login()` and the server returns 200 with `#usuarioLogueado` in the HTML
- THEN `is_logged_in` is `True`, cookies are persisted on the client, and the IP is captured

#### Scenario: Fallback login on HTTP 500
- GIVEN the primary login endpoint returns HTTP 500
- WHEN `login()` is called
- THEN the system POSTs to `/Login/IngresarModal` with a JSON payload and validates the response

#### Scenario: Login failure — no usuarioLogueado
- GIVEN valid credentials that the server rejects
- WHEN the response HTML lacks `#usuarioLogueado`
- THEN `SessionException` is raised (if `raise_exception=True`), `is_logged_in` stays `False`

#### Scenario: HTTP transport error
- GIVEN the server is unreachable or returns a 4xx/5xx after fallback
- WHEN `login()` is called with `raise_exception=True`
- THEN `ServerException` is raised

#### Scenario: Logout clears session
- GIVEN the user is logged in with persisted cookies
- WHEN `logout()` is called
- THEN all cookies are cleared and `is_logged_in` is `False`

#### Scenario: Unknown broker
- GIVEN a broker_id not in the 17-broker configuration
- WHEN `login()` is called
- THEN `BrokerNotSupportedException` is raised

## Error Handling

| Condition | Exception |
|-----------|-----------|
| HTTP transport error (4xx/5xx outside fallback) | `ServerException` |
| Response lacks `#usuarioLogueado` | `SessionException` |
| Unknown `broker_id` | `BrokerNotSupportedException` |

## Data Formats

**Login request payload (primary, form-urlencoded):**
| Field | Type |
|-------|------|
| `IpAddress` | str |
| `Dni` | int |
| `Usuario` | str |
| `Password` | str |

**Login request payload (fallback, JSON):** same fields as JSON.

**Login success indicator:** HTML response containing element `#usuarioLogueado`.

**IP response (`api.ipify.org`):** `{ "ip": "1.2.3.4" }`.

## Dependencies

- `common.brokers.get_broker()` — broker config lookup
- `common.exceptions.SessionException`, `BrokerNotSupportedException`, `ServerException`
- `httpx.Client` — transport with cookie jar persistence
- `pyquery` or HTML parser — `#usuarioLogueado` element detection
