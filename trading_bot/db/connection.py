"""aiosqlite 비동기 연결 관리자"""

from pathlib import Path
from types import TracebackType

import aiosqlite
from loguru import logger

from trading_bot.db.schema import ALL_DDL


class AsyncConnectionContext:
    """
    async with 패턴을 지원하는 DB 연결 컨텍스트

    정상 종료 시 커밋, 예외 발생 시 롤백을 자동 처리합니다.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def __aenter__(self) -> aiosqlite.Connection:
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        return self._conn

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._conn is None:
            return

        try:
            if exc_type is not None:
                # 예외 발생 시 롤백
                await self._conn.rollback()
            else:
                # 정상 종료 시 커밋
                await self._conn.commit()
        finally:
            await self._conn.close()
            self._conn = None


class DatabaseManager:
    """SQLite 데이터베이스 관리자"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        """
        데이터베이스 초기화

        - DDL 실행 (테이블, 인덱스 생성)
        - WAL 모드 활성화 (동시 읽기 성능 향상)
        - 외래 키 제약 활성화
        """
        # DB 파일 디렉토리 생성
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self._db_path) as conn:
            # WAL(Write-Ahead Logging) 모드 - 동시 읽기 성능 향상
            await conn.execute("PRAGMA journal_mode=WAL")
            # 외래 키 제약 활성화
            await conn.execute("PRAGMA foreign_keys=ON")

            # 전체 DDL 일괄 실행
            for ddl in ALL_DDL:
                await conn.execute(ddl)

            await conn.commit()

        logger.info(f"데이터베이스 초기화 완료: {self._db_path}")

    def connection(self) -> AsyncConnectionContext:
        """
        비동기 연결 컨텍스트 반환

        Usage:
            async with db_manager.connection() as conn:
                await conn.execute(...)
        """
        return AsyncConnectionContext(self._db_path)
