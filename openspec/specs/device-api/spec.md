# device-api Specification

## Purpose
TBD - created by archiving change add-device-api-tests. Update Purpose after archive.
## Requirements
### Requirement: Django TestCase MUST 覆盖 `list_devices` 成功路径
Tests MUST use `django.test.TestCase`（或 `AsyncClient`）为 `/api/device-api` 根路径的 `list_devices` 编写成功路径测试，验证分页、状态过滤与字段格式。

#### Scenario: 分页 + 状态过滤
- **GIVEN** 测试夹具创建 3 台设备（online/offline/maintenance）以及对应的 `Reading` 数据，`DeviceApiService._now()` 被固定
- **WHEN** 通过 `AsyncClient.get("/api/device-api", {"status": "online", "page": 1, "page_size": 2})` 且附带有效 JWT
- **THEN** 响应 `200`，`data.total` 只统计在线设备，返回列表依照名称排序，并携带 `last_seen_at` 的 ISO8601 字符串
- **AND** 默认分页元数据（`page=1`, `page_size=2`）与请求一致

#### Scenario: 无设备返回空列表
- **GIVEN** 当前用户名下没有任何设备
- **WHEN** 发起 GET `/api/device-api`
- **THEN** 返回 `success=true`，`data.items=[]` 且 `total=0`，证明服务端不会抛错

### Requirement: Django Tests MUST 覆盖鉴权与参数异常
All authentication/parameter failure branches MUST be covered by assertions in Django 自带测试模块。

#### Scenario: 缺失/非法 JWT
- **GIVEN** 测试请求缺少 `Authorization: Bearer <token>`
- **WHEN** 调用 `list_devices`
- **THEN** 响应 `401` 且 Ninja 返回 `{"detail": "Unauthorized"}`，测试需要断言该 JSON 结构以锁定鉴权行为

#### Scenario: 超出允许的 page_size
- **GIVEN** 请求 `page_size=200`（超过 `MAX_PAGE_SIZE=100`）
- **WHEN** 发送 GET `/api/device-api`
- **THEN** Ninja 返回 `422` 并包含参数校验错误，测试需断言状态码与报文（至少包含 `"page_size"` 提示）

#### Scenario: 非法 status 参数
- **GIVEN** 查询参数 `status=oops`
- **WHEN** 访问 `list_devices`
- **THEN** 响应 `422`，表明 `DeviceStatusFilter` 的枚举校验生效

### Requirement: Fixtures MUST 记录可复用的 JWT/时间助手
Testing documentation MUST include helpers that生成有效 JWT 和固定当前时间，以保证断言可重复。

#### Scenario: 记录辅助方法
- **GIVEN** 测试文件需要多次构造 JWT 与伪造 “当前时间”
- **WHEN** 在测试类中提供 `_make_token(user_id)` 与 `override_settings`/`mock.patch("DeviceApiService._now")`
- **THEN** 其他测试只需调用助手即可获得一致的 token/时间，测试说明中有注释解释使用方式

### Requirement: Django Tests MUST cover `get_device_electricity` success windows
Tests MUST use Django `TestCase`（或 `AsyncClient`）验证 `/v1/devices/{device_id}/electricity` 在 24h/7d/30d 三种窗口下的响应，确保 interval label、时间范围与 point 顺序正确。

#### Scenario: 24h window returns ordered points
- **GIVEN** 测试夹具创建一台设备及覆盖 24h 的读数，并通过 `mock.patch("apps.api.routes.device_api.DeviceApiService._now")` 固定当前时间
- **WHEN** 认证用户 GET `/v1/devices/{id}/electricity?window=24h`
- **THEN** 响应 `200`，`data.interval="pt5m"`，`data.start_time`/`end_time` 与固定时间差 24 小时
- **AND** `data.points` 依时间排序且包含期望的功率/能耗字段

#### Scenario: 7d/30d windows reuse same helper
- **GIVEN** helper 方法可注入窗口参数并构造读数
- **WHEN** 依次请求 `window=7d` 与 `window=30d`
- **THEN** interval label 分别为 `pt30m` 与 `pt120m`，返回的 `points` 大小与预期桶数一致

### Requirement: Django Tests MUST cover `get_device_electricity` error paths
Automated tests MUST 断言设备不存在、非法窗口与未授权时的响应码和 payload 结构。

#### Scenario: DeviceNotFound yields 404
- **GIVEN** 请求的 `device_id` 不存在或不属于当前用户
- **WHEN** 调用 `/v1/devices/{id}/electricity`
- **THEN** 响应 `404`，`error_code="DEVICE_NOT_FOUND"`，`message` 描述设备无效

#### Scenario: Invalid window yields 400
- **GIVEN** 查询参数 `window=oops`
- **WHEN** 访问 `get_device_electricity`
- **THEN** 响应 `400`，`error_code="INVALID_TIME_RANGE"`

#### Scenario: Missing token yields 401
- **GIVEN** 请求缺少 `Authorization: Bearer <token>`
- **WHEN** 访问 `get_device_electricity`
- **THEN** Ninja 返回 `401` 且 body 为 `{"detail": "Unauthorized"}`

### Requirement: Fixtures MUST document reusable helpers
Test documentation MUST describe helper methods for JWT、固定当前时间以及读数生成，以保证后续用例一致性。

#### Scenario: Document helper utilities
- **GIVEN** 测试文件需要多次构造 token、设备、读数
- **WHEN** 在测试类中提供 `_make_token(user_id)`、`_freeze_now()`、`_create_reading()` 等函数并添加注释
- **THEN** 所有用例都复用这些 helper，保证 token/时间/读数构造逻辑一致，降低重复代码

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

