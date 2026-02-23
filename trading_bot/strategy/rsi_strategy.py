"""RSI 기반 역추세 전략"""

import pandas as pd
from loguru import logger

from trading_bot.api.models import OHLCVBar, Position
from trading_bot.config.settings import settings
from trading_bot.data.indicators import calculate_rsi
from trading_bot.strategy.base import BaseStrategy, Signal, SignalType
from trading_bot.utils.exceptions import StrategyError


class RSIStrategy(BaseStrategy):
    """
    RSI 기반 역추세 매매 전략

    - 매수: RSI < oversold_threshold (과매도 구간 진입)
    - 매도: RSI > overbought_threshold (과매수 구간) AND 포지션 보유 중
    - 데이터 부족 또는 NaN RSI → HOLD 반환
    """

    def __init__(
        self,
        period: int = 14,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 70.0,
    ) -> None:
        """
        Args:
            period: RSI 계산 기간 (기본 14)
            oversold_threshold: 매수 기준 RSI 하한 (기본 30)
            overbought_threshold: 매도 기준 RSI 상한 (기본 70)
        """
        self._period = period
        self._oversold = oversold_threshold
        self._overbought = overbought_threshold
        self._max_position_size = settings.trading.max_position_size

    async def generate_signal(
        self,
        symbol: str,
        ohlcv: list[OHLCVBar],
        current_position: Position | None,
    ) -> Signal:
        """RSI 기반 매매 신호 생성"""
        try:
            # 데이터 부족 확인 (period + 1 이상 필요)
            if len(ohlcv) < self._period + 1:
                return Signal(
                    type=SignalType.HOLD,
                    symbol=symbol,
                    reason=f"데이터 부족 ({len(ohlcv)}봉, 최소 {self._period + 1}봉 필요)",
                )

            # OHLCV → 종가 Series 변환 (시간 오름차순 정렬)
            closes = pd.Series(
                [bar.close for bar in reversed(ohlcv)],
                dtype=float,
            )

            # RSI 계산
            rsi_series = calculate_rsi(closes, self._period)
            current_rsi = rsi_series.iloc[-1]

            # NaN RSI 확인
            if pd.isna(current_rsi):
                return Signal(
                    type=SignalType.HOLD,
                    symbol=symbol,
                    reason="RSI 계산 불가 (NaN)",
                )

            rsi_value = float(current_rsi)
            current_price = ohlcv[0].close  # 최신 종가

            logger.debug(f"{symbol} RSI={rsi_value:.2f}, 현재가={current_price:,.0f}")

            # 매수 신호: RSI 과매도 구간
            if rsi_value < self._oversold:
                quantity = int(self._max_position_size // current_price)
                if quantity <= 0:
                    return Signal(
                        type=SignalType.HOLD,
                        symbol=symbol,
                        reason=f"RSI 과매도({rsi_value:.2f}) - 최대 포지션 대비 수량 0",
                        metadata={"rsi": rsi_value},
                    )
                return Signal(
                    type=SignalType.BUY,
                    symbol=symbol,
                    reason=f"RSI 과매도 ({rsi_value:.2f} < {self._oversold})",
                    quantity=quantity,
                    metadata={"rsi": rsi_value, "current_price": current_price},
                )

            # 매도 신호: RSI 과매수 구간 AND 포지션 보유 중
            if rsi_value > self._overbought and current_position and current_position.quantity > 0:
                return Signal(
                    type=SignalType.SELL,
                    symbol=symbol,
                    reason=f"RSI 과매수 ({rsi_value:.2f} > {self._overbought})",
                    quantity=current_position.quantity,
                    metadata={"rsi": rsi_value, "current_price": current_price},
                )

            return Signal(
                type=SignalType.HOLD,
                symbol=symbol,
                reason=f"RSI 중립 ({rsi_value:.2f})",
                metadata={"rsi": rsi_value},
            )

        except Exception as exc:
            raise StrategyError(
                message=f"{symbol} RSI 신호 생성 오류: {exc}",
                strategy_name="RSIStrategy",
            ) from exc
