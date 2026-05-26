import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _sqlite_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
    return {row["name"] for row in rows}


def _sqlite_table_info(conn, table_name: str):
    return conn.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()


def _execute_best_effort(conn, sql: str) -> None:
    try:
        conn.execute(text(sql))
    except Exception as exc:
        logger.warning("SQLite schema migration skipped for %s: %s", sql, exc)


def _ensure_users_integer_pk(conn) -> None:
    columns = _sqlite_table_info(conn, "users")
    id_column = next((column for column in columns if column["name"] == "id"), None)
    if not id_column or id_column["type"].upper() == "INTEGER":
        return

    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(
        text(
            """
            CREATE TABLE users_new (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(128) NOT NULL UNIQUE,
                password_hash VARCHAR(256) NOT NULL,
                email VARCHAR(256),
                role VARCHAR(16) NOT NULL,
                status VARCHAR(16) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO users_new (id, username, password_hash, email, role, status, created_at, updated_at)
            SELECT id, username, password_hash, email, role, status, created_at, updated_at
            FROM users
            """
        )
    )
    conn.execute(text("DROP TABLE users"))
    conn.execute(text("ALTER TABLE users_new RENAME TO users"))
    conn.execute(text("PRAGMA foreign_keys=ON"))


def ensure_sqlite_schema(engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        _ensure_users_integer_pk(conn)
        batch_stock_columns = _sqlite_columns(conn, "batch_stocks")
        if "added_date" not in batch_stock_columns:
            conn.execute(text("ALTER TABLE batch_stocks ADD COLUMN added_date DATE"))
        if "is_traded" not in batch_stock_columns:
            conn.execute(text("ALTER TABLE batch_stocks ADD COLUMN is_traded BOOLEAN NOT NULL DEFAULT 0"))
        if "is_held" not in batch_stock_columns:
            conn.execute(text("ALTER TABLE batch_stocks ADD COLUMN is_held BOOLEAN NOT NULL DEFAULT 0"))

        sync_logs_columns = _sqlite_columns(conn, "sync_logs")
        if "log_type" not in sync_logs_columns:
            conn.execute(text("ALTER TABLE sync_logs ADD COLUMN log_type VARCHAR(32) NOT NULL DEFAULT 'sync'"))
        if "level" not in sync_logs_columns:
            conn.execute(text("ALTER TABLE sync_logs ADD COLUMN level VARCHAR(16) NOT NULL DEFAULT 'info'"))
        if "message" not in sync_logs_columns:
            conn.execute(text("ALTER TABLE sync_logs ADD COLUMN message TEXT"))

        _execute_best_effort(conn, """
            CREATE TABLE IF NOT EXISTS app_logs (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                level VARCHAR(16) NOT NULL DEFAULT 'info',
                category VARCHAR(64) NOT NULL DEFAULT 'general',
                message TEXT NOT NULL,
                details TEXT,
                source VARCHAR(64),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        _execute_best_effort(conn, """
            CREATE TABLE IF NOT EXISTS stock_basic_info (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                stock_code VARCHAR(32) NOT NULL UNIQUE,
                stock_name VARCHAR(128),
                industry VARCHAR(128),
                market VARCHAR(32),
                list_date DATE,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        stock_basic_info_columns = _sqlite_columns(conn, "stock_basic_info")
        if "market_type" in stock_basic_info_columns and "market" not in stock_basic_info_columns:
            conn.execute(text("ALTER TABLE stock_basic_info RENAME COLUMN market_type TO market"))
        if "updated_at" not in stock_basic_info_columns:
            conn.execute(text("ALTER TABLE stock_basic_info ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"))
        if "created_at" not in stock_basic_info_columns:
            conn.execute(text("ALTER TABLE stock_basic_info ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"))
        if "list_status" in stock_basic_info_columns:
            conn.execute(text("ALTER TABLE stock_basic_info DROP COLUMN list_status"))

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            "CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)",
            "CREATE INDEX IF NOT EXISTS idx_strategies_owner ON strategies(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_strategies_status ON strategies(status)",
            "CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name)",
            "CREATE INDEX IF NOT EXISTS idx_batches_strategy ON batches(strategy_id)",
            "CREATE INDEX IF NOT EXISTS idx_batches_batch_date ON batches(batch_date)",
            "CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status)",
            "CREATE INDEX IF NOT EXISTS idx_batch_stocks_batch ON batch_stocks(batch_id)",
            "CREATE INDEX IF NOT EXISTS idx_batch_stocks_code ON batch_stocks(stock_code)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uniq_batch_stock_code ON batch_stocks(batch_id, stock_code)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uniq_market_data_date_symbol ON market_data(trade_date, symbol)",
            "CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_market_data_trade_date ON market_data(trade_date)",
            "CREATE INDEX IF NOT EXISTS idx_market_data_market_type ON market_data(market_type)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_metrics_strategy_date ON strategy_metrics(strategy_id, metric_date)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_metrics_batch_date ON strategy_metrics(batch_id, metric_date)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_metrics_stock_date ON strategy_metrics(stock_code, metric_date)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_metrics_scope ON strategy_metrics(strategy_id, batch_id, stock_code, metric_date)",
            "CREATE INDEX IF NOT EXISTS idx_sync_logs_log_type ON sync_logs(log_type)",
            "CREATE INDEX IF NOT EXISTS idx_sync_logs_level ON sync_logs(level)",
            "CREATE INDEX IF NOT EXISTS idx_sync_logs_created_at ON sync_logs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_app_logs_level ON app_logs(level)",
            "CREATE INDEX IF NOT EXISTS idx_app_logs_category ON app_logs(category)",
            "CREATE INDEX IF NOT EXISTS idx_app_logs_created_at ON app_logs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_stock_basic_info_code ON stock_basic_info(stock_code)",
            "CREATE INDEX IF NOT EXISTS idx_stock_basic_info_name ON stock_basic_info(stock_name)",
        ]
        for sql in indexes:
            _execute_best_effort(conn, sql)