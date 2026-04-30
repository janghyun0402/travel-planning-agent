import json
from datetime import date

from pydantic import BaseModel, field_validator


class TripPreferences(BaseModel):
    budget: str | None = None
    companions: str | None = None
    walk_limit_km: float = 1.5
    cafe_preference: bool = False
    notes: str | None = None


class TripCreateRequest(BaseModel):
    city: str
    start_date: date
    end_date: date
    preferences: TripPreferences = TripPreferences()


class TripResponse(BaseModel):
    id: str
    city: str
    start_date: date
    end_date: date
    preferences: dict
    status: str
    progress_total: int
    progress_done: int
    final_response: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("preferences", mode="before")
    @classmethod
    def parse_preferences(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


class ChatMessageRequest(BaseModel):
    message: str


class ChatMessageResponse(BaseModel):
    reply: str
    trip_request: dict | None = None


class PlaceResponse(BaseModel):
    id: str
    name: str
    address: str | None
    google_maps_url: str | None
    category: str | None
    reservation_status: str | None
    reservation_lead_time: str | None
    booking_method: dict | None = None
    operating_hours: dict | None = None
    last_order: str | None
    break_time: str | None
    restrictions: dict | None = None
    payment_info: dict | None = None
    parking_info: str | None
    rating: float | None
    review_count: int | None
    price_level: str | None
    lat: float | None = None
    lng: float | None = None
    evidence_urls: list[str] | None = None
    review_snippets: list[str] | None = None

    model_config = {"from_attributes": True}

    @field_validator(
        "booking_method",
        "operating_hours",
        "restrictions",
        "payment_info",
        "evidence_urls",
        "review_snippets",
        mode="before",
    )
    @classmethod
    def _parse_json_field(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return None
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return v


class SlotResponse(BaseModel):
    id: str
    day_number: int
    slot_order: int
    slot_date: date
    time_start: str | None
    time_end: str | None
    place_id: str | None
    place: PlaceResponse | None = None
    travel_minutes: int | None
    travel_method: str | None
    notes: str | None
    is_reserved: bool

    model_config = {"from_attributes": True}


class ItineraryResponse(BaseModel):
    trip: TripResponse
    days: dict[int, list[SlotResponse]]
