"""트레이딩 봇 진입점"""

import asyncio
import signal
from typing import Any

from loguru import logger

from trading_bot.api.kiwoom_client import KiwoomClient
from trading_bot.config.settings import settings
from trading_bot.db.connection import DatabaseManager
from trading_bot.db.repositories import OrderRepository, PositionRepository, TradeRepository
from trading_bot.execution.order_manager import OrderManager
from trading_bot.execution.position_tracker import PositionTracker
from trading_bot.execution.risk_manager import RiskManager
from trading_bot.notification.telegram_notifier import TelegramNotifier
from trading_bot.scheduler.scheduler import TradingScheduler
from trading_bot.strategy.rsi_strategy import RSIStrategy
from trading_bot.utils.logger import setup_logger


async def main() -> None:
    """
    트레이딩 봇 메인 함수

    초기화 순서:
    1. 로거 설정
    2. 데이터베이스 초기화 (DDL 실행)
    3. 레포지토리 생성
    4. API 클라이언트 초기화 (async with)
    5. 실행 컴포넌트 조립
    6. 포지션 동기화
    7. SIGINT/SIGTERM 핸들러 등록
    8. 스케줄러 시작 및 종료 대기
    """
    # 1. 로거 설정
    setup_logger(
        log_level=settings.log.level,
        bot_token=settings.telegram.bot_token,
        chat_id=settings.telegram.chat_id,
    )

    mode_label = "[DRY_RUN]" if settings.trading.dry_run else "[실거래]"
    logger.info(f"트레이딩 봇 시작 {mode_label}")
    logger.info(f"API URL: {settings.kiwoom.base_url}")

    # 2. 데이터베이스 초기화
    db_manager = DatabaseManager(settings.db.path)
    await db_manager.initialize()

    # 3. 레포지토리 생성
    order_repo = OrderRepository(db_manager)
    trade_repo = TradeRepository(db_manager)
    position_repo = PositionRepository(db_manager)

    # 4. API 클라이언트 초기화
    async with KiwoomClient() as client:
        # 5. 실행 컴포넌트 조립
        risk_manager = RiskManager()
        position_tracker = PositionTracker(client, position_repo)
        order_manager = OrderManager(
            client=client,
            risk_manager=risk_manager,
            position_tracker=position_tracker,
            order_repo=order_repo,
            trade_repo=trade_repo,
        )
        notifier = TelegramNotifier()
        strategy = RSIStrategy()

        # 감시 종목 목록 (추후 설정으로 분리 가능)
        symbols = ["005930", "000660", "035420"]  # 삼성전자, SK하이닉스, NAVER

        scheduler = TradingScheduler(
            client=client,
            strategy=strategy,
            order_manager=order_manager,
            position_tracker=position_tracker,
            notifier=notifier,
            symbols=symbols,
        )

        # 6. 포지션 초기 동기화
        try:
            await position_tracker.update_positions()
        except Exception as exc:
            logger.warning(f"초기 포지션 동기화 실패 (계속 진행): {exc}")

        # 7. 종료 이벤트 및 시그널 핸들러 등록
        stop_event = asyncio.Event()

        def _handle_signal(sig: Any) -> None:
            logger.info(f"종료 신호 수신: {sig}")
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _handle_signal, sig)

        # 8. 스케줄러 시작
        await scheduler.start()

        logger.info("트레이딩 봇 가동 완료. 종료하려면 Ctrl+C를 누르세요.")

        # 종료 신호 대기
        await stop_event.wait()

        # 9. 정상 종료
        logger.info("봇 종료 중...")
        await scheduler.stop()

    logger.info("트레이딩 봇 종료 완료")


if __name__ == "__main__":
    asyncio.run(main())
