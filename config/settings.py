import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = ""
    google_maps_api_key: str = ""
    serpapi_api_key: str = ""
    tavily_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./travel_agent.db"
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

# ADK는 GOOGLE_API_KEY 환경변수를 직접 읽으므로 설정
if settings.gemini_api_key and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key
