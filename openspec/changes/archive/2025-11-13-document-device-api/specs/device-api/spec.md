## ADDED Requirements

### Requirement: Document `/v1/devices` endpoint
Documentation MUST describe the list endpoint with URL, method, query parameters (`page`, `page_size`, `status`), and the response schema (`DeviceListResponse`).

#### Scenario: FE reads list API doc
- **WHEN** developer checks `docs/api/device-api.md`
- **THEN** they see pagination rules (default 20, max 100), status filter options (`online/offline/maintenance/all`), sample response with `items/total/page/page_size`

### Requirement: Document `/v1/devices/{device_id}/electricity`
Docs MUST cover the electricity endpoint, including path parameter `device_id`, query `window` options (24h/7d/30d), point structure (`timestamp`, `power_kw`, etc.), and interval labels (`pt5m/pt30m/pt120m`).

#### Scenario: FE implements electricity chart
- **WHEN** FE references doc
- **THEN** they find window choices, explanation of buckets, sample response showing `points` and `interval`

### Requirement: Error codes + auth info
Docs MUST list relevant error codes (`UNAUTHORIZED`, `DEVICE_NOT_FOUND`, `INVALID_TIME_RANGE`, etc.) with HTTP status and meaning, and remind clients to send `Authorization: Bearer <token>` header.

#### Scenario: QA tests failures
- **WHEN** doc is consulted
- **THEN** it presents an error table and mentions JWT requirements so QA can simulate 401/404/400 cases

### Requirement: Provide usage examples
Docs MUST include cURL and JavaScript examples for both endpoints, demonstrating pagination, status filter, window usage, and headers.

#### Scenario: Developer copy-pastes sample
- **WHEN** they copy JS/cURL snippets
- **THEN** requests include `Authorization` header, query params, and parse responses as shown
