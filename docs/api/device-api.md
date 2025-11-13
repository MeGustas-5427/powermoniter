# Device API 文档

本文档面向前端/QA，介绍 `/v1/devices` 与 `/v1/devices/{device_id}/electricity` 两个接口的用法、参数、返回值和错误码。

- 所有接口均要求 `Authorization: Bearer <token>` 头，token 来源于 `/v1/auth/login`。
- 响应中的时间字段均为 UTC，格式 `YYYY-MM-DDThh:mm:ssZ`。

---

## 1. GET `/v1/devices`

### 概述

分页列出当前用户有权限查看的设备，支持状态过滤。用于仪表盘设备列表。

### 请求

| Method | URL | Auth | Content-Type |
| --- | --- | --- | --- |
| GET | `/v1/devices` | 必须（JWT Bearer） | N/A |

Query 参数：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | int ≥ 1 | 1 | 页码 |
| `page_size` | int 1~100 | 20 | 单页数量，最大 100 |
| `status` | enum | `all` | 可选：`online` / `offline` / `maintenance` / `all` |

### 成功响应

HTTP 200，body 为 `DeviceListResponse`：

```jsonc
{
  "success": true,
  "data": {
    "page": 1,
    "page_size": 20,
    "total": 57,
    "items": [
      {
        "device_id": "019a7827-da4b-7c8f-a729-6b5f5f17c303",
        "mac": "AA0000000001",
        "name": "配电柜1",
        "description": "XXX 厂房",
        "location": "杭州",
        "status": "online",
        "last_seen_at": "2025-01-01T11:55:00Z"
      }
    ]
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | `"online"|"offline"|"maintenance"` | 系统计算的运行状态 |
| `last_seen_at` | string? | 最近一次 telemetry 时间，ISO8601 UTC；无数据时为 `null` |
| `total` | int | 满足过滤条件的总数 |

### 错误码

| HTTP | error_code | 场景 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 未携带或携带无效 JWT |
| 403 | `FORBIDDEN` | 角色无权访问（如后续引入） |
| 500 | `INTERNAL_ERROR` | 服务器异常 |

### 示例

#### cURL

```bash
curl -G "https://api.example.com/v1/devices" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=20" \
  --data-urlencode "status=online"
```

#### JavaScript

```ts
async function fetchDevices(token, params = { page: 1, page_size: 20, status: "all" }) {
  const query = new URLSearchParams(params).toString();
  const resp = await fetch(`/v1/devices?${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) throw await resp.json();
  return resp.json();
}
```

---

## 2. GET `/v1/devices/{device_id}/electricity`

### 概述

查询单个设备在 24h / 7d / 30d 时间窗口内的电量曲线（桶统计）。

### 请求

| Method | URL | Auth | Content-Type |
| --- | --- | --- | --- |
| GET | `/v1/devices/{device_id}/electricity` | 必须（JWT Bearer） | N/A |

Path & Query 参数：

| 参数 | 位置 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `device_id` | path | UUID | - | 设备 ID |
| `window` | query | enum | `24h` | 可选：`24h` / `7d` / `30d` |

### 成功响应

HTTP 200，body 为 `ElectricityResponse`：

```jsonc
{
  "success": true,
  "data": {
    "device_id": "019a7827-da4b-7c8f-a729-6b5f5f17c303",
    "start_time": "2025-01-01T00:00:00Z",
    "end_time": "2025-01-02T00:00:00Z",
    "interval": "pt5m",
    "points": [
      {
        "timestamp": "2025-01-01T00:05:00Z",
        "power_kw": 1.23,
        "energy_kwh": 0.4,
        "voltage_v": 220.1,
        "current_a": 1.8
      }
    ]
  }
}
```

说明：

- `interval`：窗口对应的桶粒度，24h → `pt5m`，7d → `pt30m`，30d → `pt120m`。
- `points`：仅包含 `count > 0` 的桶，按时间升序。

### 错误码

| HTTP | error_code | 场景 |
| --- | --- | --- |
| 400 | `INVALID_TIME_RANGE` | `window` 不在 24h/7d/30d |
| 401 | `UNAUTHORIZED` | 缺少或非法 JWT |
| 404 | `DEVICE_NOT_FOUND` | 设备不存在或不属于当前用户 |
| 500 | `INTERNAL_ERROR` | 服务器异常 |

### 示例

#### cURL

```bash
curl -G "https://api.example.com/v1/devices/019a7827-da4b-7c8f-a729-6b5f5f17c303/electricity" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "window=7d"
```

#### JavaScript

```ts
async function fetchElectricity(token, deviceId, window = "24h") {
  const resp = await fetch(`/v1/devices/${deviceId}/electricity?window=${window}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) throw await resp.json();
  return resp.json();
}
```

---

## 3. 参考与注意事项

- 所有时间字符串均为 UTC，前端若需本地化需自行转换。
- `status` 过滤与 `window` 参数对大小写敏感（统一使用小写）。
- 访问频率较高的页面建议缓存 `points` 数据，减少重复请求。
