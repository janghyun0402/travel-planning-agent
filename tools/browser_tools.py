"""웹사이트에서 심층 정보를 추출한다. httpx+Gemini 기본, browser-use 폴백."""

import logging

from tools.website_crawler import crawl_and_extract

logger = logging.getLogger(__name__)


async def crawl_website_for_info(url: str, place_name: str) -> dict:
    """URL에서 장소의 예약 정보, 운영 정책, 방문 팁을 추출합니다.

    기본적으로 httpx + Gemini로 빠르게 처리하고 (2-3초),
    JS 렌더링이 필요한 경우에만 browser-use로 폴백합니다 (30-60초).

    Args:
        url: 크롤링할 웹페이지 URL
        place_name: 장소 이름

    Returns:
        예약 정보, 팁, 제한사항 등이 담긴 dict.
    """
    result = await crawl_and_extract(url, place_name)
    if not result:
        logger.warning("크롤 결과 없음: %s (%s)", place_name, url)
        return {"error": None, "data": {}}
    return {"error": None, "data": result}
