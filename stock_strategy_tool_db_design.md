# 选股策略跟踪工具数据库设计

## 1. 总体说明

- 推荐数据库：PostgreSQL / MySQL
- 设计原则：关系型数据建模，支持权限控制、历史行情、收益指标和可扩展性。
- 主要实体：用户、策略、批次、批次个股、行情数据、收益指标、日志

---

## 2. 数据表设计

### 2.1 users

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 用户 ID |
| username | VARCHAR(128) UNIQUE | 登录账号 |
| password_hash | VARCHAR(256) | 密码哈希 |
| email | VARCHAR(256) | 邮箱 |
| role | VARCHAR(16) | admin / vip / user |
| status | VARCHAR(16) | active / disabled |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

索引：
- UNIQUE(username)
- INDEX(role)

### 2.2 strategies

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 策略 ID |
| owner_id | BIGINT FK -> users.id | 所属用户 |
| name | VARCHAR(256) | 策略名称 |
| description | TEXT | 策略描述 |
| benchmark | VARCHAR(64) | 对比基准，例如 CSI300 |
| tags | JSON / VARCHAR | 标签列表 |
| status | VARCHAR(32) | active / inactive |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

索引：
- INDEX(owner_id)
- INDEX(status)
- FULLTEXT(name, description) 或 VARCHAR 关键词索引

### 2.3 batches

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 批次 ID |
| strategy_id | BIGINT FK -> strategies.id | 所属策略 |
| name | VARCHAR(256) | 批次名称 |
| batch_date | DATE | 选股日期 |
| description | TEXT | 批次说明 |
| status | VARCHAR(32) | 进行中 / 已完成 / 失效 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

索引：
- INDEX(strategy_id)
- INDEX(batch_date)
- INDEX(status)

### 2.4 batch_stocks

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 记录 ID |
| batch_id | BIGINT FK -> batches.id | 所属批次 |
| stock_code | VARCHAR(32) | 股票代码 |
| stock_name | VARCHAR(128) | 股票名称 |
| added_at | TIMESTAMP | 加入时间 |
| remark | TEXT | 个股备注 |

索引：
- INDEX(batch_id)
- INDEX(stock_code)

### 2.5 market_data

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 记录 ID |
| trade_date | DATE | 交易日 |
| symbol | VARCHAR(32) | 股票或指数代码 |
| market_type | VARCHAR(16) | stock / index |
| close_price | DECIMAL(18, 6) | 收盘价 |
| open_price | DECIMAL(18, 6) | 开盘价 |
| high_price | DECIMAL(18, 6) | 最高价 |
| low_price | DECIMAL(18, 6) | 最低价 |
| volume | BIGINT | 成交量 |
| source | VARCHAR(64) | 数据来源 |
| updated_at | TIMESTAMP | 更新时间 |

索引：
- UNIQUE(trade_date, symbol)
- INDEX(symbol)
- INDEX(trade_date)

### 2.6 strategy_metrics

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 指标记录 ID |
| strategy_id | BIGINT FK -> strategies.id | 策略 ID |
| batch_id | BIGINT FK -> batches.id NULLABLE | 批次 ID |
| stock_code | VARCHAR(32) NULLABLE | 个股代码 |
| metric_date | DATE | 指标日期 |
| daily_return | DECIMAL(18, 6) | 当日收益率 |
| cumulative_return | DECIMAL(18, 6) | 累计收益率 |
| max_drawdown | DECIMAL(18, 6) | 最大回撤 |
| max_gain | DECIMAL(18, 6) | 最大涨幅 |
| trade_days_since_entry | INT | 自加入日交易日天数 |
| hold_return_n_k | DECIMAL(18, 6) NULLABLE | N 日后买入持有 K 日收益 |
| updated_at | TIMESTAMP | 更新时间 |

索引：
- INDEX(strategy_id, metric_date)
- INDEX(batch_id, metric_date)
- INDEX(stock_code, metric_date)

### 2.7 sync_logs

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 日志 ID |
| trade_date | DATE | 同步交易日 |
| status | VARCHAR(32) | success / failed |
| success_count | INT | 成功记录数 |
| fail_count | INT | 失败记录数 |
| error_detail | TEXT | 异常信息 |
| created_at | TIMESTAMP | 创建时间 |

索引：
- INDEX(trade_date)

---

## 3. 关系图说明

- users 1:n strategies
- strategies 1:n batches
- batches 1:n batch_stocks
- market_data 存储股票和指数行情
- strategy_metrics 关联策略/批次/个股的每日收益指标

---

## 4. 关键设计说明

### 4.1 行情数据建模

- `market_data` 统一存储股票和指数，使用 `market_type` 区分。
- `symbol` 可以是股票代码或指数代码。
- 通过 `trade_date` 与 `symbol` 唯一约束避免重复写入。

### 4.2 收益数据建模

- `strategy_metrics` 支持策略、批次、个股同表存储，有利于统一查询与报表。
- `batch_id` 和 `stock_code` 均可为空，策略级指标仅填 strategy_id。
- `hold_return_n_k` 用于存储 N+K 持有期收益，若数据不足则为空。

### 4.3 权限控制

- 在业务层校验 `owner_id` 对于策略与批次的访问权限。
- `vip` 只限制写权限；读全部数据。

### 4.4 扩展接口与索引

- 对 `strategies.name`、`batches.batch_date`、`market_data.symbol` 添加索引提高查询效率。
- 若未来支持多标签、行业、组合，则可新增 `strategy_tags`、`stock_categories` 等表。

---

## 5. 数据库部署建议

- 生产环境建议 PostgreSQL 14+ 或 MySQL 8+
- 备份策略：每日全量备份 + 增量日志备份
- 性能优化：
  - 批量写入行情与指标数据
  - 普通查询使用分页
  - 定时清理历史日志
  - 对大表建立合适分区（如 `market_data` 按年分区）

---

## 6. 数据一致性与事务

- 策略/批次/个股 CRUD 操作应在事务内执行
- 数据同步时，若某个交易日数据拉取失败，写失败记录并回滚该批次写入
- 指标计算可异步执行，避免阻塞主流程
