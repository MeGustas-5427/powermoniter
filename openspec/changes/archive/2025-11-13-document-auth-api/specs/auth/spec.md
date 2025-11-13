## ADDED Requirements

### Requirement: Document `/v1/auth/login` request/response contract
Documentation MUST describe the login endpoint URL, HTTP method, request body fields (`username`, `password`), and the success payload (`token`, `expires_at`, `user` block).

#### Scenario: Front-end developer reads doc
- **WHEN** a developer opens `docs/api/auth-login.md`
- **THEN** they see HTTP method/URL, JSON schema/field types, and an example request/response that matches `LoginRequest`/`LoginResponse`

### Requirement: Error codes table MUST be included
Docs MUST list possible error codes (`ACCOUNT_LOCKED`, `UNAUTHORIZED`, `INTERNAL_ERROR`) with HTTP status and explanation (e.g.,锁定时间、凭证错误).

#### Scenario: QA reviews failure handling
- **WHEN** QA checks the doc
- **THEN** they find a table or section detailing each error code、对应状态码、触发条件

### Requirement: Provide sample code snippets
Docs MUST include at least one cURL sample and one JavaScript fetch/axios示例，展示如何发送请求并处理响应。

#### Scenario: Front-end copy-pastes example
- **WHEN** FE copy-pastes the JS snippet
- **THEN** the snippet shows headers (`Content-Type: application/json`)、body结构以及如何解析 `token`/`expires_at`
