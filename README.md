# 한국 주식 시스템 트레이딩 스타터킷

Kiwoom REST API + Python asyncio 기반의 한국 주식 시스템 트레이딩 스타터킷입니다.
전략 교체가 쉽고 Paper Trading 모드를 지원하는 프로덕션 레디 템플릿입니다.

## 주요 기능

- **Kiwoom REST API 연동**: 토큰 자동 갱신, TR 요청 속도 제한 (초당 5회)
- **Paper Trading 모드**: `TRADING__DRY_RUN=true` 설정으로 실제 주문 없이 전략 검증
- **전략 확장**: `BaseStrategy` 추상 클래스 상속으로 새 전략 쉽게 추가
- **RSI 전략 예시**: RSI < 30 매수, RSI > 70 매도
- **위험 관리**: 종목당/전체 투자 한도 체크
- **비동기 스케줄링**: APScheduler 기반 장 시작/종료 자동 처리
- **텔레그램 알림**: 매매 신호, 에러, 일간 요약 알림
- **SQLite 이력 관리**: 주문/거래 이력 영속화

## 기술 스택

| 역할 | 라이브러리 |
|---|---|
| HTTP 클라이언트 | httpx |
| 데이터 모델 | pydantic v2 |
| 설정 관리 | pydantic-settings |
| 스케줄링 | apscheduler (AsyncIOScheduler) |
| 데이터 분석 | pandas, numpy |
| 기술 지표 | ta |
| DB | aiosqlite (SQLite) |
| 알림 | python-telegram-bot |
| 로깅 | loguru |

## 빠른 시작

### 1. 환경 구성

```bash
# uv 설치 (없는 경우)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 프로젝트 초기화
uv sync

# 환경변수 설정
cp .env.example .env
# .env 파일에 Kiwoom API 키 입력
```

### 2. 설정 확인

```bash
uv run python -c "from trading_bot.config.settings import settings; print(settings.trading.dry_run)"
```

### 3. Paper Trading 실행

```bash
# DRY_RUN=true 상태에서 실행 (실제 주문 미실행)
uv run python -m trading_bot.main
```

### 4. 실거래 실행

```bash
# .env에서 TRADING__DRY_RUN=false 설정 후 실행
TRADING__DRY_RUN=false uv run python -m trading_bot.main
```

## 새 전략 추가

```python
# trading_bot/strategy/my_strategy.py
from trading_bot.strategy.base import BaseStrategy, Signal, SignalType
from trading_bot.api.models import OHLCVBar, Position
import pandas as pd

class MyStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "my_strategy"

    @property
    def symbols(self) -> list[str]:
        return ["005930"]  # 삼성전자

    async def initialize(self) -> None:
        pass

    async def generate_signal(
        self,
        symbol: str,
        ohlcv: list[OHLCVBar],
        current_position: Position | None,
    ) -> Signal:
        # 매매 로직 구현
        return Signal(type=SignalType.HOLD, symbol=symbol, reason="조건 미충족")
```

```python
# main.py에서 전략 교체
from trading_bot.strategy.my_strategy import MyStrategy
strategy = MyStrategy(settings=settings)
```

## 테스트

```bash
# 단위 테스트
uv run pytest tests/unit/ -v

# 통합 테스트
uv run pytest tests/integration/ -v

# 전체 테스트
uv run pytest -v
```

## 린트

```bash
uv run ruff check trading_bot/
uv run ruff format trading_bot/
```

## 디렉토리 구조

```
trading_bot/
├── main.py                     # 진입점
├── config/settings.py          # 중앙 설정
├── api/
│   ├── kiwoom_client.py        # API 클라이언트
│   ├── rate_limiter.py         # TR 속도 제한
│   └── models.py               # 요청/응답 모델
├── strategy/
│   ├── base.py                 # 추상 전략 클래스
│   └── rsi_strategy.py         # RSI 전략 예시
├── execution/
│   ├── order_manager.py        # 주문 실행
│   └── position_tracker.py     # 포지션 추적
├── data/
│   ├── market_data.py          # OHLCV 수집
│   └── indicators.py           # 기술 지표
├── db/
│   ├── database.py             # DB 연결/스키마
│   └── repositories.py         # CRUD
├── notification/
│   └── telegram_bot.py         # 텔레그램 알림
├── scheduler/
│   └── job_scheduler.py        # 스케줄러
└── utils/
    ├── logger.py               # 로깅
    └── exceptions.py           # 커스텀 예외
```

## 주의사항

- 실거래 전 반드시 Paper Trading 모드로 충분히 검증하세요.
- API 키, 시크릿은 절대 코드에 하드코딩하지 마세요.
- Kiwoom API는 TR 요청 횟수 제한이 있습니다 (초당 5회).
- 투자에 대한 책임은 사용자 본인에게 있습니다.
