"""CrawlerAgent - trip_request의 각 장소에 대해 정보를 수집한다.

BaseAgent 상속으로 LLM 왕복 없이 Python 코드로 직접 도구를 호출한다.
1. Places API → 기본 정보
2. SerpAPI → 검색 URL 목록
3. httpx + Gemini → URL에서 심층 정보 추출
"""

import json
import logging
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from google.genai.types import Content, Part

from tools.places_api import search_place
from tools.google_search_api import search_web
from tools.website_crawler import crawl_and_extract

logger = logging.getLogger(__name__)

# 크롤링 스킵할 도메인 (CAPTCHA/차단)
BLOCKED_DOMAINS = {"google.com", "tripadvisor.com", "yelp.com", "facebook.com"}


def _is_blocked_url(url: str) -> bool:
    """차단된 도메인인지 확인한다."""
    return any(domain in url.lower() for domain in BLOCKED_DOMAINS)


class CrawlerAgent(BaseAgent):
    """Python 코드로 직접 크롤링을 수행하는 에이전트."""

    model_config = {"arbitrary_types_allowed": True}

    @staticmethod
    def _parse_json(raw) -> dict:
        """session state 값에서 JSON을 파싱한다."""
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            return {}
        text = raw.strip()
        # ```json 블록 추출
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("JSON 파싱 실패: %s", text[:200])
            return {}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # session state에서 trip_request 읽기
        state = ctx.session.state or {}
        trip_req_raw = state.get("trip_request", "{}")
        trip_req = self._parse_json(trip_req_raw)

        city = trip_req.get("city", "")
        max_per_day = trip_req.get("preferences", {}).get("max_places_per_day", 3)

        # 여행 일수 계산
        start = trip_req.get("start_date", "")
        end = trip_req.get("end_date", "")
        try:
            from datetime import date as dt_date
            num_days = max(1, (dt_date.fromisoformat(end) - dt_date.fromisoformat(start)).days + 1)
        except (ValueError, TypeError):
            num_days = 1

        MAX_TOTAL_PLACES = min(max_per_day * num_days, 10)

        # trip_request.places에서 장소 리스트 추출
        places = [
            p.get("place_name", "") for p in trip_req.get("places", [])
        ]
        places = places[:MAX_TOTAL_PLACES]

        logger.info("CrawlerAgent 시작: %s, %d개 장소", city, len(places))

        # 진행 상황 이벤트
        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=f"크롤링 시작: {city}, {len(places)}개 장소")]),
        )

        crawl_results = []

        for i, place_name in enumerate(places):
            if not place_name:
                continue

            logger.info("[%d/%d] 크롤링: %s", i + 1, len(places), place_name)

            place_data = {"name": place_name, "city": city}

            # 1. Places API
            try:
                places_result = await search_place(place_name, city)
                if places_result.get("data"):
                    place_data.update(places_result["data"])
                    logger.info("  Places API 성공: %s", place_name)
                else:
                    logger.warning("  Places API 결과 없음: %s", place_name)
            except Exception:
                logger.exception("  Places API 에러: %s", place_name)

            # 2. SerpAPI
            search_urls = []
            try:
                search_result = await search_web(
                    f"{place_name} {city} reservation tips review", num_results=3
                )
                search_urls = search_result.get("urls", [])
                logger.info("  SerpAPI 성공: %d개 URL", len(search_urls))
            except Exception:
                logger.exception("  SerpAPI 에러: %s", place_name)

            # 3. 크롤링 대상 URL 선정 (최대 1개)
            crawl_url = None

            # 공식 웹사이트 우선
            official_website = place_data.get("website")
            if official_website and not _is_blocked_url(official_website):
                crawl_url = official_website
            else:
                # SerpAPI 결과에서 차단 안 된 첫 번째 URL
                for url in search_urls:
                    if not _is_blocked_url(url):
                        crawl_url = url
                        break

            # 4. URL 크롤링
            if crawl_url:
                try:
                    crawl_result = await crawl_and_extract(crawl_url, place_name)
                    if crawl_result:
                        # 크롤 결과를 place_data에 병합 (기존 값 덮어쓰지 않음)
                        for key, value in crawl_result.items():
                            if value and key not in ("name", "city"):
                                place_data.setdefault(key, value)
                        place_data["evidence_urls"] = json.dumps([crawl_url], ensure_ascii=False)
                        logger.info("  웹 크롤 성공: %s → %s", place_name, crawl_url)
                    else:
                        logger.warning("  웹 크롤 결과 없음: %s", crawl_url)
                except Exception:
                    logger.exception("  웹 크롤 에러: %s", crawl_url)
            else:
                logger.info("  크롤 URL 없음, Places API 데이터만 사용: %s", place_name)

            # operating_hours를 JSON 문자열로 변환
            if isinstance(place_data.get("operating_hours"), dict):
                place_data["operating_hours"] = json.dumps(
                    place_data["operating_hours"], ensure_ascii=False
                )

            crawl_results.append(place_data)

            logger.info("[%d/%d] 완료: %s", i + 1, len(places), place_name)

        # 결과를 session state에 저장
        result = {"city": city, "places": crawl_results}
        result_json = json.dumps(result, ensure_ascii=False, default=str)
        ctx.session.state["raw_crawl_data"] = result_json

        logger.info("CrawlerAgent 완료: %d개 장소 처리", len(crawl_results))

        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=result_json)]),
        )


crawler_agent = CrawlerAgent(
    name="CrawlerAgent",
    description="Gathers place info via Places API, finds URLs via SerpAPI, then extracts info with httpx+Gemini.",
)
