"""트레이딩 봇 커스텀 예외 계층"""


class TradingBotError(Exception):
    """트레이딩 봇 기본 예외"""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


# API 관련 예외
class ApiError(TradingBotError):
    """API 요청/응답 오류"""

    def __init__(self, message: str, status_code: int | None = None, details: dict | None = None) -> None:
        super().__init__(message, details)
        self.status_code = status_code


class AuthenticationError(ApiError):
    """인증 오류 (토큰 만료, 잘못된 API 키 등)"""


class RateLimitError(ApiError):
    """TR 요청 속도 제한 초과"""

    def __init__(self, message: str = "TR 요청 속도 제한을 초과했습니다", retry_after: float = 1.0) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


# 주문 관련 예외
class OrderError(TradingBotError):
    """주문 처리 오류"""

    def __init__(self, message: str, order_id: str | None = None, details: dict | None = None) -> None:
        super().__init__(message, details)
        self.order_id = order_id


class InsufficientFundsError(OrderError):
    """잔액 부족"""

    def __init__(self, required: int, available: int) -> None:
        super().__init__(
            f"잔액 부족: 필요 {required:,}원, 가용 {available:,}원",
            details={"required": required, "available": available},
        )
        self.required = required
        self.available = available


# 포지션 관련 예외
class PositionError(TradingBotError):
    """포지션 관리 오류"""


class PositionLimitExceededError(PositionError):
    """포지션 한도 초과"""

    def __init__(self, symbol: str, amount: int, limit: int) -> None:
        super().__init__(
            f"{symbol} 포지션 한도 초과: {amount:,}원 (한도: {limit:,}원)",
            details={"symbol": symbol, "amount": amount, "limit": limit},
        )


class TotalExposureLimitExceededError(PositionError):
    """전체 노출 한도 초과"""

    def __init__(self, additional: int, current: int, limit: int) -> None:
        super().__init__(
            f"전체 투자 한도 초과: 현재 {current:,}원 + 추가 {additional:,}원 > 한도 {limit:,}원",
            details={"additional": additional, "current": current, "limit": limit},
        )


# 전략 관련 예외
class StrategyError(TradingBotError):
    """전략 실행 오류"""

    def __init__(self, message: str, strategy_name: str = "", details: dict | None = None) -> None:
        super().__init__(message, details)
        self.strategy_name = strategy_name
