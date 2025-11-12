## 1. 梳理需求
- [x] 1.1 复盘 `apps/api/routes/device_api.py` 与 `DeviceApiService.list_devices` 的业务路径，明确需要覆盖的状态。
- [x] 1.2 设计 Django 测试夹具（用户、设备、读数、JWT token）并记录在测试文件注释中。

## 2. 编写测试
- [x] 2.1 新建 `apps/api/routes/tests/test_device_api_list.py`，基于 `django.test.AsyncClient`/`TestCase` 覆盖成功分页（默认/指定 status）、无设备返回空列表等场景。
- [x] 2.2 编写鉴权及参数异常测试：缺失/非法 token、`page_size` 超过 100、`status` 非法值得到 400/422。
- [x] 2.3 视需要 mock `DeviceApiService._now()` 保证 last_seen 相关断言稳定，并断言响应 payload 中的 `status`/`last_seen_at`。

## 3. 验证与文档
- [x] 3.1 运行 `python manage.py test apps.api.routes.tests.test_device_api_list` 并确保通过。
- [x] 3.2 在 PR/变更记录中附带“测试用例规范”小结，方便 QA 对照执行。
