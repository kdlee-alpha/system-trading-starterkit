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

- **`trading_bot/main.py`**: 진입점. 모든 컴포넌트 초기화 및 의존성 주입
- **`trading_bot/config/settings.py`**: Pydantic Settings. 환경 변수 `__` 구분자로 중첩 설정 (예: `KIWOOM__BASE_URL`)
- **`trading_bot/api/kiwoom_client.py`**: 비동기 HTTP 클라이언트. 자동 토큰 갱신(만료 5분 전), 재시도 로직
- **`trading_bot/api/rate_limiter.py`**: 슬라이딩 윈도우 방식 TR 요청 제한 (초당 5회)
- **`trading_bot/strategy/base.py`**: `BaseStrategy` 추상 클래스. 커스텀 전략 구현 시 상속
- **`trading_bot/execution/risk_manager.py`**: 주문 전 리스크 검증. 포지션 한도 및 총 노출 한도 체크
- **`trading_bot/db/repositories.py`**: Repository 패턴. orders/trades/positions 테이블 CRUD
- **`trading_bot/scheduler/scheduler.py`**: 장 시간(KST 09:00-15:30) 감지 및 주기적 틱 실행
- **`trading_bot/utils/exceptions.py`**: 커스텀 예외 계층 구조 (`TradingBotError` → `ApiError`, `OrderError` 등)

### 커스텀 전략 추가

`trading_bot/strategy/base.py`의 `BaseStrategy`를 상속하여 `generate_signal()` 메서드 구현:

```python
from trading_bot.strategy.base import BaseStrategy, Signal

class MyStrategy(BaseStrategy):
    async def generate_signal(self, symbol: str) -> Signal | None:
        # 매수/매도 시그널 반환 로직 구현
        ...
```

### 환경 변수 구조

중첩 설정은 `__`로 구분:
- `KIWOOM__APP_KEY`, `KIWOOM__APP_SECRET`, `KIWOOM__BASE_URL`
- `TRADING__DRY_RUN` (페이퍼 트레이딩 토글), `TRADING__MAX_POSITION_SIZE`, `TRADING__MAX_TOTAL_EXPOSURE`
- `TELEGRAM__BOT_TOKEN`, `TELEGRAM__CHAT_ID`
- `DB__PATH` (SQLite 파일 경로)

### 로깅

3채널 출력: 콘솔 / 파일(로테이션) / Telegram(ERROR 이상). `trading_bot/utils/logger.py`에서 Loguru 설정.

### DB 스키마

SQLite WAL 모드. 테이블: `orders`, `trades`, `positions`. DDL은 `trading_bot/db/schema.py` 참조.
