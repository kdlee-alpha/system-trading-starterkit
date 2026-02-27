# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

키움증권 REST API 기반 한국 주식 시장 자동매매 봇 스타터킷. Python 3.12+, 완전 비동기(asyncio) 설계.

## 개발 환경 설정

```bash
# 의존성 설치
uv sync

# 환경 변수 설정
cp .env.example .env
# .env 파일에서 KIWOOM_*, TRADING_*, TELEGRAM_* 값 설정
```

## 주요 명령어

```bash
# 봇 실행 (페이퍼 트레이딩)
TRADING__DRY_RUN=true uv run python -m trading_bot.main

# 테스트
uv run pytest tests/ -v
uv run pytest tests/unit/ -v          # 단위 테스트
uv run pytest tests/integration/ -v   # 통합 테스트
uv run pytest tests/ -k "test_name"   # 단일 테스트 실행
uv run pytest tests/unit/strategy/ -v # 전략 단위 테스트만 실행

# 린트 & 포맷
uv run ruff check trading_bot/
uv run ruff format trading_bot/
```

## 아키텍처

### 레이어 구조

```
Scheduler (APScheduler)
    └── Strategy (BaseStrategy 추상 클래스)
            ├── MarketDataHandler (OHLCV 조회)
            ├── RiskManager (포지션/노출 한도 검증)
            └── OrderManager (주문 실행)
                    ├── KiwoomClient (키움 REST API)
                    ├── PositionTracker (인메모리 캐시 + API 동기화)
                    └── Repository (SQLite CRUD)
```

### 핵심 모듈

- **`trading_bot/main.py`**: 진입점. 모든 컴포넌트 초기화 및 의존성 주입. `symbols` 리스트에서 감시 종목 변경 가능 (기본: 삼성전자 005930, SK하이닉스 000660, NAVER 035420)
- **`trading_bot/config/settings.py`**: Pydantic Settings. 환경 변수 `__` 구분자로 중첩 설정 (예: `KIWOOM__BASE_URL`)
- **`trading_bot/api/kiwoom_client.py`**: 비동기 HTTP 클라이언트. 자동 토큰 갱신(만료 5분 전), 재시도 로직
- **`trading_bot/api/rate_limiter.py`**: 슬라이딩 윈도우 방식 TR 요청 제한 (초당 5회)
- **`trading_bot/strategy/base.py`**: `BaseStrategy` 추상 클래스. 커스텀 전략 구현 시 상속
- **`trading_bot/strategy/rsi_strategy.py`**: RSI 기반 역추세 전략 구현체
- **`trading_bot/strategy/golden_cross_of_moving_average_strategy.py`**: 이동평균 골든크로스/데드크로스 전략 구현체
- **`trading_bot/data/indicators.py`**: 기술 지표 계산 유틸리티 (RSI, SMA, EMA, 볼린저 밴드). `ta` 라이브러리 기반
- **`trading_bot/execution/risk_manager.py`**: 주문 전 리스크 검증. 포지션 한도 및 총 노출 한도 체크
- **`trading_bot/notification/telegram_notifier.py`**: 텔레그램 알림 전송. 주문 체결, 오류 등 이벤트 알림
- **`trading_bot/db/repositories.py`**: Repository 패턴. orders/trades/positions 테이블 CRUD
- **`trading_bot/scheduler/scheduler.py`**: 장 시간(KST 09:00-15:30) 감지 및 주기적 틱 실행
- **`trading_bot/utils/exceptions.py`**: 커스텀 예외 계층 구조 (`TradingBotError` → `ApiError`, `OrderError`, `StrategyError` 등)

## 환경 변수

중첩 설정은 `__`로 구분 (`.env.example` 참조):

```bash
# Kiwoom REST API
KIWOOM__APP_KEY=your_app_key_here
KIWOOM__APP_SECRET=your_app_secret_here
KIWOOM__ACCOUNT_NUMBER=your_account_number_here
KIWOOM__BASE_URL=https://mockapi.kiwoom.com  # 모의투자 (실거래: https://api.kiwoom.com)

# 트레이딩
TRADING__DRY_RUN=true                        # Paper Trading 모드
TRADING__MAX_POSITION_SIZE=1000000           # 종목당 최대 투자금액 (원)
TRADING__MAX_TOTAL_EXPOSURE=5000000          # 전체 최대 투자금액 (원)

# 스케줄러
SCHEDULER__TICK_INTERVAL_SECONDS=60          # 전략 실행 주기 (초)

# 텔레그램 알림 (선택사항)
TELEGRAM__BOT_TOKEN=your_telegram_bot_token
TELEGRAM__CHAT_ID=your_telegram_chat_id

# 로깅
LOG__LEVEL=INFO                              # DEBUG, INFO, WARNING, ERROR, CRITICAL

# DB
DB__PATH=data/trading.db                     # SQLite 파일 경로
```

## 커스텀 전략 추가 가이드

### 올바른 generate_signal 시그니처

`trading_bot/strategy/base.py`의 `BaseStrategy`를 상속하고 `generate_signal()` 메서드를 구현한다. **반환 타입은 `Signal`이며 항상 반환해야 함** (HOLD Signal 포함, `None` 반환 불가).

