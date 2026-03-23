import time

import httpx
import streamlit as st

API_BASE = "http://localhost:8000/api"

st.set_page_config(page_title="Progress - Travel Planner", page_icon="⏳", layout="wide")
st.title("⏳ 일정 생성 진행 상황")

# Redirect if no trip
if "trip_id" not in st.session_state or not st.session_state.trip_id:
    st.warning("먼저 채팅에서 여행 계획을 입력해주세요.")
    time.sleep(1)
    st.switch_page("pages/01_chat.py")

STAGE_LABELS = {
    "pending": ("⏸️", "대기 중"),
    "drafting": ("📝", "초안 작성 중"),
    "crawling": ("🔍", "정보 수집 중"),
    "merging": ("🔀", "데이터 병합 중"),
    "done": ("✅", "완료"),
    "error": ("❌", "오류 발생"),
}

STAGE_ORDER = ["pending", "drafting", "crawling", "merging", "done"]


def fetch_trip_status(trip_id: str) -> dict | None:
    try:
        response = httpx.get(f"{API_BASE}/trip/{trip_id}", timeout=10)
        if response.status_code == 200:
            return response.json()
    except httpx.RequestError:
        st.error("서버에 연결할 수 없습니다. FastAPI 서버가 실행 중인지 확인하세요.")
    return None


trip_id = st.session_state.trip_id
data = fetch_trip_status(trip_id)

if data is None:
    st.error("여행 정보를 불러올 수 없습니다.")
    st.stop()

status = data["status"]
progress_total = data.get("progress_total", 0)
progress_done = data.get("progress_done", 0)

# Stage display
icon, label = STAGE_LABELS.get(status, ("❓", status))
st.subheader(f"{icon} 현재 단계: {label}")

# Stage progress indicators
cols = st.columns(len(STAGE_ORDER))
current_idx = STAGE_ORDER.index(status) if status in STAGE_ORDER else -1
for i, stage in enumerate(STAGE_ORDER):
    s_icon, s_label = STAGE_LABELS[stage]
    with cols[i]:
        if i < current_idx:
            st.success(f"✅ {s_label}")
        elif i == current_idx:
            st.info(f"▶️ {s_label}")
        else:
            st.container().markdown(f"⬜ {s_label}")

# Progress bar
st.markdown("---")
if progress_total > 0:
    progress_ratio = min(progress_done / progress_total, 1.0)
    st.progress(progress_ratio, text=f"{progress_done} / {progress_total} 완료")
else:
    st.progress(0.0, text="진행률 계산 중...")

# Trip info in sidebar
with st.sidebar:
    st.subheader("📋 여행 정보")
    st.write(f"**도시:** {data.get('city', '-')}")
    st.write(f"**기간:** {data.get('start_date', '-')} ~ {data.get('end_date', '-')}")

# Handle terminal states
if status == "done":
    st.balloons()
    st.success("일정 생성이 완료되었습니다! 잠시 후 일정 페이지로 이동합니다.")
    time.sleep(2)
    st.switch_page("pages/03_itinerary.py")
elif status == "error":
    st.error("일정 생성 중 오류가 발생했습니다. 채팅에서 다시 시도해주세요.")
    if st.button("💬 채팅으로 돌아가기"):
        st.switch_page("pages/01_chat.py")
    st.stop()

# Auto-refresh every 3 seconds
time.sleep(3)
st.rerun()
