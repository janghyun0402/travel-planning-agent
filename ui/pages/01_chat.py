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
                reply = result["reply"]
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})

                # Check if trip_request was extracted
                if result.get("trip_request"):
                    st.session_state.trip_request = result["trip_request"]
                    st.rerun()