```python
from trading_bot.api.models import OHLCVBar, Position
from trading_bot.strategy.base import BaseStrategy, Signal, SignalType
from trading_bot.utils.exceptions import StrategyError

class MyStrategy(BaseStrategy):
    async def generate_signal(
        self,
        symbol: str,
        ohlcv: list[OHLCVBar],           # 최신 기준 내림차순 정렬
        current_position: Position | None,
    ) -> Signal:
        try:
            # 매수/매도/홀드 시그널 반환 로직 구현
            return Signal(type=SignalType.HOLD, symbol=symbol, reason="조건 미충족")
        except Exception as exc:
            raise StrategyError(message=f"{symbol} 신호 생성 오류: {exc}", strategy_name="MyStrategy") from exc
```

### Signal 모델

```python
@dataclass
class Signal:
    type: SignalType            # BUY | SELL | HOLD
    symbol: str                 # 종목 코드 (예: "005930")
    reason: str                 # 신호 발생 이유 (로그/알림용)
    quantity: int = 0           # 주문 수량 (HOLD 시 0)
    price: float | None = None  # 지정가 가격 (None이면 시장가)
    metadata: dict[str, float | int | str] = field(default_factory=dict)  # 지표 값 등 부가 정보
```

### 선택적 오버라이드 메서드

```python
async def initialize(self) -> None:
    """봇 시작 시 1회 호출 (선택적 오버라이드)"""
    ...

async def on_order_filled(self, symbol: str, signal: Signal) -> None:
    """주문 체결 시 호출 (선택적 오버라이드)"""
    ...
```

### 기술 지표 유틸리티

`trading_bot/data/indicators.py`에서 import하여 사용:

```python
import pandas as pd
from trading_bot.data.indicators import calculate_rsi, calculate_sma, calculate_ema, calculate_bollinger_bands

# OHLCV → 종가 Series 변환 (오름차순 정렬 필요)
closes = pd.Series([bar.close for bar in reversed(ohlcv)], dtype=float)

rsi = calculate_rsi(closes, period=14)                                         # RSI
sma = calculate_sma(closes, period=20)                                         # 단순이동평균
ema = calculate_ema(closes, period=12)                                         # 지수이동평균
upper, mid, lower = calculate_bollinger_bands(closes, period=20, num_std=2.0)  # 볼린저 밴드
```

> **주의**: `ohlcv`는 최신 기준 내림차순이므로 `reversed(ohlcv)`로 오름차순 변환 후 지표 계산.

### 구현된 전략 (레퍼런스)

| 전략 | 파일 | 설명 |
|------|------|------|
| `RSIStrategy` | `trading_bot/strategy/rsi_strategy.py` | RSI 과매도/과매수 역추세 전략 |
| `GoldenCrossOfMovingAverageStrategy` | `trading_bot/strategy/golden_cross_of_moving_average_strategy.py` | 이동평균 골든크로스/데드크로스 추세 추종 전략 |

### main.py에 전략 등록

```python
# trading_bot/main.py에서 전략 교체
from trading_bot.strategy.my_strategy import MyStrategy

strategy = MyStrategy()  # 파라미터는 전략별로 다름
```

## 테스트

### 설정 (pyproject.toml)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"   # @pytest.mark.asyncio 데코레이터 불필요
testpaths = ["tests"]
```

### 전략 테스트 패턴

```python
"""전략 단위 테스트 - tests/unit/strategy/test_my_strategy.py"""
import pytest
from unittest.mock import MagicMock
from trading_bot.api.models import OHLCVBar, Position
from trading_bot.strategy.my_strategy import MyStrategy
from trading_bot.strategy.base import SignalType

@pytest.fixture
def strategy():
    return MyStrategy()

@pytest.fixture
def sample_ohlcv():
    """테스트용 OHLCV 데이터 (최신 기준 내림차순)"""
    return [MagicMock(spec=OHLCVBar, close=float(100 - i)) for i in range(30)]

async def test_매수_신호(strategy, sample_ohlcv):
    signal = await strategy.generate_signal("005930", sample_ohlcv, None)
    assert signal.type == SignalType.BUY

async def test_데이터_부족시_hold(strategy):
    signal = await strategy.generate_signal("005930", [], None)
    assert signal.type == SignalType.HOLD
```

## Claude Code 통합

### Hooks (`.claude/hooks/`)

- **`protect_env.py`**: `.env` 파일 수정 시도를 차단 (PreToolUse 훅)
- **`telegram_notify.py`**: 도구 실행 결과를 텔레그램으로 알림 (PostToolUse 훅)

### strategy-builder 에이전트

자연어로 전략 생성 요청 시 자동으로 활성화되는 전문 에이전트:
- "RSI 30 이하 매수 전략 만들어줘" 등의 요청에 반응
- 전략 파일 + 테스트 파일 동시 생성
- 정의: `.claude/agents/strategy-builder.md`

### /create-strategy 명령어

전략 보일러플레이트 파일 생성:

```bash
/create-strategy MyStrategyName
```

- `trading_bot/strategy/my_strategy_name.py` 생성
- `trading_bot/main.py` import 및 인스턴스화 교체
- 정의: `.claude/commands/create-strategy.md`

## 로깅

3채널 출력: 콘솔 / 파일(로테이션) / Telegram(ERROR 이상). `trading_bot/utils/logger.py`에서 Loguru 설정.

## DB 스키마

SQLite WAL 모드. 테이블: `orders`, `trades`, `positions`. DDL은 `trading_bot/db/schema.py` 참조.
