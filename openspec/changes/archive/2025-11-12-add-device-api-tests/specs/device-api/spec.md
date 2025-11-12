## ADDED Requirements

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
