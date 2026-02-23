"""주문 실행 관리자"""

from datetime import datetime
from uuid import uuid4

from loguru import logger

from trading_bot.api.kiwoom_client import KiwoomClient
from trading_bot.api.models import (
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
)
from trading_bot.config.settings import settings
from trading_bot.db.repositories import OrderRepository, TradeRecord, TradeRepository
from trading_bot.execution.position_tracker import PositionTracker
from trading_bot.execution.risk_manager import RiskManager
from trading_bot.strategy.base import Signal, SignalType


class OrderManager:
    """
    주문 실행 관리자

    - 신호(Signal) → 주문 변환 및 실행
    - DRY_RUN 모드: 더미 FILLED 응답 반환
    - 리스크 검증 통과 후 실제/더미 주문 실행
    - 주문/거래 기록 DB 저장
    """

    def __init__(
        self,
        client: KiwoomClient,
        risk_manager: RiskManager,
        position_tracker: PositionTracker,
        order_repo: OrderRepository,
        trade_repo: TradeRepository,
    ) -> None:
        self._client = client
        self._risk_manager = risk_manager
        self._position_tracker = position_tracker
        self._order_repo = order_repo
        self._trade_repo = trade_repo
        self._dry_run = settings.trading.dry_run

    async def execute_signal(self, signal: Signal) -> OrderResponse | None:
        """
        신호를 주문으로 변환하여 실행

        Args:
            signal: 매매 신호

        Returns:
            주문 응답 (HOLD이거나 리스크 검증 실패 시 None)
        """
        # HOLD 신호는 실행 스킵
        if signal.type == SignalType.HOLD:
            return None

        if signal.quantity <= 0:
            logger.warning(f"{signal.symbol} 신호 수량 0 - 주문 스킵")
            return None

        # ── 리스크 검증 ───────────────────────────────────────────────────────
        try:
            current_position = self._position_tracker.get_current_position(signal.symbol)
            all_positions = self._position_tracker.get_all_positions()
            current_price = signal.price or _get_price_from_signal(signal)

            if signal.type == SignalType.BUY:
                # 수량 조정 (한도 내 최대)
                adjusted_quantity = self._risk_manager.validate_signal_quantity(
                    signal.quantity, current_price
                )

                # 포지션 한도 검사
                self._risk_manager.check_position_limit(
                    signal.symbol,
                    adjusted_quantity,
                    current_price,
                    current_position,
                )

                # 전체 노출 한도 검사
                new_amount = int(adjusted_quantity * current_price)
                self._risk_manager.check_total_exposure(new_amount, all_positions)

                signal = Signal(
                    type=signal.type,
                    symbol=signal.symbol,
                    reason=signal.reason,
                    quantity=adjusted_quantity,
                    price=signal.price,
                    metadata=signal.metadata,
                )

        except Exception as exc:
            logger.warning(f"{signal.symbol} 리스크 검증 실패 - 주문 스킵: {exc}")
            return None

        # ── 주문 실행 ─────────────────────────────────────────────────────────
        order_request = OrderRequest(
            symbol=signal.symbol,
            side=OrderSide(signal.type.value),
            order_type=OrderType.MARKET if signal.price is None else OrderType.LIMIT,
            quantity=signal.quantity,
            price=signal.price,
            account_number=settings.kiwoom.account_number,
        )

        if self._dry_run:
            current_price = signal.price or 0.0
            order_response = self._create_dry_run_response(order_request, current_price)
            logger.info(
                f"[DRY_RUN] {signal.symbol} {signal.type} {signal.quantity}주 "
                f"@ {current_price:,.0f}원 - {signal.reason}"
            )
        else:
            order_response = await self._client.place_order(order_request)
            logger.info(
                f"주문 실행: {signal.symbol} {signal.type} {signal.quantity}주 "
                f"→ 주문ID={order_response.order_id}"
            )

        # ── DB 저장 ───────────────────────────────────────────────────────────
        await self._order_repo.save_order(order_response)

        if order_response.status == OrderStatus.FILLED and order_response.filled_price:
            trade = TradeRecord(
                order_id=order_response.order_id,
                symbol=order_response.symbol,
                side=order_response.side,
                quantity=order_response.filled_quantity or order_response.quantity,
                price=order_response.filled_price,
                amount=int((order_response.filled_quantity or order_response.quantity) * order_response.filled_price),
            )
            await self._trade_repo.save_trade(trade)

        return order_response

    async def cancel_order(self, order_id: str) -> bool:
        """
        주문 취소

        Args:
            order_id: 취소할 주문 ID

        Returns:
            True (취소 성공)
        """
        result = await self._client.cancel_order(order_id)
        if result:
            logger.info(f"주문 취소 완료: {order_id}")
        else:
            logger.warning(f"주문 취소 실패: {order_id}")
        return result

    def _create_dry_run_response(
        self,
        order: OrderRequest,
        current_price: float,
    ) -> OrderResponse:
        """
        DRY_RUN 모드용 더미 FILLED 주문 응답 생성

        Args:
            order: 주문 요청
            current_price: 현재가 (체결가로 사용)

        Returns:
            더미 주문 응답 (status=FILLED)
        """
        filled_price = current_price if current_price > 0 else 1.0
        return OrderResponse(
            order_id=f"DRY_{uuid4().hex[:8].upper()}",
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            filled_price=filled_price,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )


def _get_price_from_signal(signal: Signal) -> float:
    """신호 메타데이터에서 현재가 추출 (fallback: 1.0)"""
    price = signal.metadata.get("current_price", 1.0)
    return float(price)
