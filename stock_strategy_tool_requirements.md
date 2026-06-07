# 选股策略跟踪工具需求文档

## 1. 项目目标

构建一个轻量级的选股策略跟踪工具，用于管理策略、批次与个股的选股结果，支持自动获取收盘数据并更新数据库，持续跟踪策略收益与风险指标，提供可视化报表与权限控制，能够部署在云服务器上，支持约 100 个用户访问。

---

## 2. 用户角色与权限

### 2.1 管理员
- 可以查看全部策略与全部批次
- 可以新增、修改、删除任意策略与批次
- 可以管理用户账户及权限
- 可以查看整体系统统计信息和日志

### 2.2 VIP 用户
- 可以查看全部策略与全部批次的情况
- 只能新增、修改、删除自己的策略与批次
- 不能修改其他用户的策略与批次

### 2.3 普通用户
- 只能查看自己的策略与批次
- 只能新增、修改、删除自己的策略与批次
- 不能查看或操作他人的策略与批次

---

## 3. 核心概念

### 3.1 策略（Strategy）
- 策略名称
- 策略描述
- 创建人
- 标签/分类
- 默认基准（可选，例如上证指数、沪深300）
- 创建日期、更新时间

### 3.2 批次（Batch）
- 所属策略
- 批次名称
- 批次日期（选股日期）
- 选股备注
- 状态（进行中 / 已完成 / 失效）
- 关联的选股列表
- 创建日期、更新时间

### 3.3 个股（Stock）
- 股票代码
- 股票名称
- 批次关联
- 加入日期（与批次日期一致或可修正）
- 目标持仓说明 / 买入理由

### 3.4 收盘数据与行情数据
- 交易日
- 股票代码
- 收盘价
- 开盘价、最高价、最低价、成交量（可选）
- 指数收盘价（用于策略对比）
- 数据更新时间

---

## 4. 功能需求

### 4.1 策略管理
- 新增策略
- 编辑策略
- 删除策略
- 管理策略所属用户
- 支持策略分类及关键词搜索

### 4.2 批次管理
- 在策略下新增批次
- 支持批次名称、选股日期、批次说明
- 编辑批次信息
- 删除批次
- 批次列表展示

### 4.3 批次选股管理
- 在批次下新增/删除个股
- 支持批次一次性导入多只股票
- 支持按批次查看个股列表
- 支持批次标注“是否已成交”或“是否已持有”

### 4.4 外部 API 收盘数据获取与更新
- 支持定时任务从外部 API 获取收盘数据
- 能够补全历史交易日数据
- 支持按交易日、股票代码、指数代码查询最新数据
- 将获取到的收盘价写入数据库
- 数据更新失败时保留失败原因并报警（日志即可）
- 支持手动触发数据同步

### 4.5 收益与风险计算
- 对每个批次和策略，计算如下指标：
  - 自加入后到当前日期的累计收益（单只股票、批次、策略）
  - 期间最大涨幅（running max 最高收益）
  - 最大回撤（从峰值到谷底的最大跌幅）
  - 每天收益变化（按交易日计算）
- 策略收益比较：
  - 以策略为单位，对同一策略加入日同一天内的多个批次进行对比
  - 计算策略层面累计收益和批次间相对表现
- N 日后买入、持有 K 日收益：
  - 对每个策略、批次、个股支持“加入后 N 个交易日后买入，持有 K 天”收益计算
  - 如果当前距离加入日还不足 N+K 个交易日，则返回默认值（例如 null / 未达标 / 0）

### 4.6 可视化与报表
- 策略总体收益走势图
- 批次收益走势对比
- 个股加入后每日收益变化曲线
- 累计收益、最大回撤、最大涨幅指标卡片
- 策略与批次之间日常走势对比图
- N 日后买入持有 K 日收益热力图或表格
- 支持按策略、批次、股票筛选展示
- 支持导出收益数据（CSV/Excel）

### 4.7 用户权限与访问控制
- 用户登录/注册（管理员可创建账户）
- 身份认证与授权
- 普通用户只能访问自己的策略与批次
- VIP 用户可查看全部数据，但仅修改自己的数据
- 管理员可管理全部策略、批次、用户
- API 接口必须校验当前用户权限

---

## 5. 数据模型建议

### 5.1 数据表结构（关系型数据库）

- users
  - id
  - username
  - password_hash
  - role (admin / vip / user)
  - email
  - created_at
  - updated_at

- strategies
  - id
  - owner_id
  - name
  - description
  - benchmark
  - status
  - created_at
  - updated_at

- batches
  - id
  - strategy_id
  - name
  - batch_date
  - description
  - status
  - created_at
  - updated_at

- batch_stocks
  - id
  - batch_id
  - stock_code
  - stock_name
  - added_at
  - remark

- market_data
  - id
  - trade_date
  - stock_code
  - close_price
  - open_price
  - high_price
  - low_price
  - volume
  - index_code
  - index_close_price
  - source
  - updated_at

