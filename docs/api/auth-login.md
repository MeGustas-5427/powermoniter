# `/v1/auth/login`

提供给前端和第三方客户端的登录 API。通过用户名/密码验证，返回 JWT 访问令牌以及基本用户信息。

## 基本信息

| 项目 | 说明 |
| --- | --- |
| Method | `POST` |
| URL | `/v1/auth/login` |
| Content-Type | `application/json` |
| 认证 | 不需要（此接口用于获取令牌） |

## 请求体

```jsonc
{
  "username": "string (1~64 chars)",
  "password": "string (6~128 chars)"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 用户名（区分大小写），当前为账号登录名 |
| `password` | string | 是 | 用户密码 |

## 成功响应

HTTP 200，body 对应 `LoginResponse`：

```jsonc
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_at": "2025-01-01T12:00:00Z",
    "user": {
      "user_id": "019A7827-DA4B-7C8F-A729-6B5F5F17C303",
      "username": "alice",
      "last_login_at": "2024-12-31T11:30:00Z"
    }
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `token` | string | JWT 访问令牌，算法 `HS256`，有效期 30 天（`ACCESS_TOKEN_EXPIRES`） |
| `expires_at` | string | 令牌过期时间，UTC ISO8601，固定 `Z` 结尾 |
| `user.user_id` | string | 用户 UUID |
| `user.username` | string | 登录账户名 |
| `user.last_login_at` | string | 上次成功登录时间（UTC ISO8601）。若首次登录，则为 “当前时间 - 30 天” |

## 错误响应

| error_code | HTTP | 说明 |
| --- | --- | --- |
| `ACCOUNT_LOCKED` | 401 | 连续输错密码达到 3 次后账户会锁定 15 分钟；15 分钟冷却期内均返回该错误 |
| `UNAUTHORIZED` | 401 | 用户不存在或密码错误 |
| `INTERNAL_ERROR` | 500 | 未预期的服务器异常，通常不会出现，遇到请联系后端排查 |

错误响应格式统一为：

```jsonc
{
  "success": false,
  "error_code": "ACCOUNT_LOCKED",
  "message": "account locked, retry after 15 minutes"
}
```

## 调用示例

### cURL

```bash
curl -X POST https://api.example.com/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret123"}'
```

### JavaScript (fetch)

```ts
async function login(username, password) {
  const resp = await fetch("/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(`${err.error_code}: ${err.message}`);
  }

  const { data } = await resp.json();
  localStorage.setItem("auth_token", data.token);
  return data;
}
```

## 额外说明

- **时区**：所有时间均为 UTC，格式 `YYYY-MM-DDThh:mm:ssZ`。
- **账号锁定策略**：同一账号 15 分钟内连续输错 ≥3 次即锁定；等冷却结束后可再次尝试。
- **令牌**：`token` 需要在后续受保护接口的 `Authorization: Bearer <token>` 头中使用。
