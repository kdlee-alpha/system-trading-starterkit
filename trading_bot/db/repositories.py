"""Repository 패턴 - 주문/거래/포지션 CRUD"""

from dataclasses import dataclass
from datetime import datetime

from trading_bot.api.models import OrderResponse, OrderSide, OrderStatus, OrderType, Position
from trading_bot.db.connection import DatabaseManager


@dataclass
class TradeRecord:
    """거래 기록"""

    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    amount: int
    commission: int = 0
    executed_at: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.executed_at is None:
            self.executed_at = datetime.now()


@dataclass
class TradeSummary:
    """거래 요약 (종목별 집계)"""

    symbol: str
    total_trades: int
    total_quantity: int
    total_amount: int
    total_commission: int
    avg_price: float


class OrderRepository:
    """주문 저장소"""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def save_order(self, order: OrderResponse) -> None:
        """주문 저장 (INSERT OR REPLACE)"""
        async with self._db.connection() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO orders
                    (order_id, symbol, side, order_type, quantity, price,
                     status, filled_qty, filled_price, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.order_id,
                    order.symbol,
                    order.side.value,
                    order.order_type.value,
                    order.quantity,
                    order.price,
                    order.status.value,
                    order.filled_quantity,
                    order.filled_price,
                    order.created_at.isoformat(),
                    order.updated_at.isoformat(),
                ),
            )

    async def get_order(self, order_id: str) -> OrderResponse | None:
        """주문 단건 조회"""
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM orders WHERE order_id = ?",
                (order_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return _row_to_order(dict(row))

    async def list_orders(
        self,
        symbol: str | None = None,
        status: OrderStatus | None = None,
        limit: int = 100,
    ) -> list[OrderResponse]:
        """주문 목록 조회"""
        query = "SELECT * FROM orders WHERE 1=1"
        params: list[str | int] = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with self._db.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [_row_to_order(dict(row)) for row in rows]

    async def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        filled_qty: int,
        filled_price: float | None,
    ) -> bool:
        """주문 상태 업데이트"""
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                UPDATE orders
                SET status = ?, filled_qty = ?, filled_price = ?, updated_at = ?
                WHERE order_id = ?
                """,
                (
                    status.value,
                    filled_qty,
                    filled_price,
                    datetime.now().isoformat(),
                    order_id,
                ),
            )
            return cursor.rowcount > 0


class TradeRepository:
    """거래 기록 저장소"""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def save_trade(self, trade: TradeRecord) -> None:
        """거래 기록 저장"""
        async with self._db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO trades
                    (order_id, symbol, side, quantity, price, amount, commission, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.order_id,
                    trade.symbol,
                    trade.side.value,
                    trade.quantity,
                    trade.price,
                    trade.amount,
                    trade.commission,
                    trade.executed_at.isoformat(),
                ),
            )

    async def list_trades(
        self,
        symbol: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 500,
    ) -> list[TradeRecord]:
        """거래 기록 목록 조회"""
        query = "SELECT * FROM trades WHERE 1=1"
        params: list[str | int] = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if start_date:
            query += " AND executed_at >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND executed_at <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY executed_at DESC LIMIT ?"
        params.append(limit)

        async with self._db.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [_row_to_trade(dict(row)) for row in rows]

    async def get_trade_summary(self, symbol: str | None = None) -> list[TradeSummary]:
        """종목별 거래 요약 (GROUP BY)"""
        query = """
            SELECT
                symbol,
                COUNT(*) AS total_trades,
                SUM(quantity) AS total_quantity,
                SUM(amount) AS total_amount,
                SUM(commission) AS total_commission,
                AVG(price) AS avg_price
            FROM trades
        """
        params: list[str] = []

        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)

        query += " GROUP BY symbol ORDER BY total_amount DESC"

        async with self._db.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [
                TradeSummary(
                    symbol=row["symbol"],
                    total_trades=row["total_trades"],
                    total_quantity=row["total_quantity"],
                    total_amount=row["total_amount"],
                    total_commission=row["total_commission"],
                    avg_price=row["avg_price"],
                )
                for row in rows
            ]


class PositionRepository:
    """포지션 저장소"""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def save_position(self, position: Position) -> None:
        """포지션 저장 (INSERT OR REPLACE = upsert)"""
        async with self._db.connection() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO positions
                    (symbol, name, quantity, avg_price, current_price,
                     market_value, profit_loss, profit_loss_rate, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    position.symbol,
                    position.name,
                    position.quantity,
                    position.avg_price,
                    position.current_price,
                    position.market_value,
                    position.profit_loss,
                    position.profit_loss_rate,
                    datetime.now().isoformat(),
                ),
            )

    async def get_position(self, symbol: str) -> Position | None:
        """포지션 단건 조회"""
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM positions WHERE symbol = ?",
                (symbol,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return Position.model_validate(dict(row))

    async def list_positions(self) -> list[Position]:
        """보유 포지션 목록 조회 (수량 > 0 필터)"""
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM positions WHERE quantity > 0 ORDER BY market_value DESC"
            )
            rows = await cursor.fetchall()
            return [Position.model_validate(dict(row)) for row in rows]

    async def update_position(self, position: Position) -> bool:
        """포지션 업데이트"""
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                UPDATE positions
                SET name = ?, quantity = ?, avg_price = ?, current_price = ?,
                    market_value = ?, profit_loss = ?, profit_loss_rate = ?, updated_at = ?
                WHERE symbol = ?
                """,
                (
                    position.name,
                    position.quantity,
                    position.avg_price,
                    position.current_price,
                    position.market_value,
                    position.profit_loss,
                    position.profit_loss_rate,
                    datetime.now().isoformat(),
                    position.symbol,
                ),
            )
            return cursor.rowcount > 0

    async def delete_position(self, symbol: str) -> bool:
        """포지션 삭제"""
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM positions WHERE symbol = ?",
                (symbol,),
            )
            return cursor.rowcount > 0


# ── 내부 변환 헬퍼 함수 ──────────────────────────────────────────────────────


def _row_to_order(row: dict) -> OrderResponse:
    """DB 행 딕셔너리 → OrderResponse 변환"""
    return OrderResponse(
        order_id=row["order_id"],
        symbol=row["symbol"],
        side=OrderSide(row["side"]),
        order_type=OrderType(row["order_type"]),
        quantity=row["quantity"],
        price=row["price"],
        status=OrderStatus(row["status"]),
        filled_quantity=row["filled_qty"],
        filled_price=row["filled_price"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_trade(row: dict) -> TradeRecord:
    """DB 행 딕셔너리 → TradeRecord 변환"""
    return TradeRecord(
        order_id=row["order_id"],
        symbol=row["symbol"],
        side=OrderSide(row["side"]),
        quantity=row["quantity"],
        price=row["price"],
        amount=row["amount"],
        commission=row["commission"],
        executed_at=datetime.fromisoformat(row["executed_at"]),
    )
