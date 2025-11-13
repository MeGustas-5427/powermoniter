# 变更：document-auth-api

## Why
- 前端需要可阅读的 `/v1/auth/login` API 文档来对接登录页，但当前仓库没有针对该路由的公共说明。
- 登录接口的请求/响应字段、错误码（`ACCOUNT_LOCKED`、`UNAUTHORIZED`）以及节流说明仅在代码中体现，缺少统一文档，易造成集成偏差。
- 近期 `auth` 路由已经迁移到 Django Ninja 栈，需要同步文档确保各端一致。

## What Changes
- 编写一份供前端使用的 API 文档（建议 `docs/api/auth-login.md`），详细描述请求 URL、方法、请求体/返回体结构、示例以及错误码语义。
- 在文档中补充调用示例（cURL/JavaScript fetch）、时间字段格式（UTC ISO8601）与账号锁定策略说明。
- 将文档加入 README 或 docs 索引，方便前端/QA 查阅。

## Impact
- 仅新增文档，不影响后端逻辑；但会让前后端协作更顺畅。
- 需要保持文档随代码演进更新，后续登录扩展（例如多因子）就有参考基线。
