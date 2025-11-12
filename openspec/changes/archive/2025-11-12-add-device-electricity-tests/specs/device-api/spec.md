## ADDED Requirements

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
