## ADDED Requirements

### Requirement: Device admin APIs MUST use Django Ninja stack
All endpoints previously implemented via FastAPI (`apps/api/routes/devices.py`) MUST be reimplemented with `ninja.Router`, `JWTAuth`, `ApiError`, and `observe_device_api` so they share the same auth/telemetry contract as `device_api`.

#### Scenario: Router uses shared middleware
- **GIVEN** a request hits `/v1/device-admin/macs`
- **WHEN** code handles create/list/update
- **THEN** the view is protected by `JWTAuth`, errors propagate through `ApiError`, and metrics log via `observe_device_api`

### Requirement: Create/List/Update MUST reuse repository + schemas
Device CRUD APIs MUST delegate to `DeviceRepository` and return the existing `DeviceResponse` / `DeviceListResponse` schemas so clients receive consistent payloads.

#### Scenario: Create device with unique MAC
- **WHEN** caller POSTs a new MAC
- **THEN** repository `create_device` is invoked, `subscription_manager.apply_device` runs, and the response body equals `DeviceResponse.from_model(...)`

#### Scenario: Conflict handled gracefully
- **WHEN** MAC already exists
- **THEN** API raises `ApiError("DEVICE_CONFLICT", ..., 409)` (exact code TBD) using unified error schema rather than FastAPI `HTTPException`

#### Scenario: List devices filtered by status
- **WHEN** GET `/macs?status=enabled`
- **THEN** repository `list_devices(status=...)` result is mapped to `DeviceListResponse`, preserving `total`

#### Scenario: Update device applies subscription change
- **WHEN** PATCH `/macs/{mac}` succeeds
- **THEN** repository `update_device` result is returned via schema and `subscription_manager.apply_device` is called

### Requirement: Django tests MUST cover new routes
Automated tests MUST live under `apps/api/routes/tests/` and exercise happy paths plus 401/404/409 branches for the device admin router.

#### Scenario: Create/list/update tests
- **GIVEN** JWT helper + repo fixtures
- **WHEN** tests hit the new Ninja endpoints
- **THEN** they assert schema payloads, subscription manager invocation (can be patched), and error codes for conflict/not-found/unauthorized cases
