进一步方案细化：

- URL 计划：将新 router 注册为 `api.add_router("/v1/device-admin", devices_admin_router)`，并与 `powermoniter/urls.py` 中的 NinjaAPI 共享 `JWTAuth`/`ApiError`。
- 认证：沿用 `router = Router(tags=["Device Admin"], auth=JWTAuth())`，内部 `_require_auth` 可复用 `device_api` 的 helper 或在 router 顶层依赖 `request.auth`。
- 错误码：新增 `DEVICE_CONFLICT`（409）、`DEVICE_NOT_FOUND`（404）等，全部通过 `ApiError` 抛出，避免 FastAPI `HTTPException`。
- 遥测：参考 `device_api`，在 create/list/update 函数 `try/finally` 中调用 `observe_device_api("device_admin_create", status_label, duration, points=None)` 之类的指标。
- 依赖注入：`DeviceRepository` 和 `subscription_manager` 通过模块级实例获取，不再依赖 FastAPI `Depends`；若需要，可保留一个 `get_repository()` 帮助函数，直接返回类实例。
- Schema：继续使用 `apps.schemas.devices` 中的 Pydantic `Schema`，因为 Ninja 能直接返回它们；确保 `DeviceListResponse` 的 `page/page_size` 语义一致（可默认单页返回）。
