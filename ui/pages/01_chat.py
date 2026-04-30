import json

import httpx
import streamlit as st

API_BASE = "http://localhost:8000/api"

st.set_page_config(page_title="Chat - Travel Planner", page_icon="💬", layout="wide")
st.title("💬 여행 계획 채팅")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "trip_id" not in st.session_state:
    st.session_state.trip_id = None
if "trip_request" not in st.session_state:
    st.session_state.trip_request = None


def create_trip_if_needed(trip_request: dict) -> str | None:
    """Parse trip_request and create a trip via API."""
    try:
        response = httpx.post(
            f"{API_BASE}/trip",
            json=trip_request,
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            return data["id"]
    except httpx.RequestError:
        st.error("서버에 연결할 수 없습니다. FastAPI 서버가 실행 중인지 확인하세요.")
    return None


def send_chat_message(trip_id: str, message: str) -> dict | None:
    """Send a chat message to the agent and get a reply."""
    try:
        response = httpx.post(
            f"{API_BASE}/trip/{trip_id}/chat",
            json={"message": message},
            timeout=60,
        )
        if response.status_code == 200:
            return response.json()
    except httpx.RequestError:
        st.error("서버에 연결할 수 없습니다.")
    return None


# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Show trip request if extracted
if st.session_state.trip_request:
    with st.sidebar:
        st.subheader("📋 여행 정보")
        st.json(st.session_state.trip_request)
        if st.button("🚀 일정 생성 시작"):
            try:
                resp = httpx.post(
                    f"{API_BASE}/trip/{st.session_state.trip_id}/start-pipeline",
                    json={"message": json.dumps(st.session_state.trip_request, ensure_ascii=False)},
                    timeout=10,
                )
                if resp.status_code == 200:
                    st.switch_page("pages/02_progress.py")
                else:
                    detail = resp.json().get("detail", "알 수 없는 오류")
                    st.error(f"파이프라인 시작 실패: {detail}")
            except httpx.RequestError:
                st.error("서버에 연결할 수 없습니다.")

# Chat input
if prompt := st.chat_input("여행 계획을 알려주세요! (예: 4월에 파리 3일 여행 가고 싶어)"):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Create a temporary trip if none exists (for chat session)
    if not st.session_state.trip_id:
        trip_data = {
            "city": "TBD",
            "start_date": "2026-01-01",
            "end_date": "2026-01-02",
            "preferences": {},
        }
        trip_id = create_trip_if_needed(trip_data)
        if trip_id:
            st.session_state.trip_id = trip_id

    # Send message to agent
    if st.session_state.trip_id:
        with st.chat_message("assistant"):
            with st.spinner("생각하는 중..."):
                result = send_chat_message(st.session_state.trip_id, prompt)

            if result:
                trip_request = result.get("trip_request")

                if trip_request:
                    # 정보가 모두 추출된 경우 — JSON 대신 친근한 요약을 표시
                    city = trip_request.get("city", "")
                    start = trip_request.get("start_date", "")
                    end = trip_request.get("end_date", "")
                    place_names = [
                        p.get("place_name") or p.get("name") or ""
                        for p in trip_request.get("places", [])
                    ]
                    place_names = [n for n in place_names if n]

                    summary_lines = [
                        "좋아요! 여행 계획을 정리했어요. ✈️",
                        "",
                        f"- **목적지:** {city}",
                        f"- **기간:** {start} ~ {end}",
                    ]
                    if place_names:
                        summary_lines.append(f"- **추천 장소 ({len(place_names)}곳):** " + ", ".join(place_names))
                    summary_lines.append("")
                    summary_lines.append("왼쪽 사이드바에서 확인하시고, **🚀 일정 생성 시작** 버튼을 눌러주세요.")

                    display_reply = "\n".join(summary_lines)
                    st.markdown(display_reply)
                    st.session_state.messages.append({"role": "assistant", "content": display_reply})
                    st.session_state.trip_request = trip_request
                    st.rerun()
                else:
                    # 아직 정보 수집 중인 경우 — 모델 응답을 그대로 표시
                    reply = result["reply"]
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
