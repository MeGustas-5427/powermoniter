# 变更：add-device-electricity-tests

## Why
- `/v1/devices/{device_id}/electricity` 是仪表盘展示 24h/7d/30d 曲线的唯一入口，目前缺少 Django 自带测试覆盖，无法确保窗口配置、桶粒度和序列排序不被回归。
- 错误分支（设备不存在、非法时间窗口、鉴权缺失）只在业务代码里定义，没有自动化测试锁定响应格式与错误码。
- QA 需要一份“get_device_electricity”测试用例规范，以便验收时对照执行。

## What Changes
- 设计一套 Django `TestCase/AsyncClient` 测试规范，覆盖成功窗口（24h/7d/30d）以及 `DeviceNotFoundError`、`InvalidTimeRangeError`、鉴权失败等路径。
- 在 `apps/api/routes/tests/` 下新增测试文件，构建最小 ORM 夹具（用户、设备、读数）并 mock `DeviceApiService._now()`，从而验证时间区间、interval label、point 排序等字段。
- 记录可复用的 JWT/时间助手，让后续 API 测试共享同一工具。

## Impact
- 仅新增测试与规范，不改变生产逻辑； CI 需运行新增的 Django 用例。
- 可能需要引入 PostgreSQL/SQLite 兼容的读数夹具以及 patch `_aggregate_buckets_postgres`/`_now`，以保持测试稳定。
