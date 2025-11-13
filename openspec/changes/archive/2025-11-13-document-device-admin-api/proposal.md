# 变更：document-device-admin-api

## Why
- `/v1/device-admin/macs`（增、查、改）是后台管理端创建/管理设备的主接口，但缺少前端可读的官方文档。
- 请求/响应结构、必填字段、冲突与未找到等错误码只有代码可查，影响前端/QA 对接效率。
- 设备运维团队需要统一文档以支撑后台管理界面开发，与现有的 `/v1/devices`、`/v1/auth/login` 文档保持一致。

## What Changes
- 在 `docs/api/` 下新增设备管理 API 文档，说明 `POST /v1/device-admin/macs`、`GET /v1/device-admin/macs`、`PATCH /v1/device-admin/macs/{mac}` 的请求/响应、字段含义、示例。
- 覆盖错误码（`DEVICE_CONFLICT`、`DEVICE_NOT_FOUND`、`UNAUTHORIZED` 等）、MAC 大小写规则、JWT 认证要求。
- 在 README 或 docs 索引中添加链接，方便前端快速定位。

## Impact
- 纯文档更新，不影响运行逻辑；但能减少联调沟通并作为回归依据。
- 后续如扩展删除或批量导入，可在同文档增量更新。
