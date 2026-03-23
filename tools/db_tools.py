import json
from datetime import date

from db.database import async_session
from db.crud import create_place, create_slot, create_alternative


async def save_place_to_db(place_data: dict) -> dict:
    """Save a validated place to the database.

    Args:
        place_data: Dict containing place information. Must include 'trip_id' and 'name'.
            Optional fields: address, google_maps_url, category, reservation_status,
            reservation_lead_time, booking_method, operating_hours, last_order,
            break_time, restrictions, payment_info, parking_info, rating,
            review_count, price_level, evidence_urls, review_snippets,
            confidence_score, raw_gmaps_data, raw_tripadvisor_data.

    Returns:
        Dict with saved place id and name.
    """
    trip_id = place_data.pop("trip_id", None)
    if not trip_id:
        return {"error": "trip_id is required"}

    # Place 모델에 존재하는 필드만 허용
    allowed_fields = {
        "name", "address", "google_maps_url", "category",
        "reservation_status", "reservation_lead_time", "booking_method",
        "operating_hours", "last_order", "break_time", "restrictions",
        "payment_info", "parking_info", "rating", "review_count",
        "price_level", "evidence_urls", "review_snippets",
        "raw_gmaps_data", "raw_tripadvisor_data",
    }
    filtered = {k: v for k, v in place_data.items() if k in allowed_fields}

    # Serialize JSON fields
    json_fields = [
        "booking_method", "operating_hours", "restrictions",
        "payment_info", "evidence_urls", "review_snippets",
        "raw_gmaps_data", "raw_tripadvisor_data",
    ]
    for field in json_fields:
        if field in filtered and isinstance(filtered[field], (dict, list)):
            filtered[field] = json.dumps(filtered[field], ensure_ascii=False)

    async with async_session() as session:
        place = await create_place(session, trip_id=trip_id, **filtered)
        return {"id": place.id, "name": place.name, "status": "saved"}


async def save_itinerary_to_db(itinerary_data: dict) -> dict:
    """Save the final itinerary (slots and alternatives) to the database.

    Args:
        itinerary_data: Dict with 'trip_id' and 'days' list. Each day has
            'day_number', 'date', and 'slots'. Each slot has 'slot_order',
            'time_start', 'time_end', 'place_id', optional 'travel_minutes',
            'travel_method', 'notes', 'is_reserved'. Slots may include
            'alternatives' list with 'place_id', 'reason', 'priority'.

    Returns:
        Dict with count of saved slots and alternatives.
    """
    trip_id = itinerary_data.get("trip_id")
    if not trip_id:
        return {"error": "trip_id is required"}

    days = itinerary_data.get("days", [])
    slot_count = 0
    alt_count = 0

    async with async_session() as session:
        for day in days:
            day_number = day.get("day_number", 1)
            raw_date = day.get("date", "")
            slot_date = (
                date.fromisoformat(raw_date)
                if isinstance(raw_date, str) and raw_date
                else raw_date
            )

            for slot_data in day.get("slots", []):
                slot = await create_slot(
                    session,
                    trip_id=trip_id,
                    day_number=day_number,
                    slot_order=slot_data.get("slot_order", 0),
                    slot_date=slot_date,
                    time_start=slot_data.get("time_start"),
                    time_end=slot_data.get("time_end"),
                    place_id=slot_data.get("place_id"),
                    travel_minutes=slot_data.get("travel_minutes"),
                    travel_method=slot_data.get("travel_method"),
                    notes=slot_data.get("notes"),
                    is_reserved=slot_data.get("is_reserved", False),
                )
                slot_count += 1

                for alt_data in slot_data.get("alternatives", []):
                    await create_alternative(
                        session,
                        trip_id=trip_id,
                        slot_id=slot.id,
                        place_id=alt_data.get("place_id"),
                        reason=alt_data.get("reason"),
                        priority=alt_data.get("priority", 1),
                    )
                    alt_count += 1

    return {"slots_saved": slot_count, "alternatives_saved": alt_count, "status": "saved"}
