import streamlit as st

st.set_page_config(
    page_title="Travel Planning Agent",
    page_icon="✈️",
    layout="wide",
)

st.title("✈️ Travel Planning Agent")
st.markdown("채팅으로 여행 계획을 세워보세요. 도시, 날짜, 선호도를 알려주시면 맞춤 일정을 만들어 드립니다.")

# Redirect to chat page
st.switch_page("pages/01_chat.py")
