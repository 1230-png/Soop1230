"""애플리케이션 설정 관리.

환경 변수를 Pydantic으로 검증하고 타입 안전성을 제공한다.
"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 전역 설정"""

    # === 데이터베이스 ===
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/moneylogic")

    # === 환경 ===
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # === OpenAI ===
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 800  # 비용 폭탄 방지 (고정값)

    # === ElevenLabs ===
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "")
    elevenlabs_stability: float = 0.35  # 0.0 ~ 1.0, 낮을수록 자연스러움

    # === 렌더링 ===
    output_dir: str = os.getenv("OUTPUT_DIR", "./output")
    video_fps: int = 30
    video_codec: str = "libx264"
    video_preset: str = "ultrafast"

    class Config:
        env_file = ".env"
        case_sensitive = False


def get_settings() -> Settings:
    """싱글톤 설정 인스턴스 반환"""
    return Settings()
