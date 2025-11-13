## 1. 方案与接口对齐
- [x] 1.1 阅读旧 FastAPI 路由、`DeviceRepository`、`DeviceResponse` schema，确认字段与业务规则。
- [x] 1.2 确认新的 URL 前缀、认证策略（JWTAuth）、错误码与 `observe_device_api` 标签，更新方案记录。

## 2. 路由改写
- [x] 2.1 使用 `ninja.Router` + `JWTAuth` 重写 create/list/update 端点，复用 `ApiError`，返回统一 schema。
- [x] 2.2 将路由注册到 `powermoniter/urls.py`（或集中入口），并删除 FastAPI `APIRouter` 依赖。
- [x] 2.3 在实现中复用 `DeviceRepository`/`subscription_manager`，保证行为与旧路由一致。

## 3. 测试与验证
- [x] 3.1 为新路由编写 Django 测试（成功/冲突/未找到/未授权），使用现有 helper。
- [x] 3.2 运行 `python manage.py test apps.api.routes.tests.test_devices_admin`（或同类）并记录结果。
- [x] 3.3 更新文档/README 或 PR 描述，说明接口迁移与测试覆盖。
