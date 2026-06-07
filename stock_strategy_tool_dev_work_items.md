# 选股策略跟踪工具开发工单

## 1. 迭代 1：基础后端与权限

### 1.1 用户认证与权限
- [ ] 设计用户角色与权限模型
  - `admin`：全面访问与修改权限
  - `vip`：查看全部，修改自身数据
  - `user`：仅查看/修改自身数据
- [ ] 实现用户注册与登录接口
- [ ] 实现 JWT 认证中间件
- [ ] 实现 `/api/auth/me` 当前用户信息接口
- [ ] 实现管理员用户列表与用户修改接口

### 1.2 策略管理
- [ ] 设计 `strategies` 表结构
- [ ] 实现新增策略接口 `POST /api/strategies`
- [ ] 实现策略列表查询接口 `GET /api/strategies`
- [ ] 实现策略详情接口 `GET /api/strategies/{strategyId}`
- [ ] 实现策略更新接口 `PUT /api/strategies/{strategyId}`
- [ ] 实现策略删除接口 `DELETE /api/strategies/{strategyId}`

### 1.3 批次管理
- [ ] 设计 `batches` 表结构
- [ ] 实现新增批次接口 `POST /api/strategies/{strategyId}/batches`
- [ ] 实现批次列表查询接口 `GET /api/strategies/{strategyId}/batches`
- [ ] 实现批次详情接口 `GET /api/batches/{batchId}`
- [ ] 实现批次更新接口 `PUT /api/batches/{batchId}`
- [ ] 实现批次删除接口 `DELETE /api/batches/{batchId}`

### 1.4 批次个股管理
- [ ] 设计 `batch_stocks` 表结构
- [ ] 实现批次个股新增接口 `POST /api/batches/{batchId}/stocks`
- [ ] 实现批次个股列表 `GET /api/batches/{batchId}/stocks`
- [ ] 实现批次个股删除接口 `DELETE /api/batches/{batchId}/stocks/{stockId}`

## 2. 迭代 2：行情同步与收益计算

### 2.1 行情同步服务
- [ ] 设计 `market_data` 表结构
- [ ] 实现行情拉取适配层（外部 API 抽象）
- [ ] 实现定时同步任务（每日/手动触发）
- [ ] 实现同步状态查询接口 `GET /api/data/status`
- [ ] 实现数据历史查询接口 `GET /api/data/history`
- [ ] 实现同步日志表 `sync_logs`

### 2.2 收益指标计算
- [ ] 设计 `strategy_metrics` 表结构
- [ ] 实现单个个股每日收益计算
- [ ] 实现批次加权/等权收益汇总逻辑
- [ ] 实现策略层面每日收益与累计收益计算
- [ ] 实现最大涨幅 `max_gain` 计算逻辑
- [ ] 实现最大回撤 `max_drawdown` 计算逻辑
- [ ] 实现 N 日后买入并持有 K 日收益计算接口
- [ ] 实现指标增量写入与更新

### 2.3 报表接口
- [ ] 实现策略指标接口 `GET /api/strategies/{strategyId}/metrics`
- [ ] 实现批次指标接口 `GET /api/batches/{batchId}/metrics`
- [ ] 实现个股指标接口 `GET /api/stocks/{stockCode}/metrics`
- [ ] 实现批次对比接口 `GET /api/strategies/{strategyId}/compare-batches`
- [ ] 实现持有期收益接口 `GET /api/metrics/hold-return`

## 3. 迭代 3：前端展示与部署

### 3.1 可视化页面
- [ ] 设计策略列表页面
- [ ] 设计策略详情与收益曲线页面
- [ ] 设计批次详情与对比页面
- [ ] 设计个股收益走势页面
- [ ] 设计用户权限视图与角色区分

### 3.2 报表与导出
- [ ] 实现收益数据导出 CSV/Excel
- [ ] 实现可视化趋势图与对比图
- [ ] 增加指标卡片显示累计收益、最大回撤、最大涨幅

### 3.3 部署与运维
- [ ] 编写 Dockerfile
- [ ] 编写数据库迁移脚本
- [ ] 编写部署文档
- [ ] 集成日志与错误监控
- [ ] 验证轻量云服务器部署可行性

## 4. 开发工单示例

### 4.1 工单 A：实现策略 CRUD
- 任务目标：完成策略增删改查 API 与权限校验
- 输出：策略表建模、策略接口实现、策略单元测试
- 验收标准：管理员可管理全部策略；VIP/普通用户只能操作自身策略

### 4.2 工单 B：实现行情同步与收益指标
- 任务目标：完成行情数据拉取、数据库写入、收益指标计算
- 输出：同步服务、数据表、收益指标查询接口
- 验收标准：同步数据写入 `market_data`；指标接口返回正确累计收益和回撤

### 4.3 工单 C：实现批次对比可视化接口
- 任务目标：完成 `compare-batches` 和 `hold-return` API
- 输出：对比结果接口与示例数据返回
- 验收标准：同一策略跨批次收益对比准确，N/K 持有期缺失数据返回默认值
