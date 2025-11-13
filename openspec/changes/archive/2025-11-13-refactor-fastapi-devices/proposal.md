# 变更：refactor-fastapi-devices

## Why
- `apps/api/routes/devices.py` 仍是 FastAPI/Depends 风格的旧源码，与当前 Django + Ninja 体系（`apps/api/routes/device_api.py`、JWTAuth、统一错误处理）脱节。
- 旧路由未复用 `apps.api.errors.ApiError`、`apps.api.dependencies.security`、`observe_device_api` 指标等模块，导致认证、响应规范、遥测与其他 API 不一致。
- 代码仍直接依赖 FastAPI 的 `APIRouter` 和 `HTTPException`，难以共用 Pydantic Schema、JWT、日志与测试工具链。

## What Changes
- 将 `apps/api/routes/devices.py` 改写为 Django Ninja `Router`，复用 `JWTAuth`、`ApiError`、`DeviceStatusFilter` 等模块，统一认证与错误格式。
- 新路由挂载在 `/v1/device-admin`（可调整），提供 create/list/update 功能，内部调用重用的 repository/service，返回 `DeviceResponse`/`DeviceListResponse` Pydantic schema。
- 为新路由补充 Django 测试用例，覆盖成功路径与冲突/未找到/鉴权失败等错误场景，并使用与 `device_api` 相同的 helper。

## Impact
- FastAPI 依赖被移除，CI/部署只需维护 Django；旧 `APIRouter` 将被弃用。
- 统一的认证/错误/指标逻辑让产品与监控能复用同一工具，减少重复实现。
- 需要调整 `powermoniter/urls.py`（或统一注册点）以挂载新 router，并确保文档/客户端适配。
