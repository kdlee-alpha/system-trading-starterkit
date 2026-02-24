"""골든 크로스(이동평균선 돌파) 기반 추세 추종 전략"""

from loguru import logger

from trading_bot.api.models import OHLCVBar, Position
from trading_bot.config.settings import settings
from trading_bot.strategy.base import BaseStrategy, Signal, SignalType
from trading_bot.utils.exceptions import StrategyError


class GoldenCrossOfMovingAverageStrategy(BaseStrategy):
    """
    이동평균선 골든 크로스/데드 크로스 매매 전략

    - 매수 (골든 크로스): 직전 봉에서 단기 MA ≤ 장기 MA였다가, 현재 봉에서 단기 MA > 장기 MA로 상향 돌파
    - 매도 (데드 크로스): 직전 봉에서 단기 MA ≥ 장기 MA였다가, 현재 봉에서 단기 MA < 장기 MA로 하향 돌파
    - 데이터 부족 → HOLD 반환
    """

    # 크로스 감지를 위해 직전/현재 MA 값 2개가 필요하므로 +2
    _MIN_BARS_OFFSET = 2

    def __init__(
        self,
        short_period: int = 5,
        long_period: int = 20,
    ) -> None:
        """
        Args:
            short_period: 단기 이동평균 기간 (기본 5)
            long_period: 장기 이동평균 기간 (기본 20)
        """
        if short_period >= long_period:
            raise ValueError(
                f"short_period({short_period})는 long_period({long_period})보다 작아야 합니다."
            )
        self._short_period = short_period
        self._long_period = long_period
        self._min_bars = long_period + self._MIN_BARS_OFFSET
        self._max_position_size = settings.trading.max_position_size

    def _calculate_sma(self, closes: list[float], period: int) -> float:
        """단순 이동평균(SMA) 계산

        Args:
            closes: 종가 리스트 (오름차순, 최신값이 마지막)
            period: 이동평균 기간

        Returns:
            최신 봉 기준 SMA 값
        """
        return sum(closes[-period:]) / period

    def _should_buy(self, closes: list[float]) -> bool:
        """골든 크로스 감지: 단기 MA가 장기 MA를 상향 돌파했는지 확인

        Args:
            closes: 종가 리스트 (오름차순, 최신값이 마지막)
        """
        # 현재 봉 MA
        current_short = self._calculate_sma(closes, self._short_period)
        current_long = self._calculate_sma(closes, self._long_period)

        # 직전 봉 MA (마지막 원소 제외)
        prev_closes = closes[:-1]
        prev_short = self._calculate_sma(prev_closes, self._short_period)
        prev_long = self._calculate_sma(prev_closes, self._long_period)

        # 직전: 단기 ≤ 장기, 현재: 단기 > 장기 → 골든 크로스
        return prev_short <= prev_long and current_short > current_long

    def _should_sell(self, closes: list[float]) -> bool:
        """데드 크로스 감지: 단기 MA가 장기 MA를 하향 돌파했는지 확인

        Args:
            closes: 종가 리스트 (오름차순, 최신값이 마지막)
        """
        # 현재 봉 MA
        current_short = self._calculate_sma(closes, self._short_period)
        current_long = self._calculate_sma(closes, self._long_period)

        # 직전 봉 MA
        prev_closes = closes[:-1]
        prev_short = self._calculate_sma(prev_closes, self._short_period)
        prev_long = self._calculate_sma(prev_closes, self._long_period)

        # 직전: 단기 ≥ 장기, 현재: 단기 < 장기 → 데드 크로스
        return prev_short >= prev_long and current_short < current_long

    async def generate_signal(
        self,
        symbol: str,
        ohlcv: list[OHLCVBar],
        current_position: Position | None,
    ) -> Signal:
        """골든 크로스/데드 크로스 기반 매매 신호 생성"""
        try:
            # 데이터 부족 확인
            if len(ohlcv) < self._min_bars:
                return Signal(
                    type=SignalType.HOLD,
                    symbol=symbol,
                    reason=f"데이터 부족 ({len(ohlcv)}봉, 최소 {self._min_bars}봉 필요)",
                )

            # OHLCV → 종가 리스트 변환 (시간 오름차순 정렬)
            closes = [bar.close for bar in reversed(ohlcv)]

            # 현재 MA 값 (로그용)
            current_short_ma = self._calculate_sma(closes, self._short_period)
            current_long_ma = self._calculate_sma(closes, self._long_period)
            current_price = ohlcv[0].close  # 최신 종가

            logger.debug(
                f"{symbol} 단기MA({self._short_period})={current_short_ma:,.0f}, "
                f"장기MA({self._long_period})={current_long_ma:,.0f}, "
                f"현재가={current_price:,.0f}"
            )

            # 매수 신호: 골든 크로스
            if self._should_buy(closes):
                quantity = int(self._max_position_size // current_price)
                if quantity <= 0:
                    return Signal(
                        type=SignalType.HOLD,
                        symbol=symbol,
                        reason="골든 크로스 감지 - 최대 포지션 대비 수량 0",
                        metadata={
                            "short_ma": current_short_ma,
                            "long_ma": current_long_ma,
                        },
                    )
                return Signal(
                    type=SignalType.BUY,
                    symbol=symbol,
                    reason=(
                        f"골든 크로스 (단기MA {current_short_ma:,.0f} > 장기MA {current_long_ma:,.0f})"
                    ),
                    quantity=quantity,
                    metadata={
                        "short_ma": current_short_ma,
                        "long_ma": current_long_ma,
                        "current_price": current_price,
                    },
                )

            # 매도 신호: 데드 크로스 AND 포지션 보유 중
            if self._should_sell(closes) and current_position and current_position.quantity > 0:
                return Signal(
                    type=SignalType.SELL,
                    symbol=symbol,
                    reason=(
                        f"데드 크로스 (단기MA {current_short_ma:,.0f} < 장기MA {current_long_ma:,.0f})"
                    ),
                    quantity=current_position.quantity,
                    metadata={
                        "short_ma": current_short_ma,
                        "long_ma": current_long_ma,
                        "current_price": current_price,
                    },
                )

            return Signal(
                type=SignalType.HOLD,
                symbol=symbol,
                reason=(
                    f"크로스 없음 (단기MA {current_short_ma:,.0f}, 장기MA {current_long_ma:,.0f})"
                ),
                metadata={
                    "short_ma": current_short_ma,
                    "long_ma": current_long_ma,
                },
            )

        except Exception as exc:
            raise StrategyError(
                message=f"{symbol} 골든 크로스 신호 생성 오류: {exc}",
                strategy_name="GoldenCrossOfMovingAverageStrategy",
            ) from exc
