# 变更：add-device-api-tests

## Why
- `apps/api/routes/device_api.py` 的 `list_devices` 是仪表盘加载设备列表的入口，目前缺少 Django 自带测试模块（`django.test`）的覆盖，无法防止分页或状态过滤回归。
- 认证/过滤逻辑由 Ninja +自定义 JWT 组合完成，错误场景没有契约文档也没有回归测试，排障成本高。
- QA 团队需要一份可追溯的测试用例规范，明确哪些行为必须由自动化测试守护。

## What Changes
- 为 `list_devices` API 制定测试用例规范，覆盖成功分页、状态过滤、无数据、鉴权失败以及参数越界等场景。
- 使用 Django 原生 `TestCase/AsyncClient` 编写对应的单元测试文件（建议放在 `apps/api/routes/tests/test_device_api_list.py`），复用 ORM 模型构造设备/读数组合。
- 提供辅助方法快速生成有效 JWT，减少重复样板代码，并保证测试可并行运行。

## Impact
- 引入新的测试模块与数据夹具，不影响生产逻辑；但会要求 CI 在变更时运行 Django 测试套件。
- 需要准备最小化的设备/读数种子数据，可能需要在测试中 mock `DeviceApiService._now()` 以保证可预测性。