- strategy_metrics
  - id
  - strategy_id
  - batch_id (可选)
  - stock_code (可选)
  - metric_date
  - cumulative_return
  - max_drawdown
  - max_gain
  - daily_return
  - buy_after_n_days_return
  - hold_k_days_return
  - created_at

---

## 6. 关键 API 设计

### 6.1 策略 API
- POST /api/strategies
- GET /api/strategies
- GET /api/strategies/{strategyId}
- PUT /api/strategies/{strategyId}
- DELETE /api/strategies/{strategyId}

### 6.2 批次 API
- POST /api/strategies/{strategyId}/batches
- GET /api/strategies/{strategyId}/batches
- GET /api/batches/{batchId}
- PUT /api/batches/{batchId}
- DELETE /api/batches/{batchId}

### 6.3 个股 API
- POST /api/batches/{batchId}/stocks
- GET /api/batches/{batchId}/stocks
- DELETE /api/batches/{batchId}/stocks

### 6.4 数据同步 API
- POST /api/data/sync?date=YYYY-MM-DD
- GET /api/data/status
- GET /api/data/history?start=YYYY-MM-DD&end=YYYY-MM-DD

### 6.5 收益与报表 API
- GET /api/strategies/{strategyId}/metrics?start=YYYY-MM-DD&end=YYYY-MM-DD
- GET /api/batches/{batchId}/metrics?start=YYYY-MM-DD&end=YYYY-MM-DD
- GET /api/stocks/{stockCode}/metrics?start=YYYY-MM-DD&end=YYYY-MM-DD
- GET /api/strategies/{strategyId}/compare-batches?date=YYYY-MM-DD
- GET /api/metrics/hold-return?n={N}&k={K}&scope=strategy|batch|stock

---

## 7. 业务流程

### 7.1 新增策略与批次流程
1. 用户登录
2. 用户创建策略
3. 在策略下新增批次并登记选股列表
4. 系统记录批次日期与选股明细

### 7.2 数据获取流程
1. 系统定时任务或手动触发外部 API 数据拉取
2. 获取指定交易日的个股收盘价与指数收盘价
3. 将数据写入 `market_data`
4. 更新策略、批次、个股的收益指标

### 7.3 收益计算流程
1. 计算每个个股从加入日开始的每日收益
2. 批次收益按批次内股票平均或等权加权汇总
3. 策略收益按策略内所有批次累计计算
4. 计算最大涨幅、最大回撤、N 日后买入持有 K 日收益

### 7.4 权限检查流程
1. 用户访问时读取角色
2. 普通用户请求策略/批次时，仅返回 owner_id 与当前用户匹配的数据
3. VIP 用户读取全部策略/批次，但修改时依然校验 owner_id
4. 管理员绕过普通权限，允许全部访问

---

## 8. 可视化需求

### 8.1 关键图表
- 策略净值曲线图
- 批次收益对比图
- 个股每日收益瀑布图/折线图
- 最大回撤与最大涨幅指标图
- N 日后买入、持有 K 日收益表格
- 策略与批次的同期比较图

### 8.2 页面/仪表盘
- 策略总览页：展示策略列表、关键指标、最新批次
- 批次详情页：展示批次个股、收益趋势、风险指标
- 个股详情页：展示加入后每日报酬、N/K 策略收益
- 用户个人页：展示自己策略与批次的历史表现
- 管理员页：展示全局策略统计、数据同步状态、用户管理

---

## 9. 非功能需求

### 9.1 性能与规模
- 支持约 100 个并发用户
- 数据库应支持数千条策略与批次、数万个个股行情记录
- 页面查询响应时间尽量控制在 1-2 秒以内
- 定时数据同步任务可批量处理最近交易日数据

### 9.2 可部署性
- 可部署在轻量级云服务器（例如 1-2 核、4-8GB 内存）
- 推荐使用容器化方案（Docker）或轻量级应用框架
- 支持 PostgreSQL/MySQL 等关系型数据库
- 前后端可分离部署，后端提供 REST API

### 9.3 安全
- 用户密码加密存储
- API 采用令牌认证（JWT / Session）
- 严格权限校验
- 防止 SQL 注入、越权访问
- 日志记录关键操作

### 9.4 可维护性
- 代码结构清晰，模块化拆分
- 收益计算与数据同步逻辑可测试
- 支持日志与监控

---

## 10. 后续扩展建议

- 添加更多对比基准（多指数、行业指数）
- 支持权重交易策略和不同持仓方式
- 支持持仓成本及手续费计算
- 提供策略回测功能
- 支持推送报告与邮件提醒

---

## 11. 交付内容

- 完整的策略与批次管理后端
- 收盘数据同步模块
- 策略、批次、个股收益计算模块
- 权限控制与用户管理功能
- 可视化报表页面
- 部署说明文档

---

## 12. 输出格式建议

建议将该文档作为项目初期需求规范，后续分成：
- `需求说明书`
- `数据模型文档`
- `接口文档`
- `部署方案`

如果你愿意，我可以继续帮助拆分成更详细的开发任务与接口设计。