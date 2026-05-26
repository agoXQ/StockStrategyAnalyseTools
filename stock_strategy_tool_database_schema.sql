-- 选股策略跟踪工具数据库建表 SQL

-- 1. 用户表
CREATE TABLE users (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(128) NOT NULL UNIQUE,
  password_hash VARCHAR(256) NOT NULL,
  email VARCHAR(256),
  role VARCHAR(16) NOT NULL DEFAULT 'user',
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 2. 策略表
CREATE TABLE strategies (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  owner_id BIGINT NOT NULL,
  name VARCHAR(256) NOT NULL,
  description TEXT,
  benchmark VARCHAR(64),
  tags JSON,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_strategy_owner FOREIGN KEY (owner_id) REFERENCES users(id)
);
CREATE INDEX idx_strategies_owner ON strategies(owner_id);
CREATE INDEX idx_strategies_status ON strategies(status);

-- 3. 批次表
CREATE TABLE batches (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  strategy_id BIGINT NOT NULL,
  name VARCHAR(256) NOT NULL,
  batch_date DATE NOT NULL,
  description TEXT,
  status VARCHAR(32) NOT NULL DEFAULT '进行中',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_batch_strategy FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);
CREATE INDEX idx_batches_strategy ON batches(strategy_id);
CREATE INDEX idx_batches_batch_date ON batches(batch_date);
CREATE INDEX idx_batches_status ON batches(status);

-- 4. 批次个股表
CREATE TABLE batch_stocks (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  batch_id BIGINT NOT NULL,
  stock_code VARCHAR(32) NOT NULL,
  stock_name VARCHAR(128),
  added_date DATE,
  is_traded BOOLEAN NOT NULL DEFAULT FALSE,
  is_held BOOLEAN NOT NULL DEFAULT FALSE,
  added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  remark TEXT,
  CONSTRAINT fk_batch_stock FOREIGN KEY (batch_id) REFERENCES batches(id),
  UNIQUE KEY uniq_batch_stock_code (batch_id, stock_code)
);
CREATE INDEX idx_batch_stocks_batch ON batch_stocks(batch_id);
CREATE INDEX idx_batch_stocks_code ON batch_stocks(stock_code);

-- 5. 行情数据表
CREATE TABLE market_data (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  trade_date DATE NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  market_type VARCHAR(16) NOT NULL,
  close_price DECIMAL(18, 6) NOT NULL,
  open_price DECIMAL(18, 6),
  high_price DECIMAL(18, 6),
  low_price DECIMAL(18, 6),
  volume BIGINT,
  source VARCHAR(64),
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_market_data (trade_date, symbol)
);
CREATE INDEX idx_market_data_symbol ON market_data(symbol);
CREATE INDEX idx_market_data_trade_date ON market_data(trade_date);

-- 6. 收益与指标表
CREATE TABLE strategy_metrics (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  strategy_id BIGINT NOT NULL,
  batch_id BIGINT NULL,
  stock_code VARCHAR(32) NULL,
  metric_date DATE NOT NULL,
  daily_return DECIMAL(18, 6),
  cumulative_return DECIMAL(18, 6),
  max_drawdown DECIMAL(18, 6),
  max_gain DECIMAL(18, 6),
  trade_days_since_entry INT,
  hold_return_n_k DECIMAL(18, 6),
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_metric_strategy FOREIGN KEY (strategy_id) REFERENCES strategies(id),
  CONSTRAINT fk_metric_batch FOREIGN KEY (batch_id) REFERENCES batches(id)
);
CREATE INDEX idx_strategy_metrics_strategy_date ON strategy_metrics(strategy_id, metric_date);
CREATE INDEX idx_strategy_metrics_batch_date ON strategy_metrics(batch_id, metric_date);
CREATE INDEX idx_strategy_metrics_stock_date ON strategy_metrics(stock_code, metric_date);

-- 7. 同步日志表
CREATE TABLE sync_logs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  trade_date DATE NOT NULL,
  status VARCHAR(32) NOT NULL,
  success_count INT NOT NULL DEFAULT 0,
  fail_count INT NOT NULL DEFAULT 0,
  error_detail TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_sync_logs_trade_date ON sync_logs(trade_date);

-- 8. 可选：策略标签表（如果不使用 JSON）
CREATE TABLE strategy_tags (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  strategy_id BIGINT NOT NULL,
  tag VARCHAR(64) NOT NULL,
  CONSTRAINT fk_strategy_tag_strategy FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);
CREATE INDEX idx_strategy_tags_strategy ON strategy_tags(strategy_id);
