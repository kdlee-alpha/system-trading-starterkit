"""텔레그램 알림 모듈"""

from loguru import logger

from trading_bot.api.models import AccountBalance, OrderResponse
from trading_bot.config.settings import settings
from trading_bot.db.repositories import TradeRecord
from trading_bot.strategy.base import Signal


class TelegramNotifier:
    """
    텔레그램 알림 발송기

    python-telegram-bot v21 비동기 API 기반.
    전송 실패 시 예외를 전파하지 않습니다 (알림 실패가 트레이딩을 중단하면 안 됨).
    """

    def __init__(self) -> None:
        self._bot_token = settings.telegram.bot_token
        self._chat_id = settings.telegram.chat_id
        self._bot = None

    @property
    def enabled(self) -> bool:
        """텔레그램 알림 활성화 여부"""
        return bool(self._bot_token and self._chat_id)

    async def _get_bot(self):
        """텔레그램 봇 인스턴스 지연 초기화"""
        if self._bot is None:
            from telegram import Bot
            self._bot = Bot(token=self._bot_token)
        return self._bot

    async def send_signal(self, signal: Signal) -> None:
        """
        매매 신호 알림 발송

        Args:
            signal: 매매 신호
        """
        if signal.type.value == "HOLD":
            return

        emoji = "📈" if signal.type.value == "BUY" else "📉"
        lines = [
            f"{emoji} *매매 신호 발생*",
            f"종목: `{signal.symbol}`",
            f"유형: `{signal.type}`",
            f"수량: `{signal.quantity:,}주`",
            f"이유: {signal.reason}",
        ]

        if signal.price:
            lines.append(f"가격: `{signal.price:,.0f}원`")

        # 메타데이터 (RSI 등 지표 값)
        for key, value in signal.metadata.items():
            if isinstance(value, float):
                lines.append(f"{key}: `{value:.2f}`")
            else:
                lines.append(f"{key}: `{value}`")

        await self._send_message("\n".join(lines))

    async def send_order_result(self, order: OrderResponse) -> None:
        """
        주문 체결 결과 알림 발송

        Args:
            order: 주문 응답
        """
        emoji = "✅" if order.side.value == "BUY" else "🔴"
        lines = [
            f"{emoji} *주문 체결*",
            f"종목: `{order.symbol}`",
            f"구분: `{order.side}`",
            f"상태: `{order.status}`",
            f"수량: `{order.filled_quantity:,}주`",
        ]

        if order.filled_price:
            lines.append(f"체결가: `{order.filled_price:,.0f}원`")
            total = int(order.filled_quantity * order.filled_price)
            lines.append(f"체결금액: `{total:,}원`")

        await self._send_message("\n".join(lines))

    async def send_error(self, error: Exception, context: str = "") -> None:
        """
        오류 알림 발송

        Args:
            error: 발생한 예외
            context: 오류 발생 맥락 설명
        """
        lines = [
            "🚨 *오류 발생*",
            f"오류: `{type(error).__name__}: {error}`",
        ]
        if context:
            lines.append(f"맥락: {context}")

        await self._send_message("\n".join(lines))

    async def send_daily_summary(
        self,
        balance: AccountBalance,
        trades: list[TradeRecord],
    ) -> None:
        """
        일일 요약 알림 발송

        Args:
            balance: 현재 계좌 잔액
            trades: 오늘 거래 기록 목록
        """
        profit_emoji = "📈" if balance.total_profit_loss >= 0 else "📉"
        lines = [
            "📊 *일일 거래 요약*",
            "",
            "*계좌 현황*",
            f"총 자산: `{balance.total_assets:,}원`",
            f"가용 현금: `{balance.available_cash:,}원`",
            f"총 투자: `{balance.total_invested:,}원`",
            f"평가손익: {profit_emoji} `{balance.total_profit_loss:+,}원` ({balance.profit_loss_rate:+.2f}%)",
            "",
            f"*오늘 거래: {len(trades)}건*",
        ]

        if trades:
            buy_trades = [t for t in trades if t.side.value == "BUY"]
            sell_trades = [t for t in trades if t.side.value == "SELL"]
            lines.append(f"매수: `{len(buy_trades)}건`  매도: `{len(sell_trades)}건`")

            total_amount = sum(t.amount for t in trades)
            lines.append(f"총 거래금액: `{total_amount:,}원`")

        await self._send_message("\n".join(lines))

    async def _send_message(self, text: str) -> None:
        """
        텔레그램 메시지 전송 (실패 시 경고 로그만 출력)

        Args:
            text: Markdown 형식 메시지 텍스트
        """
        if not self.enabled:
            return

        try:
            bot = await self._get_bot()
            await bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode="Markdown",
            )
        except Exception as exc:
            # 알림 실패 시 예외 전파하지 않음 (트레이딩 중단 방지)
            logger.warning(f"텔레그램 알림 전송 실패: {exc}")
