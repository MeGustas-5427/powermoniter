# Device Admin API 文档

`/v1/device-admin/macs` 系列接口用于后台创建/查看/更新设备。所有请求均需要携带 `Authorization: Bearer <token>`，token 来源于登录 API。

---

## 1. POST `/v1/device-admin/macs`

### 作用

按 MAC 地址创建新设备，同时触发订阅器同步。

### 请求

| 项 | 描述 |
| --- | --- |
| Method | `POST` |
| URL | `/v1/device-admin/macs` |
| Header | `Authorization: Bearer <token>`、`Content-Type: application/json` |

请求体（`DeviceCreate`）示例：

```jsonc
{
  "mac": "aa0000000001",
  "status": 1,
  "collect_enabled": true,
  "ingress_type": 0,
  "ingress_config": {
    "name": "配电柜1",
    "location": "杭州",
    "broker": "mqtt.example.com",
    "port": 1883,
    "pub_topic": "aa0000000001/pub",
    "sub_topic": "aa0000000001/sub",
    "client_id": "client-aa0000000001",
    "username": "device",
    "password": "secret"
  },
  "description": "一期厂房柜"
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `mac` | string(12) | 设备 MAC，创建时会自动 `strip().upper()` |
| `status` | int (`DeviceStatus`) | 1=enabled, 0=disabled |
| `collect_enabled` | bool | 是否采集数据 |
| `ingress_type` | int | 0=MQTT, 1=TCP |
| `ingress_config` | object | 与采集方式相关的所有配置，见上例 |
| `description` | string? | 备注信息 |

### 成功响应

HTTP 201，body 为 `DeviceResponse`：

```jsonc
{
  "mac": "AA0000000001",
  "status": 1,
  "collect_enabled": true,
  "ingress_type": 0,
  "ingress_config": { ... },
  "description": "一期厂房柜",
  "created_at": "2025-01-01T12:00:00Z"
}
```

### 错误码

| HTTP | error_code | 说明 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | JWT 缺失/无效 |
| 409 | `DEVICE_CONFLICT` | MAC 已存在 |
| 500 | `INTERNAL_ERROR` | 服务器异常 |

### 示例

```bash
curl -X POST https://api.example.com/v1/device-admin/macs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ ... }'
```

```ts
async function createDevice(token, payload) {
  const resp = await fetch("/v1/device-admin/macs", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw await resp.json();
  return resp.json();
}
```

---

## 2. GET `/v1/device-admin/macs`

### 作用

按状态筛选设备列表（后台视角）。

### 请求

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `status` | int? | null | 传 `1` 仅看启用设备，`0` 看禁用设备 |

响应为：

```jsonc
{
  "items": [
    {
      "mac": "AA0000000001",
      "status": 1,
      "collect_enabled": true,
      "...": "..."
    }
  ],
  "total": 2
}
```

错误码：与创建相同（401、500 等）。

---

## 3. PATCH `/v1/device-admin/macs/{mac}`

### 作用

按 MAC 更新设备配置，若成功会重新应用订阅。

### 请求

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `mac` | path string | MAC 大小写不敏感，会转为大写 |

请求体（`DeviceUpdate`）中字段均为可选：

```jsonc
{
  "status": 0,
  "collect_enabled": false,
  "description": "停用维护",
  "ingress_config": { "...": "..." }
}
```

成功响应同 `DeviceResponse`。

错误码：

| HTTP | error_code | 说明 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 缺少/无效 JWT |
| 404 | `DEVICE_NOT_FOUND` | 指定 MAC 不存在 |
| 500 | `INTERNAL_ERROR` | 服务器异常 |

---

## 注意事项

- 创建/更新后会调用 `subscription_manager.apply_device`，可能触发订阅重启。
- `ingress_config` 没有固定 schema，前端需根据业务收集必要字段。
- 请确保 MAC 唯一且使用大写（文档和 UI 均应提示）。
