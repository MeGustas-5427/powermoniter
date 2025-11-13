## ADDED Requirements

### Requirement: Auth routes MUST use Ninja stack
The `/auth/login` endpoint MUST be implemented with `ninja.Router`, integrated into the global `NinjaAPI`, and return the existing `LoginResponse` schema.

#### Scenario: Router registration
- **WHEN** clients POST `/v1/auth/login`
- **THEN** the request is handled by a Ninja router (not FastAPI), and the response body matches `LoginResponse`

### Requirement: Login errors MUST use ApiError + metrics
Account lock and invalid credential branches MUST raise `ApiError` with codes `ACCOUNT_LOCKED` / `UNAUTHORIZED`, and the handler MUST emit `observe_device_api("auth_login", ...)` telemetry.

#### Scenario: Account locked
- **WHEN** `AuthService.login` raises `AccountLockedError`
- **THEN** the API returns 401 with `error_code="ACCOUNT_LOCKED"`, and metrics log the failure with the same label

#### Scenario: Invalid credentials
- **WHEN** credentials are wrong
- **THEN** the API responds with 401 `UNAUTHORIZED`, and metrics capture the failure

### Requirement: Django tests MUST cover login outcomes
Automated tests MUST live under `apps/api/routes/tests/` and cover success, account locked, invalid credentials, and unexpected error branches via mocks.

#### Scenario: Login success test
- **WHEN** AuthService is mocked to return a valid token
- **THEN** the test asserts status 200, `success=true`, and ISO8601 timestamps

#### Scenario: Error tests
- **WHEN** AuthService raises `AccountLockedError` or `InvalidCredentialsError`
- **THEN** tests assert 401 with the correct `error_code`
