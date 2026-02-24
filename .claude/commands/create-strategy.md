새로운 트레이딩 전략을 생성합니다. `$ARGUMENTS`를 전략 이름으로 사용합니다.

## 작업 순서

### 1단계: 이름 파싱

`$ARGUMENTS`에서 전략 이름을 추출합니다.

- **입력 예시**: `MovingAverage` 또는 `moving_average`
- **클래스명**: PascalCase로 정규화 (예: `MovingAverageStrategy`)
  - 이미 `Strategy`로 끝나면 그대로 사용, 아니면 `Strategy` 접미사 추가
- **파일명**: snake_case로 변환 (예: `moving_average_strategy.py`)
- **파일 경로**: `trading_bot/strategy/{snake_case}.py`

PascalCase → snake_case 변환 규칙:
- 대문자 앞에 `_` 삽입 후 소문자화 (예: `MovingAverage` → `moving_average`)
- 이미 snake_case면 그대로 사용

### 2단계: 참조 파일 확인

다음 파일들을 읽어 현재 패턴을 파악합니다:
- `trading_bot/strategy/base.py` — `BaseStrategy`, `Signal`, `SignalType` 정의 확인
- `trading_bot/strategy/rsi_strategy.py` — 구현 패턴 레퍼런스
- `trading_bot/utils/exceptions.py` — `StrategyError` 시그니처 확인
- `trading_bot/main.py` — import 및 인스턴스화 위치 확인

### 3단계: 전략 파일 생성

`trading_bot/strategy/{snake_case}.py` 파일을 생성합니다.

**보일러플레이트 구조** (RSIStrategy 패턴 기반):

```python
"""{전략 설명} 전략"""

from loguru import logger

from trading_bot.api.models import OHLCVBar, Position
from trading_bot.config.settings import settings
from trading_bot.strategy.base import BaseStrategy, Signal, SignalType
from trading_bot.utils.exceptions import StrategyError

# 최소 데이터 요구 봉 수 (전략에 맞게 조정)
MIN_BARS = 20


class {StrategyName}(BaseStrategy):
    """
    {전략 설명}

    - 매수: TODO - 매수 조건 설명
    - 매도: TODO - 매도 조건 설명
    - 데이터 부족 → HOLD 반환
    """

    def __init__(
        self,
        # TODO: 전략 파라미터 추가 (예: period: int = 20)
    ) -> None:
        """
        Args:
            TODO: 파라미터 설명
        """
        # settings에서 최대 포지션 크기 로드
        self._max_position_size = settings.trading.max_position_size

    def should_buy(
        self,
        symbol: str,
        ohlcv: list[OHLCVBar],
        current_position: Position | None,
    ) -> tuple[bool, str]:
        """
        매수 조건 판단

        Args:
            symbol: 종목 코드
            ohlcv: OHLCV 봉 데이터 (최신 기준 내림차순)
            current_position: 현재 보유 포지션

        Returns:
            (매수 여부, 사유 메시지)
        """
        # TODO: 매수 조건 구현
        # 예시: 특정 지표가 임계값 이하일 때 매수
        return False, "TODO: 매수 조건 미구현"

    def should_sell(
        self,
        symbol: str,
        ohlcv: list[OHLCVBar],
        current_position: Position | None,
    ) -> tuple[bool, str]:
        """
        매도 조건 판단

        Args:
            symbol: 종목 코드
            ohlcv: OHLCV 봉 데이터 (최신 기준 내림차순)
            current_position: 현재 보유 포지션

        Returns:
            (매도 여부, 사유 메시지)
        """
        # 포지션 없으면 매도 불필요
        if not current_position or current_position.quantity <= 0:
            return False, "보유 포지션 없음"

        # TODO: 매도 조건 구현
        # 예시: 특정 지표가 임계값 이상일 때 매도
        return False, "TODO: 매도 조건 미구현"

    async def generate_signal(
        self,
        symbol: str,
        ohlcv: list[OHLCVBar],
        current_position: Position | None,
    ) -> Signal:
        """{전략 설명} 기반 매매 신호 생성"""
        try:
            # 데이터 부족 확인
            if len(ohlcv) < MIN_BARS:
                return Signal(
                    type=SignalType.HOLD,
                    symbol=symbol,
                    reason=f"데이터 부족 ({len(ohlcv)}봉, 최소 {MIN_BARS}봉 필요)",
                )

            current_price = ohlcv[0].close  # 최신 종가

            logger.debug(f"{symbol} 현재가={current_price:,.0f}")

            # 매수 신호 확인
            buy_signal, buy_reason = self.should_buy(symbol, ohlcv, current_position)
            if buy_signal:
                # 최대 포지션 크기 기준 수량 계산
                quantity = int(self._max_position_size // current_price)
                if quantity <= 0:
                    return Signal(
                        type=SignalType.HOLD,
                        symbol=symbol,
                        reason=f"{buy_reason} - 최대 포지션 대비 수량 0",
                    )
                return Signal(
                    type=SignalType.BUY,
                    symbol=symbol,
                    reason=buy_reason,
                    quantity=quantity,
                    metadata={"current_price": current_price},
                )

            # 매도 신호 확인
            sell_signal, sell_reason = self.should_sell(symbol, ohlcv, current_position)
            if sell_signal and current_position:
                return Signal(
                    type=SignalType.SELL,
                    symbol=symbol,
                    reason=sell_reason,
                    quantity=current_position.quantity,
                    metadata={"current_price": current_price},
                )

            return Signal(
                type=SignalType.HOLD,
                symbol=symbol,
                reason="조건 미충족",
                metadata={"current_price": current_price},
            )

        except Exception as exc:
            raise StrategyError(
                message=f"{symbol} {StrategyName} 신호 생성 오류: {exc}",
                strategy_name="{StrategyName}",
            ) from exc
```

**생성 시 주의사항:**
- `{StrategyName}`, `{전략 설명}` 등의 플레이스홀더를 실제 이름으로 치환
- `StrategyError` 메시지의 `strategy_name`에도 실제 클래스명 사용
- 한국어 주석 유지
- `TODO` 마커로 구현 필요 부분 명시

### 4단계: main.py 수정

`trading_bot/main.py`에서 두 곳을 수정합니다.

**수정 1 — import 라인 교체:**
```python
# 변경 전
from trading_bot.strategy.rsi_strategy import RSIStrategy

# 변경 후
from trading_bot.strategy.{snake_case} import {StrategyName}
```

**수정 2 — 전략 인스턴스화 교체:**
```python
# 변경 전
strategy = RSIStrategy()

# 변경 후
strategy = {StrategyName}()
```

### 5단계: 완료 보고

작업 완료 후 다음을 보고합니다:

1. 생성된 파일 경로: `trading_bot/strategy/{snake_case}.py`
2. `main.py` 변경 내용 요약
3. 다음 단계 안내:
   - `should_buy()` / `should_sell()` 메서드에 전략 로직 구현
   - 필요한 파라미터를 `__init__`에 추가
   - `MIN_BARS` 상수를 전략에 맞게 조정
   - `uv run ruff check trading_bot/` 로 린트 확인
   - `uv run python -m trading_bot.main` 으로 임포트 오류 없는지 확인
