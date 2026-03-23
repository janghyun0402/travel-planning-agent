"""에이전트 간 데이터 교환용 Pydantic 스키마."""

from pydantic import BaseModel, Field


# --- ChatAgent output ---

class TripPreferences(BaseModel):
    budget: str | None = Field(None, description="low / medium / high / luxury")
    companions: str | None = Field(None, description="solo / couple / family / friends")
    walk_limit_km: float = Field(1.5, description="Max walking distance per segment in km")
    cafe_preference: bool = Field(False, description="Whether the user enjoys cafes")
    max_places_per_day: int = Field(4, description="Maximum number of places to visit per day. Default 4, range 2-6.")
    notes: str | None = Field(None, description="Any other preferences or constraints")


class RecommendedPlace(BaseModel):
    place_name: str = Field(description="장소 이름")
    category: str = Field(description="카테고리: museum, restaurant, cafe, attraction, park, market, shopping, entertainment, landmark")
    reason: str = Field(description="추천 이유 (15자 이내)")


class TripRequest(BaseModel):
    city: str = Field(description="Destination city")
    start_date: str = Field(description="Start date in YYYY-MM-DD format")
    end_date: str = Field(description="End date in YYYY-MM-DD format")
    preferences: TripPreferences = Field(default_factory=TripPreferences)
    places: list[RecommendedPlace] = Field(description="추천 장소 리스트")


# --- CrawlerAgent output ---

class PlaceCrawlData(BaseModel):
    name: str = Field(description="Place name")
    address: str | None = Field(None, description="Full address")
    google_maps_url: str | None = Field(None, description="Google Maps URL")
    category: str | None = Field(None, description="Place category")
    operating_hours: str | None = Field(None, description="Operating hours as JSON string")
    rating: float | None = Field(None, description="Rating (0-5)")
    review_count: int | None = Field(None, description="Number of reviews")
    price_level: str | None = Field(None, description="Price level: free, $, $$, $$$, $$$$")
    reservation_status: str | None = Field(None, description="required / recommended / not_needed / unknown")
    reservation_lead_time: str | None = Field(None, description="e.g. '2 days', '1 week'")
    booking_method: str | None = Field(None, description="Booking method info as JSON string")
    restrictions: str | None = Field(None, description="Restrictions as JSON string")
    review_snippets: str | None = Field(None, description="Review excerpts as JSON array string")
    evidence_urls: str | None = Field(None, description="Source URLs as JSON array string")


class CrawlResult(BaseModel):
    city: str = Field(description="Destination city")
    places: list[PlaceCrawlData] = Field(description="Crawled place data")


# --- MergerAgent output ---

class ValidatedPlace(BaseModel):
    name: str = Field(description="Place name")
    address: str | None = Field(None)
    google_maps_url: str | None = Field(None)
    category: str | None = Field(None)
    reservation_status: str | None = Field(None, description="required / recommended / not_needed / unknown")
    reservation_lead_time: str | None = Field(None)
    booking_method: str | None = Field(None)
    operating_hours: str | None = Field(None, description="JSON string of hours")
    last_order: str | None = Field(None)
    break_time: str | None = Field(None)
    restrictions: str | None = Field(None, description="JSON string of restrictions")
    rating: float | None = Field(None)
    review_count: int | None = Field(None)
    price_level: str | None = Field(None)
    evidence_urls: str | None = Field(None, description="JSON array string")
    review_snippets: str | None = Field(None, description="JSON array string")
    place_id: str | None = Field(None, description="UUID from DB after saving")


# --- ItineraryAgent output ---

class ItinerarySlotOutput(BaseModel):
    day_number: int = Field(description="Day number")
    slot_order: int = Field(description="Order within the day")
    date: str = Field(description="Date in YYYY-MM-DD format")
    time_start: str = Field(description="Start time HH:MM")
    time_end: str = Field(description="End time HH:MM")
    place_name: str = Field(description="Place name")
    place_id: str | None = Field(None, description="Place UUID from DB")
    travel_minutes: int | None = Field(None, description="Travel time from previous slot")
    travel_method: str | None = Field(None, description="walk / transit / taxi")
    notes: str | None = Field(None, description="e.g. 'arrive early for queue'")
    is_reserved: bool = Field(False, description="Whether reservation is confirmed")


class AlternativeOutput(BaseModel):
    slot_day: int = Field(description="Day number of the slot this replaces")
    slot_order: int = Field(description="Order of the slot this replaces")
    place_name: str = Field(description="Alternative place name")
    reason: str = Field(description="Why this alternative is suggested")


class FinalItinerary(BaseModel):
    slots: list[ItinerarySlotOutput] = Field(description="Ordered itinerary slots")
    alternatives: list[AlternativeOutput] = Field(default_factory=list, description="Alternative suggestions")
