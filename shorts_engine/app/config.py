"""환경 설정.

모든 값은 환경변수 또는 .env에서 온다. 자격증명은 코드에 넣지 않는다.
로컬 개발과 GitHub Actions가 같은 DB를 바라보므로 DATABASE_URL만 바꿔 끼우면 된다.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- 데이터베이스 -------------------------------------------------
    # 예: postgresql+asyncpg://user:pw@ep-xxx.neon.tech/shorts?ssl=require
    database_url: str = Field(
        default="postgresql+asyncpg://shorts:shorts@localhost:5432/shorts"
    )
    db_echo: bool = False
    db_pool_size: int = 5
    # Neon/Supabase 무료 티어는 유휴 연결을 끊는다. 재사용 전에 살아있는지 확인한다.
    db_pool_pre_ping: bool = True

    # --- Ollama (로컬) ------------------------------------------------
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_timeout_sec: float = 180.0
    # 로컬 모델은 깨진 JSON을 흔히 낸다. 재시도 횟수.
    ollama_max_attempts: int = 3

    # --- 피드백 루프 판정 기준 ----------------------------------------
    feedback_min_views: int = 500
    feedback_like_ratio_threshold: float = 0.01
    # 카테고리당 최소 표본. 이게 없으면 운 나쁜 한 편이 카테고리를 영구 배제한다.
    feedback_min_samples: int = 3

    # --- YouTube ------------------------------------------------------
    yt_client_id: str = ""
    yt_client_secret: str = ""
    yt_refresh_token: str = ""

    # --- 렌더링 -------------------------------------------------------
    hook_sec: float = 3.0
    hook_cut_sec: float = 0.5
    pexels_api_key: str = ""

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, v: str) -> str:
        # 동기 드라이버를 넣으면 런타임에 애매한 에러가 난다. 여기서 잡는다.
        if v.startswith("postgresql://"):
            raise ValueError(
                "async 드라이버가 필요합니다. postgresql:// 대신 "
                "postgresql+asyncpg:// 를 쓰세요."
            )
        return v

    @field_validator("feedback_like_ratio_threshold")
    @classmethod
    def _ratio_is_fraction(cls, v: float) -> float:
        # 1% 를 1.0 으로 넣는 실수를 막는다. 그러면 모든 주제가 실패로 판정된다.
        if not 0 < v < 1:
            raise ValueError(f"비율은 0과 1 사이여야 합니다 (1%는 0.01): {v}")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
