# 变更：document-device-api

## Why
- `/v1/devices` 与 `/v1/devices/{device_id}/electricity` 是前端仪表盘的核心接口，但目前缺少可供前端/QA 查阅的官方文档。
- 请求参数（分页、状态过滤、时间窗口）以及错误码（`DEVICE_NOT_FOUND`、`INVALID_TIME_RANGE`）只能从代码推断，导致对接沟通成本高。
- 既有 `auth` 文档已补充，需要继续完善设备相关 API，以建立统一文档体系。

## What Changes
- 编写 `docs/api/device-api.md`，覆盖设备列表和电量曲线两个接口：请求方法/URL、Query 参数、响应结构、字段类型、示例。
- 列出所有可能的错误码（如 `UNAUTHORIZED`、`DEVICE_NOT_FOUND`、`INVALID_TIME_RANGE`）及含义。
- 提供 cURL/JS 示例（含分页、状态过滤、window 参数），并说明 JWT Bearer 头的使用。

## Impact
- 纯文档变更，不影响运行时逻辑；但前端可以直接参考，减少沟通。
- 后续新增筛选项或时间窗口时，可在该文档基础上增量更新。
