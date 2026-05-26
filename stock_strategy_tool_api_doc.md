# 选股策略跟踪工具接口文档

## 1. 总体说明

- API 类型：RESTful
- 鉴权方式：JWT Token
- 数据格式：JSON
- 访问控制：基于用户角色（admin / vip / user）

---

## 2. 认证与用户管理

### 2.1 POST /api/auth/login

请求体：
```json
{
  "username": "string",
  "password": "string"
}
```

响应：
```json
{
  "access_token": "string",
  "token": "string",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin"
  }
}
```

### 2.2 POST /api/auth/register

说明：开放注册只创建普通用户；若数据库中还没有任何用户，首个注册用户默认初始化为管理员。

请求体：
```json
{
  "username": "string",
  "password": "string",
  "email": "string"
}
```

响应：
```json
{
  "id": 1,
  "username": "string",
  "role": "user"
}
```

### 2.3 GET /api/users

说明：仅管理员可访问。

响应：
```json
[{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "role": "admin"
}]
```

### 2.4 POST /api/users

说明：仅管理员可访问，用于创建指定角色的账户。

请求体：
```json
{
  "username": "string",
  "password": "string",
  "email": "string",
  "role": "user"
}
```

### 2.5 PUT /api/users/{userId}

说明：管理员可修改任意用户；普通用户仅能修改自身。

请求体：
```json
{
  "email": "string",
  "role": "vip"
}
```

响应：
```json
{
  "id": 1,
  "username": "admin",
  "email": "string",
  "role": "vip"
}
```

---

## 3. 策略接口

### 3.1 POST /api/strategies

请求体：
```json
{
  "name": "策略名称",
  "description": "策略描述",
  "benchmark": "CSI300",
  "tags": ["成长", "价值"]
}
```

响应：
```json
{
  "id": 101,
  "owner_id": 1,
  "name": "策略名称",
  "description": "策略描述",
  "benchmark": "CSI300",
  "created_at": "2026-05-22T10:00:00Z"
}
```

### 3.2 GET /api/strategies

说明：admin / vip 可查看全部；普通用户仅查看自身。

查询参数：
- `ownerId` 可选
- `keyword` 可选
- `page` 可选
- `pageSize` 可选

响应：
```json
{
  "total": 10,
  "items": [
    {
      "id": 101,
      "name": "策略名称",
      "description": "",
      "benchmark": "CSI300",
      "owner_id": 1,
      "owner_name": "user1",
      "created_at": "2026-05-22T10:00:00Z"
    }
  ]
}
```

### 3.3 GET /api/strategies/{strategyId}

响应：
```json
{
  "id": 101,
  "name": "策略名称",
  "description": "策略描述",
  "benchmark": "CSI300",
  "owner_id": 1,
  "owner_name": "user1",
  "created_at": "2026-05-22T10:00:00Z",
  "metrics": { ... }
}
```

### 3.4 PUT /api/strategies/{strategyId}

说明：admin 可修改任意；vip/user 仅能修改自己的。

请求体：
```json
{
  "name": "新策略名称",
  "description": "新描述",
  "benchmark": "SZ50"
}
```

### 3.5 DELETE /api/strategies/{strategyId}

说明：删除策略及其关联批次和个股，可选择软删除。

---

## 4. 批次接口

### 4.1 POST /api/strategies/{strategyId}/batches

请求体：
```json
{
  "name": "批次A",
  "batch_date": "2026-05-15",
  "description": "规模策略A"
}
```

响应：
```json
{
  "id": 201,
  "strategy_id": 101,
  "name": "批次A",
  "batch_date": "2026-05-15"
}
```

### 4.2 GET /api/strategies/{strategyId}/batches

查询参数：
- `status` 可选
- `startDate` / `endDate` 可选

响应：
```json
[{
  "id": 201,
  "strategy_id": 101,
  "name": "批次A",
  "batch_date": "2026-05-15",
  "status": "进行中",
  "metrics": { ... }
}]
```

### 4.3 GET /api/batches/{batchId}

响应：
```json
{
  "id": 201,
  "name": "批次A",
  "batch_date": "2026-05-15",
  "metrics": { ... },
  "stocks": [ ... ]
}
```

### 4.4 PUT /api/batches/{batchId}

