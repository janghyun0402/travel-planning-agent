"""ReserverAgent - 예약 필요 장소에 대해 예약 가이드를 생성한다.

MergerAgent가 판단한 reservation_status가 required/recommended인 장소에 대해
raw_crawl_data 확인 후 부족하면 Tavily 검색으로 예약 정보를 수집하고,
여행 날짜 대비 리드타임을 체크하여 장소별 예약 가이드를 생성한다.
after_agent_callback에서 DB의 places 테이블 예약 관련 필드를 업데이트한다.
"""

import json
import logging

from google.adk.agents import LlmAgent
from tavily import AsyncTavilyClient

from config.settings import settings
from db.database import async_session
from db.crud import get_places_by_trip, update_place

logger = logging.getLogger(__name__)

_tavily_client = None


def _get_tavily_client() -> AsyncTavilyClient:
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    return _tavily_client


async def search_reservation_info(query: str) -> dict:
    """Tavily로 예약 방법을 검색합니다.

    Args:
        query: 검색 쿼리 (예: "에펠탑 파리 예약 방법 booking")

    Returns:
        검색 결과 딕셔너리. results 키에 title, content, url 목록이 담겨 있습니다.
    """
    try:
        client = _get_tavily_client()
        result = await client.search(query=query, max_results=3)
        return {
            "results": [
                {"title": r.get("title", ""), "content": r.get("content", ""), "url": r.get("url", "")}
                for r in result.get("results", [])
            ]
        }
    except Exception as e:
        logger.error("Tavily 검색 실패: %s", e)
        return {"results": [], "error": str(e)}


RESERVER_AGENT_INSTRUCTION = """You are a reservation research specialist. Your job is to create
reservation guides for places that need advance booking.

## Data

Validated places:
{validated_places}

Raw crawl data:
{raw_crawl_data}

Trip request:
{trip_request}

## Process

1. From the validated places above, identify places where reservation_status is "required" or "recommended".
   Skip all places with "not_needed" or "unknown" status.

2. For each place that needs reservation:
   a. First check the raw crawl data above for existing reservation info:
      - booking_url, reservation_lead_time, booking_method, phone numbers
   b. If information is insufficient, use the `search_reservation_info` tool to search:
      - Query format: "<place_name> <city> 예약 방법 booking reservation"
   c. Compare trip start_date with reservation_lead_time:
      - If the trip is sooner than the required lead time, mark as "too_late"
      - If the trip is within the lead time window, mark as "feasible"
      - If no lead time info, mark as "unknown_feasibility"

3. Generate a reservation guide for each place.

## Output

Output a JSON array of reservation guides. Each guide should have:
- place_name: name of the place
- reservation_status: "required" or "recommended"
- booking_url: direct booking URL if found
- booking_phone: phone number for reservation if found
- booking_method: object describing how to book (online, phone, walk-in, app, etc.)
- reservation_lead_time: how far in advance to book (e.g., "2 weeks", "1 month")
- feasibility: "feasible", "too_late", or "unknown_feasibility"
- booking_steps: step-by-step reservation instructions as a list of strings
- tips: list of reservation tips and warnings
- evidence_urls: list of source URLs for the reservation info
- alternative_booking: fallback options if primary booking fails

Only include places that need reservations. Do NOT include "not_needed" or "unknown" places.
"""


async def _update_reservation_callback(*, callback_context, **kwargs) -> None:
    """ReserverAgent 완료 후 reservation_info를 파싱하여 places 테이블을 업데이트한다."""
    ctx = callback_context
    state = ctx.state or {}

    trip_id = state.get("trip_id")
    if not trip_id:
        logger.error("trip_id가 session state에 없음")
        return

    # reservation_info 파싱
    reservation_raw = state.get("reservation_info", "[]")
    if isinstance(reservation_raw, str):
        try:
            text = reservation_raw.strip()
            if "```json" in text:
                text = text.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in text:
                text = text.split("```", 1)[1].split("```", 1)[0]
            reservations = json.loads(text.strip())
        except json.JSONDecodeError:
            logger.error("reservation_info JSON 파싱 실패: %s", reservation_raw[:200])
            return
    else:
        reservations = reservation_raw

    if not isinstance(reservations, list):
        logger.error("reservation_info가 리스트가 아님: %s", type(reservations))
        return

    # DB에서 trip의 places 조회하여 name→id 매핑
    async with async_session() as session:
        places = await get_places_by_trip(session, trip_id)
        name_to_id = {p.name: p.id for p in places}

    logger.info("예약 정보 DB 업데이트 시작: %d개 장소", len(reservations))

    for res_data in reservations:
        if not isinstance(res_data, dict):
            continue

        place_name = res_data.get("place_name", "")
        place_id = name_to_id.get(place_name)
        if not place_id:
            logger.warning("  장소 '%s'를 DB에서 찾을 수 없음", place_name)
            continue

        # 업데이트할 필드 구성
        update_fields = {}
        if res_data.get("booking_url"):
            booking_method = res_data.get("booking_method", {})
            if isinstance(booking_method, dict):
                booking_method["url"] = res_data["booking_url"]
            else:
                booking_method = {"url": res_data["booking_url"], "method": booking_method}
            update_fields["booking_method"] = json.dumps(booking_method, ensure_ascii=False)
        elif res_data.get("booking_method"):
            bm = res_data["booking_method"]
            if isinstance(bm, (dict, list)):
                update_fields["booking_method"] = json.dumps(bm, ensure_ascii=False)
            else:
                update_fields["booking_method"] = str(bm)

        if res_data.get("reservation_lead_time"):
            update_fields["reservation_lead_time"] = res_data["reservation_lead_time"]

        if res_data.get("reservation_status"):
            update_fields["reservation_status"] = res_data["reservation_status"]

        if update_fields:
            try:
                async with async_session() as session:
                    await update_place(session, place_id, **update_fields)
                logger.info("  업데이트 완료: %s", place_name)
            except Exception:
                logger.exception("  업데이트 실패: %s", place_name)

    logger.info("예약 정보 DB 업데이트 완료")


reserver_agent = LlmAgent(
    name="ReserverAgent",
    model="gemini-2.5-flash",
    instruction=RESERVER_AGENT_INSTRUCTION,
    output_key="reservation_info",
    tools=[search_reservation_info],
    after_agent_callback=_update_reservation_callback,
    description="Researches reservation info for places that need booking. Updates DB via callback.",
)
