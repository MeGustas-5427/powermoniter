## 1. 方案确认
- [x] 1.1 阅读 FastAPI 登录路由、`AuthService`、`Login*` schemas，明确字段与错误分支。
- [x] 1.2 设计 Ninja 版 `/auth/login`：router 前缀、`ApiError` 映射、`observe_device_api` 指标标签。

## 2. 路由改写
- [x] 2.1 使用 `ninja.Router` 重写登录端点，保留返回 schema，使用 `ApiError` 处理异常。
- [x] 2.2 在逻辑 `finally` 中记录 `observe_device_api("auth_login", ...)` 指标。
- [x] 2.3 在 `powermoniter/urls.py` 中挂载新 router，并删除 FastAPI 依赖。

## 3. 测试与验证
- [x] 3.1 编写 Django 测试覆盖登录成功、账号锁定、凭证错误等场景，mock `AuthService`.
- [x] 3.2 运行 `python manage.py test apps.api.routes.tests.test_auth`（待新增）并通过。
- [x] 3.3 在 PR/文档说明中同步登录 API 迁移细节。
