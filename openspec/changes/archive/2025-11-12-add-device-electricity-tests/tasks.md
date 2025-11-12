## 1. 需求与夹具
- [x] 1.1 复盘 `get_device_electricity` 路由 + `DeviceApiService.get_device_electricity`，确认窗口配置/异常路径。
- [x] 1.2 设计测试夹具：用户、设备、读数、JWT helper、`DeviceApiService._now()` mock 方案，并记录在测试注释中。

## 2. 编写测试
- [x] 2.1 新建 `apps/api/routes/tests/test_device_api_electricity.py`，覆盖 24h/7d/30d 成功返回，断言 interval label、points 序列与时间范围。
- [x] 2.2 为 `DEVICE_NOT_FOUND`、`INVALID_TIME_RANGE`、未授权/缺少 token 编写用例，锁定响应码与结构。
- [x] 2.3 如需 stub `_aggregate_buckets_postgres`，确保不同数据库后端下结果一致，并断言 Prometheus 相关逻辑未破坏响应格式（如可通过 patch）。

## 3. 验证与交付
- [x] 3.1 运行 `python manage.py test apps.api.routes.tests.test_device_api_electricity`，确保测试通过。
- [x] 3.2 在 PR/变更说明中附上“get_device_electricity 测试用例规范”摘要，帮助 QA 对照。
