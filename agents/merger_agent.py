"""MergerAgent - 크롤 데이터를 교차검증하고 신뢰도를 산정한다.

BaseAgent로 구현. raw_crawl_data를 직접 읽어서 Gemini API에 명시적으로 전달.
교차검증 결과를 DB에 저장.
"""

import json
import logging
from typing import AsyncGenerator

import google.genai as genai

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from google.genai.types import Content, Part

from config.settings import settings
from tools.db_tools import save_place_to_db

logger = logging.getLogger(__name__)

MERGE_PROMPT = """다음은 여행 장소들의 크롤링 데이터입니다. 각 장소에 대해 교차검증하고 구조화된 정보를 생성해주세요.

## 크롤링 데이터
{raw_data}

## 교차검증 규칙

1. Places API 데이터와 웹 크롤 데이터가 모두 있으면: 신뢰도 높음 (Places API 우선, 웹 크롤로 보완)
2. Places API 데이터만 있으면: 기본 정보만 사용
3. 웹 크롤 데이터만 있으면: 웹 데이터 사용
4. 데이터가 충돌하면: Places API 우선
5. 데이터가 없으면: 해당 필드 null 처리

## 예약 상태 추론

- "예약 필수", "must book", "reservation required" → required
- "예약 추천", "better to reserve", "long wait" → recommended
- "예약 불필요", "walk-in", "no reservation needed" → not_needed
- 정보 없음 → unknown

## 출력

각 장소를 다음 필드를 포함하는 JSON 배열로 출력하세요.
반드시 크롤링 데이터의 **실제 장소 이름**을 사용하세요. 절대 가상의 이름을 만들지 마세요.

필드: name, address, google_maps_url, category, reservation_status, reservation_lead_time,
booking_method, operating_hours, last_order, break_time, restrictions,
rating, review_count, price_level, evidence_urls, review_snippets

JSON 배열만 출력하세요. 다른 텍스트는 포함하지 마세요.
"""


class MergerAgent(BaseAgent):
    """크롤 데이터를 교차검증하고 DB에 저장하는 에이전트."""

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state or {}

        # 데이터 읽기
        raw_crawl = state.get("raw_crawl_data", "{}")
        if isinstance(raw_crawl, str):
            raw_data_str = raw_crawl
        else:
            raw_data_str = json.dumps(raw_crawl, ensure_ascii=False)

        trip_id = state.get("trip_id")
        if not trip_id:
            logger.error("trip_id가 session state에 없음")
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text="Error: trip_id not found")]),
            )
            return

        logger.info("MergerAgent 시작: raw_crawl_data %d자", len(raw_data_str))

        # Gemini API 직접 호출
        prompt = MERGE_PROMPT.format(raw_data=raw_data_str[:15000])  # 토큰 제한

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        result_text = response.text.strip()

        # JSON 파싱
        if "```json" in result_text:
            result_text = result_text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            validated = json.loads(result_text)
        except json.JSONDecodeError:
            logger.error("MergerAgent JSON 파싱 실패: %s", result_text[:300])
            validated = []

        if not isinstance(validated, list):
            logger.error("MergerAgent 결과가 리스트 아님: %s", type(validated))
            validated = []

        # DB 저장
        logger.info("DB 저장 시작: %d개 장소", len(validated))
        for place_data in validated:
            if not isinstance(place_data, dict):
                continue
            place_data["trip_id"] = trip_id
            try:
                result = await save_place_to_db(place_data)
                logger.info("  저장 완료: %s (id: %s)", place_data.get("name"), result.get("id"))
            except Exception:
                logger.exception("  저장 실패: %s", place_data.get("name"))
        logger.info("DB 저장 완료")

        # session state에 저장
        validated_json = json.dumps(validated, ensure_ascii=False, default=str)
        ctx.session.state["validated_places"] = validated_json

        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=validated_json)]),
        )


merger_agent = MergerAgent(
    name="MergerAgent",
    description="Cross-validates crawled data with Gemini, saves validated places to DB.",
)
