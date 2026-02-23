"""로깅 설정 모듈 (loguru 기반 3중 출력: 콘솔 + 파일 + 텔레그램)"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from loguru import Message


class TelegramSink:
    """텔레그램으로 ERROR 이상 로그를 전송하는 loguru sink"""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._bot = None

    async def _get_bot(self):
        """텔레그램 봇 인스턴스 지연 초기화"""
        if self._bot is None:
            from telegram import Bot

            self._bot = Bot(token=self.bot_token)
        return self._bot

    def __call__(self, message: "Message") -> None:
        """동기 sink 메서드 (loguru 호환)"""
        import asyncio

        record = message.record
        if record["level"].no < 40:  # ERROR 레벨(40) 미만은 무시
            return

        text = (
            f"🚨 *[{record['level'].name}]* `{record['name']}:{record['line']}`\n"
            f"```\n{record['message']}\n```"
        )

        # 이벤트 루프에서 비동기 전송
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._send(text))
            else:
                loop.run_until_complete(self._send(text))
        except Exception:
            pass  # 텔레그램 전송 실패 시 로깅 중단 방지

    async def _send(self, text: str) -> None:
        """텔레그램 메시지 전송"""
        try:
            bot = await self._get_bot()
            await bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="Markdown",
            )
        except Exception:
            pass  # 알림 전송 실패는 무시


def setup_logger(log_level: str = "INFO", bot_token: str = "", chat_id: str = "") -> None:
    """
    로거 초기화 함수 - 진입점에서 1회 호출

    Args:
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        bot_token: 텔레그램 봇 토큰 (비어있으면 텔레그램 sink 비활성화)
        chat_id: 텔레그램 채팅 ID
    """
    # 기존 핸들러 초기화
    logger.remove()

    # 로그 디렉토리 생성
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 1. 콘솔 출력 (컬러, 사람이 읽기 좋은 형식)
    logger.add(
        sys.stdout,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # 2. 파일 출력 (일별 로테이션, 30일 보관)
    logger.add(
        log_dir / "trading_{time:YYYY-MM-DD}.log",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}",
        rotation="00:00",   # 자정에 새 파일 생성
        retention="30 days",
        encoding="utf-8",
    )

    # 3. 텔레그램 sink (ERROR 이상, 설정된 경우에만)
    if bot_token and chat_id:
        telegram_sink = TelegramSink(bot_token=bot_token, chat_id=chat_id)
        logger.add(
            telegram_sink,
            level="ERROR",
            format="{message}",
        )
        logger.info("텔레그램 로그 알림 활성화")
    else:
        logger.info("텔레그램 봇 설정 없음 - 텔레그램 로그 알림 비활성화")

    logger.info(f"로거 초기화 완료 (레벨: {log_level})")
