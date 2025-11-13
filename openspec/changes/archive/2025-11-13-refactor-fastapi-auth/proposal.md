# 变更：refactor-fastapi-auth

## Why
- `apps/api/routes/auth.py` 仍保留 FastAPI `APIRouter` + `HTTPException` 风格，无法复用 Django Ninja 的 `Router`、`ApiError` 和统一日志/指标。
- 登录 API 输出 `JsonResponse`，与其他 Ninja API 的返回结构、异常处理、鉴权策略不一致，难以共享测试 helper 和全局中间件。
- 现有路由绕过 `apps.api.errors`，导致监控无法通过 `observe_device_api` 捕捉登录耗时与失败原因。

## What Changes
- 将 `/auth/login` 改写为 Ninja `Router`，沿用 `ApiError` 和 `observe_device_api`，并保持响应 schema (`LoginResponse`)。
- 统一错误码语义（如 `ACCOUNT_LOCKED`、`UNAUTHORIZED`）并在 `finally` 中记录指标，确保异常由 `ApiError` 处理器接管。
- 补充 Django 测试覆盖登录成功、账号锁定、凭证错误等场景，复用认证/时间 helper。

## Impact
- FastAPI 依赖彻底移除，所有 API 都挂在 `NinjaAPI` 下，易于维护。
- Auth 模块日志/监控与其他路由一致，可在 Prometheus 中看到 login 成功率。
- 新增测试确保登录行为稳定，也便于将来的多因素/速率限制扩展。
