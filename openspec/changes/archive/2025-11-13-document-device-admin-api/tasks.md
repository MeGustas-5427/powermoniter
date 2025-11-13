## 1. 信息收集
- [x] 1.1 阅读 `apps/api/routes/devices.py`、`apps/schemas/devices.py`、`DeviceRepository`，梳理 create/list/update 的字段、认证、错误码。
- [x] 1.2 记录 MAC 正规化规则、`ingress_config` 要求、以及订阅同步行为说明。

## 2. 文档撰写
- [x] 2.1 在 `docs/api/device-admin.md` 分章节说明 `POST /v1/device-admin/macs`、`GET /v1/device-admin/macs`、`PATCH /v1/device-admin/macs/{mac}`。
- [x] 2.2 为每个接口提供请求/响应 JSON、字段说明，并展示正确的 JWT Header。
- [x] 2.3 列出错误码表（`DEVICE_CONFLICT`、`DEVICE_NOT_FOUND`、`UNAUTHORIZED`、`INTERNAL_ERROR` 等）及触发场景。

## 3. 校验 & 引用
- [x] 3.1 自查文档内容与实现一致（MAC 大小写、字段类型、示例值）。
- [x] 3.2 在 README/docs 索引增加链接，并在 PR 备注中引用文档路径。
