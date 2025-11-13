## 1. 信息收集
- [x] 1.1 阅读 `apps/api/routes/device_api.py`、`apps/schemas/device_api.py`，梳理请求参数/响应字段与错误码。
- [x] 1.2 确认分页限制（`page`/`page_size`）、`window` 枚举、JWT 认证要求以及错误码语义。

## 2. 文档撰写
- [x] 2.1 在 `docs/api/device-api.md` 描述 `/v1/devices` 的 Query 参数、响应结构和示例。
- [x] 2.2 在同一文档中描述 `/v1/devices/{device_id}/electricity` 的 `device_id`/`window` 参数、返回点位格式、错误码。
- [x] 2.3 添加 cURL 与 JavaScript 示例，展示如何携带 `Authorization: Bearer <token>`、分页/status/filter/window 等参数。

## 3. 校验 & 索引
- [x] 3.1 自查文档内容与实现一致，示例字段/取值正确。
- [x] 3.2 在 README 添加链接，并在 PR 备注中指明文档路径。
