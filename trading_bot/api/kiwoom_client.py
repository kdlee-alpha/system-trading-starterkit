"""Kiwoom REST API 비동기 클라이언트"""

import asyncio
from datetime import datetime, timedelta
from types import TracebackType

import httpx
from loguru import logger

from trading_bot.api.models import (
    AccountBalance,
    OHLCVBar,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    TokenRequest,
    TokenResponse,
)
from trading_bot.api.rate_limiter import KiwoomRateLimiter
from trading_bot.config.settings import settings
from trading_bot.utils.exceptions import (
    ApiError,
    AuthenticationError,
    RateLimitError,
)

# 토큰 만료 전 선제 갱신 여유 시간 (초)
_TOKEN_REFRESH_MARGIN_SECONDS = 300


class KiwoomClient:
    """
    Kiwoom REST API 비동기 클라이언트

    Usage:
        async with KiwoomClient() as client:
            ohlcv = await client.get_ohlcv("005930", "1D", 100)
    """

    def __init__(self) -> None:
        self._base_url = settings.kiwoom.base_url
        self._app_key = settings.kiwoom.app_key
        self._app_secret = settings.kiwoom.app_secret
        self._account_number = settings.kiwoom.account_number

        self._token: TokenResponse | None = None
        self._token_lock = asyncio.Lock()
        self._rate_limiter = KiwoomRateLimiter()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "KiwoomClient":
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── 인증 ──────────────────────────────────────────────────────────────────

    async def get_token(self) -> str:
        """
        액세스 토큰 반환 (만료 5분 전 자동 선제 갱신)

        asyncio.Lock으로 동시 갱신 요청의 레이스 컨디션을 방지합니다.
        """
        async with self._token_lock:
            if self._is_token_valid():
                return self._token.access_token  # type: ignore[union-attr]

            logger.info("액세스 토큰 갱신 중...")
            self._token = await self._fetch_token()
            logger.info("액세스 토큰 갱신 완료")
            return self._token.access_token

    def _is_token_valid(self) -> bool:
        """토큰 유효 여부 확인 (만료 5분 전 갱신 기준)"""
        if self._token is None or self._token.expires_at is None:
            return False
        margin = timedelta(seconds=_TOKEN_REFRESH_MARGIN_SECONDS)
        return datetime.now() < self._token.expires_at - margin

    async def _fetch_token(self) -> TokenResponse:
        """API에서 새 토큰 발급"""
        payload = TokenRequest(
            appkey=self._app_key,
            appsecret=self._app_secret,
        )
        response = await self._raw_request(
            method="POST",
            endpoint="/oauth2/token",
            json=payload.model_dump(),
            use_auth=False,
        )
        token = TokenResponse.model_validate(response)
        # 만료 시간 계산
        token.expires_at = datetime.now() + timedelta(seconds=token.expires_in)
        return token

    # ── 시세 데이터 ───────────────────────────────────────────────────────────

    async def get_ohlcv(
        self,
        symbol: str,
        interval: str,
        count: int,
    ) -> list[OHLCVBar]:
        """
        OHLCV 봉 데이터 조회

        Args:
            symbol: 종목 코드 (예: 005930)
            interval: 봉 주기 (예: 1D, 1H, 1m)
            count: 조회 개수

        Returns:
            OHLCVBar 리스트 (최신 데이터 기준 내림차순)
        """
        data = await self._request(
            method="GET",
            endpoint=f"/api/v1/market/ohlcv/{symbol}",
            params={"interval": interval, "count": count},
        )
        bars: list[OHLCVBar] = []
        for item in data.get("bars", []):
            bars.append(OHLCVBar.model_validate(item))
        return bars

    # ── 계좌 정보 ─────────────────────────────────────────────────────────────

    async def get_account_balance(self) -> AccountBalance:
        """계좌 잔액 조회"""
        data = await self._request(
            method="GET",
            endpoint=f"/api/v1/accounts/{self._account_number}/balance",
        )
        return AccountBalance.model_validate(data)

    async def get_positions(self) -> list[Position]:
        """보유 포지션 목록 조회"""
        data = await self._request(
            method="GET",
            endpoint=f"/api/v1/accounts/{self._account_number}/positions",
        )
        return [Position.model_validate(item) for item in data.get("positions", [])]

    # ── 주문 ──────────────────────────────────────────────────────────────────

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """주문 실행"""
        data = await self._request(
            method="POST",
            endpoint="/api/v1/orders",
            json=order.model_dump(mode="json"),
        )
        return OrderResponse.model_validate(data)

    async def cancel_order(self, order_id: str) -> bool:
        """주문 취소"""
        try:
            await self._request(
                method="DELETE",
                endpoint=f"/api/v1/orders/{order_id}",
            )
            return True
        except ApiError:
            return False

    # ── 내부 HTTP 요청 헬퍼 ───────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        """
        인증된 API 요청 (401 응답 시 토큰 재발급 후 1회 재시도)
        """
        try:
            return await self._raw_request(
                method=method,
                endpoint=endpoint,
                params=params,
                json=json,
                use_auth=True,
            )
        except AuthenticationError:
            # 토큰 무효화 후 1회 재시도
            logger.warning("인증 오류 - 토큰 초기화 후 재시도")
            async with self._token_lock:
                self._token = None
            return await self._raw_request(
                method=method,
                endpoint=endpoint,
                params=params,
                json=json,
                use_auth=True,
            )

    async def _raw_request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json: dict | None = None,
        use_auth: bool = True,
    ) -> dict:
        """
        실제 HTTP 요청 실행

        - 레이트 리미터 적용
        - HTTP 오류 → 커스텀 예외 변환
        """
        if self._client is None:
            raise ApiError("KiwoomClient가 초기화되지 않았습니다. 'async with' 구문을 사용하세요.")

        await self._rate_limiter.acquire()

        headers: dict[str, str] = {}
        if use_auth:
            token = await self.get_token()
            headers["Authorization"] = f"Bearer {token}"
            headers["appkey"] = self._app_key
            headers["appsecret"] = self._app_secret

        response = await self._client.request(
            method=method,
            url=endpoint,
            params=params,
            json=json,
            headers=headers,
        )

        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> dict:
        """HTTP 응답 처리 및 커스텀 예외 변환"""
        if response.is_success:
            return response.json()

        status_code = response.status_code
        try:
            error_body = response.json()
            message = error_body.get("message", response.text)
        except Exception:
            message = response.text

        if status_code == 401:
            raise AuthenticationError(
                message=f"인증 오류: {message}",
                status_code=status_code,
            )
        if status_code == 429:
            raise RateLimitError(message=f"속도 제한 초과: {message}")
        raise ApiError(
            message=f"API 오류 ({status_code}): {message}",
            status_code=status_code,
        )


def _create_dummy_order_response(order_id: str, symbol: str) -> OrderResponse:
    """더미 체결 응답 생성 (DRY_RUN 모드 내부용)"""
    return OrderResponse(
        order_id=order_id,
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0,
        status=OrderStatus.FILLED,
    )
