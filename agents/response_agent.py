"""ResponseAgent - DB의 places + itinerary_slots를 읽어 최종 여행 일정 답변을 생성한다.

BaseAgent로 구현. DB에서 직접 데이터를 읽고 Gemini API를 호출해 유저에게 보기 좋은 답변을 생성.
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
from db.crud import get_places_by_trip, get_slots_by_trip
from db.database import async_session

logger = logging.getLogger(__name__)

RESPONSE_PROMPT = """너는 여행 일정을 보기 좋게 정리해주는 어시스턴트야.

아래 데이터를 기반으로 유저에게 보여줄 여행 일정 답변을 **한국어**로 생성해줘.
마크다운 형식으로 깔끔하게 정리해.

## 일정 데이터 (itinerary_slots)
{slots_data}

## 장소 상세 데이터 (places)
{places_data}

## 답변 형식

### 1. 일정표
- 날짜별로 구분
- 각 슬롯: 시간, 장소명, 카테고리, 이동 방법/소요 시간
- 장소별 간단한 팁 한 줄

### 2. 장소 상세 정보
각 장소에 대해:
- 영업시간 (라스트오더, 브레이크타임 포함)
- 예약 필요 여부 및 방법/URL
- 제한사항 (있을 경우)
- 평점 및 가격대
- 유용한 팁

### 3. 예약 필요 장소 (별도 섹션으로 강조)
예약이 필요(required)하거나 추천(recommended)인 장소를 모아서:
- 장소명
- 예약 상태 (필수/추천)
- 예약 방법
- 예약 리드타임

답변은 유저가 바로 활용할 수 있도록 실용적이고 구체적으로 작성해줘.
"""


class ResponseAgent(BaseAgent):
    """DB 데이터를 읽어 최종 여행 일정 답변을 생성하는 에이전트."""

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state or {}
        trip_id = state.get("trip_id")

        if not trip_id:
            logger.error("trip_id가 session state에 없음")
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text="Error: trip_id not found")]),
            )
            return

        logger.info("ResponseAgent 시작: trip_id=%s", trip_id)

        # DB에서 places와 itinerary_slots 조회
        async with async_session() as session:
            places = await get_places_by_trip(session, trip_id)
            slots = await get_slots_by_trip(session, trip_id)

        if not places:
            logger.warning("places 데이터 없음: trip_id=%s", trip_id)
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text="저장된 장소 데이터가 없습니다.")]),
            )
            return

        # Place 객체를 dict로 변환
        place_map = {}
        places_list = []
        for p in places:
            pd = {
                "name": p.name,
                "address": p.address,
                "google_maps_url": p.google_maps_url,
                "category": p.category,
                "reservation_status": p.reservation_status,
                "reservation_lead_time": p.reservation_lead_time,
                "booking_method": p.booking_method,
                "operating_hours": p.operating_hours,
                "last_order": p.last_order,
                "break_time": p.break_time,
                "restrictions": p.restrictions,
                "rating": p.rating,
                "review_count": p.review_count,
                "price_level": p.price_level,
            }
            place_map[p.id] = pd
            places_list.append(pd)

        # ItinerarySlot 객체를 dict로 변환 (장소명 포함)
        slots_list = []
        for s in slots:
            place_info = place_map.get(s.place_id, {})
            sd = {
                "day_number": s.day_number,
                "slot_order": s.slot_order,
                "slot_date": str(s.slot_date),
                "time_start": s.time_start,
                "time_end": s.time_end,
                "place_name": place_info.get("name", "Unknown"),
                "category": place_info.get("category"),
                "travel_minutes": s.travel_minutes,
                "travel_method": s.travel_method,
                "notes": s.notes,
                "is_reserved": s.is_reserved,
            }
            slots_list.append(sd)

        places_data = json.dumps(places_list, ensure_ascii=False, default=str)
        slots_data = json.dumps(slots_list, ensure_ascii=False, default=str)

        # Gemini API 호출
        prompt = RESPONSE_PROMPT.format(
            slots_data=slots_data[:10000],
            places_data=places_data[:10000],
        )

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        result_text = response.text.strip()

        # state에 저장
        ctx.session.state["final_response"] = result_text

        # DB에 저장
        try:
            async with async_session() as db_session:
                from db.models import Trip
                trip = await db_session.get(Trip, trip_id)
                if trip:
                    trip.final_response = result_text
                    await db_session.commit()
                    logger.info("final_response DB 저장 완료")
        except Exception:
            logger.exception("final_response DB 저장 실패")

        logger.info("ResponseAgent 완료: %d자 응답 생성", len(result_text))

        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=result_text)]),
        )


response_agent = ResponseAgent(
    name="ResponseAgent",
    description="Reads places and itinerary from DB, generates a formatted travel itinerary response via Gemini.",
)
