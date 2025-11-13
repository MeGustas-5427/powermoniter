# auth Specification

## Purpose
TBD - created by archiving change refactor-fastapi-auth. Update Purpose after archive.
## Requirements
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

### Requirement: Document `/v1/auth/login` request/response contract
Documentation MUST describe the login endpoint URL, HTTP method, request body fields (`username`, `password`), and the success payload (`token`, `expires_at`, `user` block).

#### Scenario: Front-end developer reads doc
- **WHEN** a developer opens `docs/api/auth-login.md`
- **THEN** they see HTTP method/URL, JSON schema/field types, and an example request/response that matches `LoginRequest`/`LoginResponse`

### Requirement: Error codes table MUST be included
Docs MUST list possible error codes (`ACCOUNT_LOCKED`, `UNAUTHORIZED`, `INTERNAL_ERROR`) with HTTP status and explanation (e.g.,锁定时间、凭证错误).

#### Scenario: QA reviews failure handling
- **WHEN** QA checks the doc
- **THEN** they find a table or section detailing each error code、对应状态码、触发条件

### Requirement: Provide sample code snippets
Docs MUST include at least one cURL sample and one JavaScript fetch/axios示例，展示如何发送请求并处理响应。

#### Scenario: Front-end copy-pastes example
- **WHEN** FE copy-pastes the JS snippet
- **THEN** the snippet shows headers (`Content-Type: application/json`)、body结构以及如何解析 `token`/`expires_at`

