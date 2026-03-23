"""ItineraryAgent - 검증된 장소 데이터를 기반으로 최종 일정을 최적화한다.

LlmAgent로 일정 최적화를 수행하고,
after_agent_callback에서 DB 저장을 확정적으로 실행한다.
"""

import json
import logging

from google.adk.agents import LlmAgent

from tools.geocoding_tools import calculate_distance
from tools.db_tools import save_itinerary_to_db

logger = logging.getLogger(__name__)

ITINERARY_AGENT_INSTRUCTION = """You are an itinerary optimization specialist. Create the final
optimized travel itinerary based on validated place data and the user's trip request.

## Data

Validated places:
{validated_places}

Trip request:
{trip_request}

Reservation info:
{reservation_info}

## Optimization Rules

1. **Operating Hours**: Schedule visits only during open hours.
2. **Reservation Lead Time**: Flag places requiring advance booking.
3. **Travel Time**: Use `calculate_distance` to calculate travel time between consecutive places.
   - Prefer walking for distances < walk_limit_km.
   - Use transit for longer distances.
4. **Daily Flow**:
   - Morning: attractions/landmarks (09:00-12:00)
   - Lunch: restaurants (12:00-14:00)
   - Afternoon: attractions/museums/shopping (14:00-17:00)
   - Dinner: restaurants (18:00-20:00)
   - Evening: entertainment/night views (20:00-22:00)
5. **Proximity Clustering**: Group nearby places on the same day.
6. **Alternatives**: For problematic slots, suggest alternatives with reasons.
7. **Reservation Info**: Include reservation details from reservation_info for places that need booking.

## Place ID Mapping

Each place in validated_places has a "place_id" field (UUID from the database).
You MUST include the corresponding place_id in each slot so the itinerary links to the DB record.
Match by place name: find the place in validated_places whose "name" matches the slot's place, and copy its "place_id" value.

## Output

Output ONLY a JSON object. No other text before or after the JSON.

The JSON must have this structure:
{
  "days": [
    {
      "day_number": 1,
      "date": "2026-04-10",
      "slots": [
        {
          "slot_order": 1,
          "time_start": "09:00",
          "time_end": "11:30",
          "place_name": "Eiffel Tower",
          "place_id": "uuid-from-validated-places",
          "travel_minutes": 0,
          "travel_method": "start",
          "notes": "Arrive early to avoid queues. Reservation recommended 60 days in advance.",
          "is_reserved": false
        }
      ]
    }
  ]
}

Do NOT include trip_id. Do NOT call save_itinerary_to_db. Just output the JSON.
"""


async def _save_itinerary_callback(*, callback_context, **kwargs) -> None:
    """ItineraryAgent 완료 후 final_itinerary를 DB에 저장한다."""
    state = callback_context.state or {}

    trip_id = state.get("trip_id")
    if not trip_id:
        logger.error("trip_id가 session state에 없음")
        return

    itinerary_raw = state.get("final_itinerary", "{}")

    # 파싱
    if isinstance(itinerary_raw, dict):
        itinerary = itinerary_raw
    elif isinstance(itinerary_raw, str):
        text = itinerary_raw.strip()
        # ```json 블록 추출
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
        # 여러 JSON 블록이 있을 수 있으므로 마지막 유효한 JSON 객체 찾기
        try:
            itinerary = json.loads(text)
        except json.JSONDecodeError:
            # tool 응답과 섞여있을 수 있으므로, { 로 시작하는 마지막 블록 시도
            last_brace = text.rfind("{")
            if last_brace >= 0:
                try:
                    itinerary = json.loads(text[last_brace:])
                except json.JSONDecodeError:
                    logger.error("final_itinerary JSON 파싱 실패: %s", text[:300])
                    return
            else:
                logger.error("final_itinerary에 JSON 없음: %s", text[:300])
                return
    else:
        logger.error("final_itinerary 타입 에러: %s", type(itinerary_raw))
        return

    if not isinstance(itinerary, dict):
        logger.error("final_itinerary가 dict 아님: %s", type(itinerary))
        return

    days = itinerary.get("days", [])
    logger.info("일정 DB 저장 시작: %d일, trip_id=%s", len(days), trip_id)

    if not days:
        logger.warning("days가 비어있음. final_itinerary 내용: %s", str(itinerary)[:500])
        return

    itinerary["trip_id"] = trip_id

    try:
        result = await save_itinerary_to_db(itinerary)
        logger.info(
            "일정 DB 저장 완료: slots=%s, alternatives=%s",
            result.get("slots_saved"),
            result.get("alternatives_saved"),
        )
    except Exception:
        logger.exception("일정 DB 저장 실패")


itinerary_agent = LlmAgent(
    name="ItineraryAgent",
    model="gemini-2.5-flash",
    instruction=ITINERARY_AGENT_INSTRUCTION,
    output_key="final_itinerary",
    tools=[calculate_distance],
    after_agent_callback=_save_itinerary_callback,
    description="Optimizes the final itinerary. Saves to DB via callback.",
)
