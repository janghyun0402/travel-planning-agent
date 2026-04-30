import uuid
from datetime import datetime

from sqlalchemy import Boolean, Date, Float, Integer, String, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    city: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[str] = mapped_column(Date, nullable=False)
    end_date: Mapped[str] = mapped_column(Date, nullable=False)
    preferences: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    final_response: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    places: Mapped[list["Place"]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    slots: Mapped[list["ItinerarySlot"]] = relationship(back_populates="trip", cascade="all, delete-orphan")


class Place(Base):
    __tablename__ = "places"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str | None] = mapped_column(String)
    google_maps_url: Mapped[str | None] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String)
    reservation_status: Mapped[str | None] = mapped_column(String)  # required|recommended|not_needed|unknown
    reservation_lead_time: Mapped[str | None] = mapped_column(String)
    booking_method: Mapped[str | None] = mapped_column(Text)  # JSON
    operating_hours: Mapped[str | None] = mapped_column(Text)  # JSON
    last_order: Mapped[str | None] = mapped_column(String)
    break_time: Mapped[str | None] = mapped_column(String)
    restrictions: Mapped[str | None] = mapped_column(Text)  # JSON
    payment_info: Mapped[str | None] = mapped_column(Text)  # JSON
    parking_info: Mapped[str | None] = mapped_column(String)
    rating: Mapped[float | None] = mapped_column(Float)
    review_count: Mapped[int | None] = mapped_column(Integer)
    price_level: Mapped[str | None] = mapped_column(String)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    evidence_urls: Mapped[str | None] = mapped_column(Text)  # JSON array
    review_snippets: Mapped[str | None] = mapped_column(Text)  # JSON array
    raw_gmaps_data: Mapped[str | None] = mapped_column(Text)  # JSON
    raw_tripadvisor_data: Mapped[str | None] = mapped_column(Text)  # JSON
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    trip: Mapped["Trip"] = relationship(back_populates="places")
    slots: Mapped[list["ItinerarySlot"]] = relationship(back_populates="place")
    alternatives: Mapped[list["Alternative"]] = relationship(back_populates="place")


class ItinerarySlot(Base):
    __tablename__ = "itinerary_slots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_order: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_date: Mapped[str] = mapped_column(Date, nullable=False)
    time_start: Mapped[str | None] = mapped_column(String)
    time_end: Mapped[str | None] = mapped_column(String)
    place_id: Mapped[str | None] = mapped_column(ForeignKey("places.id"))
    travel_minutes: Mapped[int | None] = mapped_column(Integer)
    travel_method: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)
    is_reserved: Mapped[bool] = mapped_column(Boolean, default=False)

    trip: Mapped["Trip"] = relationship(back_populates="slots")
    place: Mapped["Place"] = relationship(back_populates="slots")


class Alternative(Base):
    __tablename__ = "alternatives"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), nullable=False)
    slot_id: Mapped[str | None] = mapped_column(ForeignKey("itinerary_slots.id"))
    place_id: Mapped[str | None] = mapped_column(ForeignKey("places.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=1)

    place: Mapped["Place"] = relationship(back_populates="alternatives")
