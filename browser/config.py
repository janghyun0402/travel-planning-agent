"""browser-use 브라우저 및 LLM 설정."""

import asyncio

from browser_use import Browser
from browser_use.llm.google.chat import ChatGoogle

from config.settings import settings

# 브라우저 설정
HEADLESS = True
TIMEOUT = 120  # 초
MAX_RETRIES = 2
MAX_BROWSERS = 2
REQUEST_DELAY = 3  # 초


def get_browser() -> Browser:
    """headless Browser 인스턴스를 반환한다."""
    return Browser(headless=HEADLESS)


def get_llm() -> ChatGoogle:
    """browser-use Agent에 사용할 LLM 인스턴스를 반환한다."""
    return ChatGoogle(
        model="gemini-2.5-flash",
        api_key=settings.gemini_api_key,
    )


async def delay_between_requests() -> None:
    """요청 간 딜레이를 적용한다."""
    await asyncio.sleep(REQUEST_DELAY)
