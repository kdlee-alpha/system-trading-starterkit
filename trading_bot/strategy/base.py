"""전략 추상 기반 클래스 및 Signal 정의"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from trading_bot.api.models import OHLCVBar, Position


class SignalType(StrEnum):
    """매매 신호 유형"""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Signal:
    """
    매매 신호

    Attributes:
        type: 신호 유형 (BUY/SELL/HOLD)
        symbol: 종목 코드
        reason: 신호 발생 이유 (로그/알림용)
        quantity: 주문 수량 (HOLD 시 0)
        price: 지정가 주문 가격 (None이면 시장가)
        metadata: 지표 값 등 부가 정보
    """

    type: SignalType
    symbol: str
    reason: str
    quantity: int = 0
    price: float | None = None
    metadata: dict[str, float | int | str] = field(default_factory=dict)


class BaseStrategy(ABC):
    """매매 전략 추상 기반 클래스"""

    @abstractmethod
    async def generate_signal(
        self,
        symbol: str,
        ohlcv: list[OHLCVBar],
        current_position: Position | None,
    ) -> Signal:
        """
        매매 신호 생성

        Args:
            symbol: 종목 코드
            ohlcv: OHLCV 봉 데이터 (최신 데이터 기준 내림차순)
            current_position: 현재 보유 포지션 (없으면 None)

        Returns:
            매매 신호
        """
        ...

    async def initialize(self) -> None:
        """
        전략 초기화 (선택적 오버라이드)

        봇 시작 시 1회 호출됩니다.
        """

    async def on_order_filled(self, symbol: str, signal: Signal) -> None:
        """
        주문 체결 콜백 (선택적 오버라이드)

        Args:
            symbol: 종목 코드
            signal: 체결된 신호
        """