请求体：
```json
{
  "name": "批次A-更新",
  "description": "更新说明",
  "status": "已完成"
}
```

### 4.5 DELETE /api/batches/{batchId}

说明：仅可删除该批次及其关联个股。

---

## 5. 个股接口

### 5.1 POST /api/batches/{batchId}/stocks

请求体：
```json
{
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "remark": "核心持仓"
}
```

响应：
```json
{
  "id": 301,
  "batch_id": 201,
  "stock_code": "600519",
  "stock_name": "贵州茅台"
}
```

### 5.2 GET /api/batches/{batchId}/stocks

响应：
```json
[{
  "id": 301,
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "added_at": "2026-05-15T09:30:00Z"
}]
```

### 5.3 DELETE /api/batches/{batchId}/stocks/{stockId}

说明：移除该批次中的个股。

---

## 6. 数据同步接口

### 6.1 POST /api/data/sync

说明：触发行情数据同步。可由定时任务或手动调用。

请求体：
```json
{
  "trade_date": "2026-05-22",
  "stock_codes": ["600519", "000001"],
  "index_codes": ["CSI300"]
}
```

响应：
```json
{
  "trade_date": "2026-05-22",
  "success_count": 2,
  "fail_count": 0,
  "errors": [],
  "recalculated_metrics": 12,
  "provider": "akshare"
}
```

### 6.2 GET /api/data/status

响应：
```json
{
  "last_sync_date": "2026-05-22",
  "success_count": 1200,
  "fail_count": 2,
  "errors": [ ... ]
}
```

### 6.3 GET /api/data/history

查询参数：
- `start` `end`

响应：
```json
[{
  "trade_date": "2026-05-21",
  "status": "success"
}]
```

---

## 7. 收益指标与报表接口

### 7.1 GET /api/strategies/{strategyId}/metrics

查询参数：
- `start` `end`
- `basis` 可选：`cumulative` / `daily`

响应：
```json
{
  "strategy_id": 101,
  "start": "2026-05-15",
  "end": "2026-05-22",
  "daily": [
    { "trade_date": "2026-05-15", "return": 0.01, "cumulative": 0.01 }
  ],
  "summary": {
    "total_return": 0.12,
    "max_drawdown": -0.07,
    "max_gain": 0.21
  }
}
```

### 7.2 GET /api/batches/{batchId}/metrics

响应结构同策略指标。

### 7.3 GET /api/stocks/{stockCode}/metrics

查询参数：
- `batchId` 可选
- `start` `end`

响应：
```json
{
  "stock_code": "600519",
  "daily": [ ... ],
  "summary": { ... }
}
```

### 7.4 GET /api/strategies/{strategyId}/compare-batches

查询参数：
- `trade_date` 可选

响应：
```json
{
  "strategy_id": 101,
  "trade_date": "2026-05-15",
  "batch_comparison": [
    { "batch_id": 201, "total_return": 0.08 },
    { "batch_id": 202, "total_return": 0.05 }
  ]
}
```

### 7.5 GET /api/metrics/hold-return

查询参数：
- `n` 必填
- `k` 必填
- `scope` 可选：`strategy` / `batch` / `stock`
- `id` 对应 scope 的 id；当 scope=stock 时为批次个股记录 id

响应：
```json
{
  "scope": "batch",
  "id": 201,
  "n": 3,
  "k": 5,
  "hold_return": 0.12,
  "status": "completed"
}
```

### 7.6 默认返回值说明

如果当前交易日距离加入日不足 N+K 天，返回：
```json
{
  "hold_return": null,
  "status": "insufficient_data"
}
```

---

## 8. 错误处理

统一响应规范：
```json
{
  "code": 400,
  "message": "Invalid request",
  "details": []
}
```

常见错误：
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- 429 Too Many Requests
- 500 Internal Server Error

---

## 9. 角色权限矩阵

- `admin`：所有接口可读写，允许查看与修改全部数据。
- `vip`：可读全部策略/批次；仅写本人数据。
- `user`：仅读写本人策略/批次。

---

## 10. 安全建议

- 所有写操作需校验当前用户身份与数据 ownership。
- 读取操作依据角色返回不同范围数据。
- 敏感字段（如密码）不在响应中返回。
- 接口限流和日志记录。
