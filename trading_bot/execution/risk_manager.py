"""리스크 관리 모듈"""

from loguru import logger

from trading_bot.api.models import Position
from trading_bot.config.settings import settings
from trading_bot.utils.exceptions import (
    PositionLimitExceededError,
    TotalExposureLimitExceededError,
)


class RiskManager:
    """
    매매 리스크 관리

    포지션 한도 및 전체 투자 노출 한도를 검증합니다.
    """

    def __init__(self) -> None:
        self._max_position_size = settings.trading.max_position_size
        self._max_total_exposure = settings.trading.max_total_exposure

    def check_position_limit(
        self,
        symbol: str,
        quantity: int,
        price: float,
        current_position: Position | None,
    ) -> bool:
        """
        종목별 포지션 한도 검사

        Args:
            symbol: 종목 코드
            quantity: 추가 매수 수량
            price: 매수 가격
            current_position: 현재 보유 포지션

        Returns:
            True (한도 이내)

        Raises:
            PositionLimitExceededError: 한도 초과 시
        """
        new_amount = int(quantity * price)
        existing_value = current_position.market_value if current_position else 0
        total_amount = new_amount + existing_value

        if total_amount > self._max_position_size:
            raise PositionLimitExceededError(
                symbol=symbol,
                amount=total_amount,
                limit=self._max_position_size,
            )

        logger.debug(
            f"{symbol} 포지션 한도 검사 통과: {total_amount:,}원 / {self._max_position_size:,}원"
        )
        return True

    def check_total_exposure(
        self,
        new_amount: int,
        positions: list[Position],
    ) -> bool:
        """
        전체 투자 노출 한도 검사

        Args:
            new_amount: 추가 투자 금액
            positions: 현재 전체 보유 포지션

        Returns:
            True (한도 이내)

        Raises:
            TotalExposureLimitExceededError: 한도 초과 시
        """
        current_exposure = sum(p.market_value for p in positions)
        total = current_exposure + new_amount

        if total > self._max_total_exposure:
            raise TotalExposureLimitExceededError(
                additional=new_amount,
                current=current_exposure,
                limit=self._max_total_exposure,
            )

        logger.debug(
            f"전체 노출 한도 검사 통과: {total:,}원 / {self._max_total_exposure:,}원"
        )
        return True

    def validate_signal_quantity(self, quantity: int, price: float) -> int:
        """
        신호 수량 유효성 검사 및 한도 내 조정

        매수 금액이 종목 최대 포지션 한도를 초과하면
        한도 내 최대 수량으로 조정합니다.

        Args:
            quantity: 원래 신호 수량
            price: 매수 가격

        Returns:
            조정된 수량
        """
        max_quantity = int(self._max_position_size // price)
        adjusted = min(quantity, max_quantity)

        if adjusted != quantity:
            logger.info(
                f"수량 조정: {quantity} → {adjusted} "
                f"(한도 {self._max_position_size:,}원 / 가격 {price:,.0f}원)"
            )

        return adjusted
