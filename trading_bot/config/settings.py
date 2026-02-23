"""중앙 설정 관리 모듈 (pydantic-settings 기반)"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KiwoomSettings(BaseSettings):
    """Kiwoom REST API 연결 설정"""

    app_key: str = Field(default="", description="앱 키")
    app_secret: str = Field(default="", description="앱 시크릿")
    account_number: str = Field(default="", description="계좌번호")
    base_url: str = Field(
        default="https://mockapi.kiwoom.com",
        description="API 기본 URL (모의투자 기본값)",
    )


class TradingSettings(BaseSettings):
    """트레이딩 전략 설정"""

    dry_run: bool = Field(default=True, description="Paper Trading 모드 (실제 주문 미실행)")
    max_position_size: int = Field(default=1_000_000, description="종목당 최대 투자금액 (원)")
    max_total_exposure: int = Field(default=5_000_000, description="전체 최대 투자금액 (원)")


class SchedulerSettings(BaseSettings):
    """스케줄러 설정"""

    tick_interval_seconds: int = Field(default=60, description="전략 실행 주기 (초)")


class TelegramSettings(BaseSettings):
    """텔레그램 알림 설정"""

    bot_token: str = Field(default="", description="텔레그램 봇 토큰")
    chat_id: str = Field(default="", description="텔레그램 채팅 ID")


class LogSettings(BaseSettings):
    """로깅 설정"""

    level: str = Field(default="INFO", description="로그 레벨")


class DBSettings(BaseSettings):
    """데이터베이스 설정"""

    path: str = Field(default="data/trading.db", description="SQLite DB 파일 경로")


class Settings(BaseSettings):
    """루트 설정 클래스 - 환경변수 중첩 설정 자동 매핑"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    kiwoom: KiwoomSettings = Field(default_factory=KiwoomSettings)
    trading: TradingSettings = Field(default_factory=TradingSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    db: DBSettings = Field(default_factory=DBSettings)


# 모듈 임포트 시 싱글톤 인스턴스 생성
settings = Settings()
