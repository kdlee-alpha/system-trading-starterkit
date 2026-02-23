"""Kiwoom REST API 요청/응답 Pydantic 모델"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ── 열거형 ──────────────────────────────────────────────────────────────────


class OrderSide(StrEnum):
    """매수/매도 구분"""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    """주문 유형"""

    MARKET = "MARKET"   # 시장가
    LIMIT = "LIMIT"     # 지정가


class OrderStatus(StrEnum):
    """주문 상태"""

    PENDING = "PENDING"       # 접수 대기
    SUBMITTED = "SUBMITTED"   # 접수됨
    FILLED = "FILLED"         # 체결됨
    PARTIAL = "PARTIAL"       # 부분 체결
    CANCELLED = "CANCELLED"   # 취소됨
    REJECTED = "REJECTED"     # 거부됨


# ── 인증 모델 ─────────────────────────────────────────────────────────────────


class TokenRequest(BaseModel):
    """토큰 발급 요청"""

    grant_type: str = "client_credentials"
    appkey: str
    appsecret: str


class TokenResponse(BaseModel):
    """토큰 발급 응답"""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="만료 시간 (초)")
    expires_at: datetime | None = None  # 클라이언트에서 계산


# ── OHLCV 모델 ───────────────────────────────────────────────────────────────


class OHLCVBar(BaseModel):
    """OHLCV 봉 데이터"""

    datetime: datetime
    open: float = Field(gt=0, description="시가")
    high: float = Field(gt=0, description="고가")
    low: float = Field(gt=0, description="저가")
    close: float = Field(gt=0, description="종가")
    volume: int = Field(ge=0, description="거래량")


# ── 주문 모델 ─────────────────────────────────────────────────────────────────


class OrderRequest(BaseModel):
    """주문 요청"""

    symbol: str = Field(description="종목 코드 (예: 005930)")
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: int = Field(gt=0, description="주문 수량")
    price: float | None = Field(default=None, description="지정가 주문 시 가격")
    account_number: str = Field(description="계좌번호")


class OrderResponse(BaseModel):
    """주문 응답"""

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: float | None = None
    status: OrderStatus
    filled_quantity: int = 0
    filled_price: float | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ── 계좌/포지션 모델 ──────────────────────────────────────────────────────────


class AccountBalance(BaseModel):
    """계좌 잔액"""

    total_assets: int = Field(description="총 자산 (원)")
    available_cash: int = Field(description="가용 현금 (원)")
    total_invested: int = Field(description="총 투자 금액 (원)")
    total_profit_loss: int = Field(description="총 평가손익 (원)")
    profit_loss_rate: float = Field(description="수익률 (%)")


class Position(BaseModel):
    """보유 포지션"""

    symbol: str = Field(description="종목 코드")
    name: str = Field(default="", description="종목명")
    quantity: int = Field(ge=0, description="보유 수량")
    avg_price: float = Field(ge=0, description="평균 매수가")
    current_price: float = Field(ge=0, description="현재가")
    market_value: int = Field(description="평가금액 (원)")
    profit_loss: int = Field(description="평가손익 (원)")
    profit_loss_rate: float = Field(description="수익률 (%)")
