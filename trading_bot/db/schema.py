"""SQLite DDL 상수 정의"""

# 주문 테이블
CREATE_ORDERS_TABLE = """
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    TEXT NOT NULL UNIQUE,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    order_type  TEXT NOT NULL,
    quantity    INTEGER NOT NULL,
    price       REAL,
    status      TEXT NOT NULL,
    filled_qty  INTEGER NOT NULL DEFAULT 0,
    filled_price REAL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
)
"""

# 거래 테이블
CREATE_TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    quantity    INTEGER NOT NULL,
    price       REAL NOT NULL,
    amount      INTEGER NOT NULL,
    commission  INTEGER NOT NULL DEFAULT 0,
    executed_at TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
)
"""

# 포지션 테이블
CREATE_POSITIONS_TABLE = """
CREATE TABLE IF NOT EXISTS positions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol           TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL DEFAULT '',
    quantity         INTEGER NOT NULL DEFAULT 0,
    avg_price        REAL NOT NULL DEFAULT 0,
    current_price    REAL NOT NULL DEFAULT 0,
    market_value     INTEGER NOT NULL DEFAULT 0,
    profit_loss      INTEGER NOT NULL DEFAULT 0,
    profit_loss_rate REAL NOT NULL DEFAULT 0,
    updated_at       TEXT NOT NULL
)
"""

# 인덱스 정의
CREATE_INDEX_ORDERS_SYMBOL = """
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol)
"""

CREATE_INDEX_ORDERS_STATUS = """
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)
"""

CREATE_INDEX_TRADES_SYMBOL = """
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)
"""

CREATE_INDEX_TRADES_EXECUTED_AT = """
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at)
"""

# 전체 DDL 목록 (일괄 실행용)
ALL_DDL: list[str] = [
    CREATE_ORDERS_TABLE,
    CREATE_TRADES_TABLE,
    CREATE_POSITIONS_TABLE,
    CREATE_INDEX_ORDERS_SYMBOL,
    CREATE_INDEX_ORDERS_STATUS,
    CREATE_INDEX_TRADES_SYMBOL,
    CREATE_INDEX_TRADES_EXECUTED_AT,
]
