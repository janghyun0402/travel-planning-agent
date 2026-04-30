import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Trip, Place, ItinerarySlot, Alternative


# --- Trip ---

async def create_trip(session: AsyncSession, city: str, start_date, end_date, preferences: dict) -> Trip:
    trip = Trip(
        city=city,
        start_date=start_date,
        end_date=end_date,
        preferences=json.dumps(preferences, ensure_ascii=False),
    )
    session.add(trip)
    await session.commit()
    await session.refresh(trip)
    return trip


async def get_trip(session: AsyncSession, trip_id: str) -> Trip | None:
    return await session.get(Trip, trip_id)


async def update_trip_status(session: AsyncSession, trip_id: str, status: str, progress_done: int | None = None):
    trip = await session.get(Trip, trip_id)
    if trip:
        trip.status = status
        if progress_done is not None:
            trip.progress_done = progress_done
        await session.commit()


# --- Place ---

async def create_place(session: AsyncSession, trip_id: str, **kwargs) -> Place:
    place = Place(trip_id=trip_id, **kwargs)
    session.add(place)
    await session.commit()
    await session.refresh(place)
    return place


async def get_places_by_trip(session: AsyncSession, trip_id: str) -> list[Place]:
    result = await session.execute(select(Place).where(Place.trip_id == trip_id))
    return list(result.scalars().all())


async def update_place(session: AsyncSession, place_id: str, **kwargs) -> Place | None:
    place = await session.get(Place, place_id)
    if place:
        for key, value in kwargs.items():
            if hasattr(place, key):
                setattr(place, key, value)
        await session.commit()
        await session.refresh(place)
    return place


# --- ItinerarySlot ---

async def create_slot(session: AsyncSession, **kwargs) -> ItinerarySlot:
    slot = ItinerarySlot(**kwargs)
    session.add(slot)
    await session.commit()
    await session.refresh(slot)
    return slot


async def get_slots_by_trip(session: AsyncSession, trip_id: str) -> list[ItinerarySlot]:
    result = await session.execute(
        select(ItinerarySlot)
        .options(selectinload(ItinerarySlot.place))
        .where(ItinerarySlot.trip_id == trip_id)
        .order_by(ItinerarySlot.day_number, ItinerarySlot.slot_order)
    )
    return list(result.scalars().all())


# --- Alternative ---

async def create_alternative(session: AsyncSession, **kwargs) -> Alternative:
    alt = Alternative(**kwargs)
    session.add(alt)
    await session.commit()
    await session.refresh(alt)
    return alt
