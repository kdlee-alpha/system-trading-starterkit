"""포지션 추적기 - 인메모리 캐시 + API/DB 동기화"""

from loguru import logger

from trading_bot.api.kiwoom_client import KiwoomClient
from trading_bot.api.models import Position
from trading_bot.db.repositories import PositionRepository


class PositionTracker:
    """
    포지션 추적기

    - 인메모리 캐시로 빈번한 조회에서 API 호출 없이 포지션 반환
    - update_positions() 호출 시 API 동기화 및 DB upsert
    """

    def __init__(self, client: KiwoomClient, position_repo: PositionRepository) -> None:
        self._client = client
        self._position_repo = position_repo
        self._cache: dict[str, Position] = {}

    async def update_positions(self) -> list[Position]:
        """
        API에서 포지션 동기화

        1. API에서 현재 포지션 조회
        2. 인메모리 캐시 갱신
        3. DB upsert

        Returns:
            현재 보유 포지션 목록
        """
        try:
            positions = await self._client.get_positions()

            # 캐시 초기화 후 갱신
            self._cache = {p.symbol: p for p in positions}

            # DB upsert
            for position in positions:
                await self._position_repo.save_position(position)

            logger.info(f"포지션 동기화 완료: {len(positions)}개 종목")
            return positions

        except Exception as exc:
            logger.error(f"포지션 동기화 실패: {exc}")
            raise

    def get_current_position(self, symbol: str) -> Position | None:
        """
        종목 포지션 조회 (인메모리 캐시, API 미호출)

        Args:
            symbol: 종목 코드

        Returns:
            포지션 (보유 중이 아니면 None)
        """
        return self._cache.get(symbol)

    def get_all_positions(self) -> list[Position]:
        """
        전체 포지션 목록 반환 (캐시 기반)

        Returns:
            보유 수량 > 0인 포지션 목록
        """
        return [p for p in self._cache.values() if p.quantity > 0]

    def get_total_exposure(self) -> int:
        """
        전체 투자 노출 금액 반환 (원)

        Returns:
            보유 포지션 평가금액 합계
        """
        return sum(p.market_value for p in self._cache.values() if p.quantity > 0)
