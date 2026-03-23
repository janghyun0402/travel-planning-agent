"""SerpAPI로 Google 검색 결과 URL 목록을 반환한다."""

import logging

from serpapi import GoogleSearch

from config.settings import settings

logger = logging.getLogger(__name__)


async def search_web(query: str, num_results: int = 5) -> dict:
    """SerpAPI로 Google 검색하여 상위 결과 URL 목록을 반환합니다.

    Args:
        query: 검색 쿼리 (예: "Café de Flore Paris reservation tips review")
        num_results: 반환할 결과 수 (기본 5)

    Returns:
        검색 결과 dict. {"urls": [...], "snippets": [...]} 형태.
    """
    if not settings.serpapi_api_key:
        logger.warning("SerpAPI key not configured")
        return {"error": "SerpAPI not configured", "urls": [], "snippets": []}

    try:
        params = {
            "q": query,
            "num": num_results,
            "api_key": settings.serpapi_api_key,
            "engine": "google",
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            logger.warning("SerpAPI error: %s", results["error"])
            return {"error": results["error"], "urls": [], "snippets": []}

        organic = results.get("organic_results", [])
        urls = [r["link"] for r in organic if "link" in r]
        snippets = [r.get("snippet", "") for r in organic]

        logger.info("SerpAPI 검색 성공: '%s' → %d개 결과", query, len(urls))
        return {"error": None, "urls": urls, "snippets": snippets}

    except Exception as e:
        logger.exception("SerpAPI 에러: %s", query)
        return {"error": str(e), "urls": [], "snippets": []}
