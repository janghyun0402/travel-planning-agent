# travel-planning-agent

Google ADK 기반 Multi-LLM 에이전트 + browser-use를 결합한 지능형 여행 계획 비서

## TODO (직접 해야 할 것들)

- [x] `.env` 파일 생성 후 `GEMINI_API_KEY` 설정 ✅ 완료
- [x] `.env` 파일에 `GOOGLE_MAPS_API_KEY` 설정 ✅ 완료 (Distance Matrix API + Places API 활성화 필요)
- [x] Playwright 브라우저 설치: `.venv/bin/playwright install chromium` ✅ 완료
- [x] `.env` 파일에 `SERPAPI_API_KEY` 설정 ✅ 완료
- [x] `.env` 파일에 `TAVILY_API_KEY` 설정 ✅ 완료

## 실행 방법

```bash
# 터미널 1: FastAPI 서버
.venv/bin/uvicorn api.main:app --reload

# 터미널 2: Streamlit UI
.venv/bin/streamlit run ui/app.py
```
