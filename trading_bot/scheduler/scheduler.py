"""트레이딩 스케줄러"""

from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from trading_bot.api.kiwoom_client import KiwoomClient
from trading_bot.config.settings import settings
from trading_bot.execution.order_manager import OrderManager
from trading_bot.execution.position_tracker import PositionTracker
from trading_bot.notification.telegram_notifier import TelegramNotifier
from trading_bot.strategy.base import BaseStrategy

# 한국 표준시 (KST = UTC+9)
KST = ZoneInfo("Asia/Seoul")

# 시장 개장/마감 시간 (KST)
_MARKET_OPEN_HOUR = 9
_MARKET_OPEN_MINUTE = 0
_MARKET_CLOSE_HOUR = 15
_MARKET_CLOSE_MINUTE = 30


class TradingScheduler:
    """
    트레이딩 스케줄러

    - 매매 신호 생성/실행 (tick_interval_seconds 주기)
    - 일일 요약 (매일 16:00 KST)
    - 포지션 동기화 (5분 주기)
    """

    def __init__(
        self,
        client: KiwoomClient,
        strategy: BaseStrategy,
        order_manager: OrderManager,
        position_tracker: PositionTracker,
        notifier: TelegramNotifier,
        symbols: list[str],
    ) -> None:
        self._client = client
        self._strategy = strategy
        self._order_manager = order_manager
        self._position_tracker = position_tracker
        self._notifier = notifier
        self._symbols = symbols
        self._tick_interval = settings.scheduler.tick_interval_seconds

        self._scheduler = AsyncIOScheduler(timezone=KST)

    async def start(self) -> None:
        """스케줄러 시작 (3개 Job 등록)"""
        # 1. 전략 tick - 매매 신호 생성 및 실행
        self._scheduler.add_job(
            self._strategy_tick,
            trigger=IntervalTrigger(seconds=self._tick_interval),
            id="strategy_tick",
            max_instances=1,  # 중복 실행 방지
            misfire_grace_time=30,
        )

        # 2. 일일 요약 - 매일 16:00 KST
        self._scheduler.add_job(
            self._daily_summary,
            trigger=CronTrigger(hour=16, minute=0, timezone=KST),
            id="daily_summary",
            max_instances=1,
        )

        # 3. 포지션 동기화 - 5분 주기
        self._scheduler.add_job(
            self._sync_positions,
            trigger=IntervalTrigger(minutes=5),
            id="sync_positions",
            max_instances=1,
        )

        self._scheduler.start()
        logger.info(
            f"스케줄러 시작 (tick={self._tick_interval}초, 종목={self._symbols})"
        )

    async def stop(self) -> None:
        """스케줄러 종료"""
        self._scheduler.shutdown(wait=True)
        logger.info("스케줄러 종료")

    async def _strategy_tick(self) -> None:
        """
        핵심 매매 로직 (주기적 실행)

        - 시장 시간 외 스킵
        - 종목별 OHLCV 조회 → 신호 생성 → 주문 실행
        - 개별 종목 오류 격리 (한 종목 실패가 전체 중단 방지)
        """
        if not self.is_market_hours():
            logger.debug("시장 시간 외 - 전략 tick 스킵")
            return

        logger.debug(f"전략 tick 시작: {len(self._symbols)}개 종목")

        for symbol in self._symbols:
            try:
                # OHLCV 조회 (RSI 기본값 14 기간 + 여유분)
                ohlcv = await self._client.get_ohlcv(symbol, "1D", 50)
                if not ohlcv:
                    logger.warning(f"{symbol} OHLCV 데이터 없음 - 스킵")
                    continue

                # 현재 포지션 조회 (캐시)
                current_position = self._position_tracker.get_current_position(symbol)

                # 신호 생성
                signal = await self._strategy.generate_signal(symbol, ohlcv, current_position)
                logger.info(f"{symbol} 신호: {signal.type} - {signal.reason}")

                # 신호 알림
                await self._notifier.send_signal(signal)

                # 주문 실행
                order = await self._order_manager.execute_signal(signal)

                if order is not None:
                    await self._notifier.send_order_result(order)
                    await self._strategy.on_order_filled(symbol, signal)

            except Exception as exc:
                # 종목별 오류 격리 - 다른 종목 처리 계속
                logger.error(f"{symbol} 처리 오류: {exc}")
                await self._notifier.send_error(exc, context=f"{symbol} 전략 tick")

        logger.debug("전략 tick 완료")

    async def _daily_summary(self) -> None:
        """일일 요약 알림 발송 (매일 16:00 KST)"""
        try:
            logger.info("일일 요약 생성 중...")
            balance = await self._client.get_account_balance()

            # 오늘 거래 기록 조회는 알림 모듈에서 처리
            await self._notifier.send_daily_summary(balance, [])
            logger.info("일일 요약 발송 완료")

        except Exception as exc:
            logger.error(f"일일 요약 생성 실패: {exc}")

    async def _sync_positions(self) -> None:
        """포지션 동기화 (5분 주기)"""
        try:
            positions = await self._position_tracker.update_positions()
            logger.debug(f"포지션 동기화: {len(positions)}개 종목")
        except Exception as exc:
            logger.error(f"포지션 동기화 실패: {exc}")

    @staticmethod
    def is_market_hours() -> bool:
        """
        현재 시각이 주식 시장 운영 시간인지 확인

        한국 주식시장: 평일 09:00 ~ 15:30 KST

        Returns:
            True (시장 운영 중)
        """
        now = datetime.now(tz=KST)

        # 주말 제외 (weekday 0=월 ~ 6=일)
        if now.weekday() >= 5:
            return False

        open_time = now.replace(
            hour=_MARKET_OPEN_HOUR,
            minute=_MARKET_OPEN_MINUTE,
            second=0,
            microsecond=0,
        )
        close_time = now.replace(
            hour=_MARKET_CLOSE_HOUR,
            minute=_MARKET_CLOSE_MINUTE,
            second=0,
            microsecond=0,
        )

        return open_time <= now <= close_time
