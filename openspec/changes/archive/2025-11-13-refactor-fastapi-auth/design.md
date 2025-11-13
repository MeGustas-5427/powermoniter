## 设计补充

- Router：`router = Router(tags=["Auth"])`，挂载到 `api.add_router("/v1/auth", auth_router)`，与现有 `JWTAuth` 解耦（登录本身不需要 auth，但可共享 `ApiError`）。
- 错误处理：`AccountLockedError` → `ApiError("ACCOUNT_LOCKED", ..., 401)`；`InvalidCredentialsError` → `ApiError("UNAUTHORIZED", ..., 401)`；其余异常映射为 `INTERNAL_ERROR`。
- 指标：使用 `observe_device_api("auth_login", status_label, duration)`，记录成功/失败次数。
- Schema：继续返回 `LoginResponse`，其中 `expires_at`/`last_login_at` 使用 UTC ISO8601。
- 测试：使用 Django `Client` + `override_settings(ROOT_URLCONF=...)`，通过 `patch("apps.api.routes.auth.AuthService.login", ...)` mock 结果，验证 status code/JSON。
