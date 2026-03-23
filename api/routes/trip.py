import asyncio
import json
import logging
import re
from collections import defaultdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from sqlalchemy.ext.asyncio import AsyncSession

from agents.chat_agent import chat_agent
from agents.root_agent import pipeline_agent
from api.dependencies import get_db
from api.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ItineraryResponse,
    PlaceResponse,
    SlotResponse,
    TripCreateRequest,
    TripResponse,
)
from db import crud
from db.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trip")

# 세션 서비스 (ChatAgent용, PipelineAgent용 각각)
chat_session_service = InMemorySessionService()
pipeline_session_service = InMemorySessionService()

# ChatAgent용 러너/세션
_chat_runners: dict[str, Runner] = {}
_chat_sessions: dict[str, str] = {}

# PipelineAgent용 러너/세션
_pipeline_runners: dict[str, Runner] = {}
_pipeline_sessions: dict[str, str] = {}


async def _get_chat_runner(trip_id: str) -> tuple[Runner, str]:
    """ChatAgent용 러너와 세션을 가져오거나 생성한다."""
    if trip_id not in _chat_runners:
        runner = Runner(
            agent=chat_agent,
            app_name="travel_chat",
            session_service=chat_session_service,
        )
        _chat_runners[trip_id] = runner

        session = await chat_session_service.create_session(
            app_name="travel_chat",
            user_id=f"user_{trip_id}",
        )
        _chat_sessions[trip_id] = session.id

    return _chat_runners[trip_id], _chat_sessions[trip_id]


async def _run_pipeline(trip_id: str, trip_request: dict):
    """PipelineAgent를 백그라운드에서 실행한다."""
    try:
        async with async_session() as db:
            await crud.update_trip_status(db, trip_id, "drafting")

        runner = Runner(
            agent=pipeline_agent,
            app_name="travel_pipeline",
            session_service=pipeline_session_service,
        )

        session = await pipeline_session_service.create_session(
            app_name="travel_pipeline",
            user_id=f"pipeline_{trip_id}",
            state={
                "trip_request": json.dumps(trip_request, ensure_ascii=False),
                "trip_id": trip_id,
            },
        )

        # 파이프라인 실행 (빈 메시지로 트리거)
        trigger = Content(role="user", parts=[Part(text="Generate the travel itinerary.")])

        async for event in runner.run_async(
            user_id=f"pipeline_{trip_id}",
            session_id=session.id,
            new_message=trigger,
        ):
            # 진행 상태 업데이트 (에이전트 이름 기반)
            if event.author:
                status_map = {
                    "DraftAgent": "drafting",
                    "CrawlerAgent": "crawling",
                    "MergerAgent": "merging",
                    "ItineraryAgent": "finalizing",
                }
                new_status = status_map.get(event.author)
                if new_status:
                    async with async_session() as db:
                        await crud.update_trip_status(db, trip_id, new_status)

        async with async_session() as db:
            await crud.update_trip_status(db, trip_id, "done")

        logger.info("Pipeline completed for trip %s", trip_id)

    except Exception:
        logger.exception("Pipeline failed for trip %s", trip_id)
        async with async_session() as db:
            await crud.update_trip_status(db, trip_id, "error")


def _extract_json_from_text(text: str) -> dict | None:
    """텍스트에서 JSON 블록을 추출한다."""
    # 먼저 순수 JSON 파싱 시도
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass

    # ```json 블록에서 추출 시도
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


@router.post("", response_model=TripResponse)
async def create_trip(request: TripCreateRequest, db: AsyncSession = Depends(get_db)):
    trip = await crud.create_trip(
        db,
        city=request.city,
        start_date=request.start_date,
        end_date=request.end_date,
        preferences=request.preferences.model_dump(),
    )
    return trip


@router.post("/{trip_id}/chat", response_model=ChatMessageResponse)
async def chat_with_agent(trip_id: str, request: ChatMessageRequest, db: AsyncSession = Depends(get_db)):
    """ChatAgent와 멀티턴 대화. trip_request가 확정되면 자동 반환."""
    trip = await crud.get_trip(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    runner, session_id = await _get_chat_runner(trip_id)

    user_content = Content(
        role="user",
        parts=[Part(text=request.message)],
    )

    reply_text = ""
    async for event in runner.run_async(
        user_id=f"user_{trip_id}",
        session_id=session_id,
        new_message=user_content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    reply_text += part.text

    trip_request = _extract_json_from_text(reply_text)

    return ChatMessageResponse(reply=reply_text, trip_request=trip_request)


@router.post("/{trip_id}/start-pipeline")
async def start_pipeline(
    trip_id: str,
    request: ChatMessageRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """trip_request를 받아 PipelineAgent를 백그라운드로 실행한다."""
    trip = await crud.get_trip(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if trip.status not in ("pending", "error"):
        raise HTTPException(status_code=400, detail=f"Pipeline already {trip.status}")

    trip_request = json.loads(request.message)

    # trip 정보 업데이트
    trip.city = trip_request.get("city", trip.city)
    trip.preferences = json.dumps(trip_request.get("preferences", {}), ensure_ascii=False)
    await db.commit()

    # 백그라운드에서 파이프라인 실행
    background_tasks.add_task(_run_pipeline, trip_id, trip_request)

    return {"status": "pipeline_started", "trip_id": trip_id}


@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip(trip_id: str, db: AsyncSession = Depends(get_db)):
    trip = await crud.get_trip(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.get("/{trip_id}/places", response_model=list[PlaceResponse])
async def get_trip_places(trip_id: str, db: AsyncSession = Depends(get_db)):
    trip = await crud.get_trip(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    places = await crud.get_places_by_trip(db, trip_id)
    return places


@router.get("/{trip_id}/itinerary", response_model=ItineraryResponse)
async def get_trip_itinerary(trip_id: str, db: AsyncSession = Depends(get_db)):
    trip = await crud.get_trip(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    slots = await crud.get_slots_by_trip(db, trip_id)
    days: dict[int, list[SlotResponse]] = defaultdict(list)
    for slot in slots:
        days[slot.day_number].append(SlotResponse.model_validate(slot))

    return ItineraryResponse(
        trip=TripResponse.model_validate(trip),
        days=dict(days),
    )
