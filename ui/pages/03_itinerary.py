import sys
import time
from pathlib import Path

import httpx
import streamlit as st

# Add parent directory so we can import components
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.place_card import render_place_card
from components.map_view import render_map

API_BASE = "http://localhost:8000/api"

st.set_page_config(page_title="Itinerary - Travel Planner", page_icon="📅", layout="wide")
st.title("📅 여행 일정")

# Redirect if no trip
if "trip_id" not in st.session_state or not st.session_state.trip_id:
    st.warning("먼저 채팅에서 여행 계획을 입력해주세요.")
    time.sleep(1)
    st.switch_page("pages/01_chat.py")

TRAVEL_ICONS = {
    "walk": "🚶",
    "walking": "🚶",
    "도보": "🚶",
    "taxi": "🚕",
    "택시": "🚕",
    "bus": "🚌",
    "버스": "🚌",
    "subway": "🚇",
    "metro": "🚇",
    "지하철": "🚇",
    "car": "🚗",
    "자동차": "🚗",
    "train": "🚆",
    "기차": "🚆",
}


def fetch_itinerary(trip_id: str) -> dict | None:
    try:
        response = httpx.get(f"{API_BASE}/trip/{trip_id}/itinerary", timeout=10)
        if response.status_code == 200:
            return response.json()
    except httpx.RequestError:
        pass
    return None


def fetch_places(trip_id: str) -> list:
    try:
        response = httpx.get(f"{API_BASE}/trip/{trip_id}/places", timeout=10)
        if response.status_code == 200:
            return response.json()
    except httpx.RequestError:
        pass
    return []


trip_id = st.session_state.trip_id
data = fetch_itinerary(trip_id)
places = fetch_places(trip_id)

trip = data.get("trip", {}) if data else {}
days = data.get("days", {}) if data else {}

if not days and not places:
    st.info("아직 생성된 일정이 없습니다.")
    st.stop()

# Trip info in sidebar header
with st.sidebar:
    st.subheader("📋 여행 정보")
    st.write(f"**도시:** {trip.get('city', '-')}")
    st.write(f"**기간:** {trip.get('start_date', '-')} ~ {trip.get('end_date', '-')}")
    st.markdown("---")

if days:
    # Day tabs
    day_numbers = sorted(int(d) for d in days.keys())
    tab_labels = [f"Day {d}" for d in day_numbers]
    tabs = st.tabs(tab_labels)

    # Track selected day for sidebar map
    if "selected_day_idx" not in st.session_state:
        st.session_state.selected_day_idx = 0

    for tab_idx, (tab, day_num) in enumerate(zip(tabs, day_numbers)):
        with tab:
            slots = days[str(day_num)]
            slots_sorted = sorted(slots, key=lambda s: s.get("slot_order", 0))

            # Collect places for this day's map
            day_places = []

            for i, slot in enumerate(slots_sorted):
                place = slot.get("place")
                time_start = slot.get("time_start", "")
                time_end = slot.get("time_end", "")
                travel_minutes = slot.get("travel_minutes")
                travel_method = slot.get("travel_method", "")
                notes = slot.get("notes", "")

                # Travel info between slots
                if i > 0 and travel_minutes:
                    method_icon = TRAVEL_ICONS.get(travel_method.lower() if travel_method else "", "🚶")
                    method_label = travel_method or "이동"
                    st.markdown(
                        f"<div style='text-align:center;color:#888;padding:4px 0;'>"
                        f"{method_icon} {method_label} · {travel_minutes}분</div>",
                        unsafe_allow_html=True,
                    )

                # Time display
                time_display = ""
                if time_start:
                    time_display = time_start
                    if time_end:
                        time_display += f" ~ {time_end}"

                if place:
                    day_places.append(place)
                    if time_display:
                        st.caption(f"🕐 {time_display}")
                    render_place_card(place, key_prefix=f"d{day_num}_s{i}_")
                else:
                    # Slot without place (e.g., free time)
                    if time_display:
                        st.markdown(f"**🕐 {time_display}**")
                    if notes:
                        st.info(f"📝 {notes}")

                if slot.get("is_reserved"):
                    st.success("✅ 예약 완료")

                if i < len(slots_sorted) - 1:
                    st.divider()

            # Store places for sidebar map
            if tab_idx == st.session_state.get("selected_day_idx", 0):
                st.session_state["_current_day_places"] = day_places

    # Sidebar map
    with st.sidebar:
        st.subheader("🗺️ 지도")
        map_places = st.session_state.get("_current_day_places", [])
        if map_places:
            render_map(map_places, height=350)
        else:
            st.info("이 날의 장소에 좌표 정보가 없습니다.")

else:
    # No itinerary yet, but places exist — show places only
    st.info("일정은 아직 생성되지 않았지만, 수집된 장소 정보를 확인할 수 있습니다.")
    for i, place in enumerate(places):
        render_place_card(place, key_prefix=f"place_{i}_")
        if i < len(places) - 1:
            st.divider()

    with st.sidebar:
        st.subheader("🗺️ 지도")
        if places:
            render_map(places, height=350)
        else:
            st.info("장소에 좌표 정보가 없습니다.")
