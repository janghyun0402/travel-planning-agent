"""웹사이트에서 여행 관련 실용 정보를 추출한다.

기본: httpx로 HTML 가져오기 + Gemini structured output
폴백: browser-use (JS 렌더링 필요 시에만)
"""

import json
import logging
import re

import google.genai as genai
import httpx
from bs4 import BeautifulSoup

from config.settings import settings

logger = logging.getLogger(__name__)

MIN_CONTENT_LENGTH = 100  # 이 미만이면 JS 렌더링 필요로 판단

EXTRACTION_PROMPT = """다음은 "{place_name}" 관련 웹페이지의 텍스트 내용입니다.
이 텍스트에서 여행자에게 유용한 실용 정보를 추출해주세요.

웹페이지 텍스트:
---
{text}
---

다음 JSON 형식으로 정보를 추출해주세요. 찾을 수 없는 필드는 null로 설정하세요:
{{
  "reservation_status": "required 또는 recommended 또는 not_needed 또는 unknown",
  "reservation_lead_time": "예약 권장 시점 (예: 2 days, 1 week, 60 days)",
  "booking_url": "예약 페이지 URL 또는 null",
  "wait_time_info": "대기 시간 관련 정보 또는 null",
  "tips": ["방문 팁1", "팁2"],
  "restrictions": {{"dress_code": null, "age": null, "group_size": null, "payment": null}},
  "review_snippets": ["유용한 리뷰 발췌1", "발췌2"],
  "break_time": "브레이크타임 정보 또는 null",
  "last_order": "라스트오더 시간 또는 null"
}}

JSON만 출력하세요.
"""


def _extract_text_from_html(html: str) -> str:
    """HTML에서 의미 있는 텍스트를 추출한다."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # 빈 줄 정리
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _parse_json_response(text: str) -> dict:
    """Gemini 응답에서 JSON을 파싱한다."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        logger.warning("Gemini 응답 JSON 파싱 실패: %s", text[:200])
        return {}


async def _extract_with_gemini(text: str, place_name: str) -> dict:
    """Gemini에 텍스트를 보내서 구조화된 정보를 추출한다."""
    prompt = EXTRACTION_PROMPT.format(place_name=place_name, text=text[:8000])

    client = genai.Client(api_key=settings.gemini_api_key)
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    result = _parse_json_response(response.text)

    # JSON 직렬화가 필요한 필드 변환
    for field in ("tips", "review_snippets"):
        if isinstance(result.get(field), list):
            result[field] = json.dumps(result[field], ensure_ascii=False)
    if isinstance(result.get("restrictions"), dict):
        result["restrictions"] = json.dumps(result["restrictions"], ensure_ascii=False)

    return result


async def crawl_and_extract(url: str, place_name: str) -> dict:
    """URL에서 여행 관련 실용 정보를 추출한다.

    1차: httpx로 HTML 가져오기 + Gemini 추출 (2-3초)
    폴백: browser-use (JS 렌더링 필요 시에만, 보수적 판단)

    Args:
        url: 크롤링할 URL
        place_name: 장소 이름

    Returns:
        추출된 정보 dict. 실패 시 빈 dict.
    """
    # 1차: httpx로 시도
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TravelPlannerBot/1.0)"},
        ) as client:
            resp = await client.get(url)

            if resp.status_code != 200:
                logger.warning("HTTP %d for %s — 스킵", resp.status_code, url)
                return {}

            text = _extract_text_from_html(resp.text)

            # Cloudflare/bot 차단 감지
            if len(text) < MIN_CONTENT_LENGTH and ("cloudflare" in resp.text.lower() or "blocked" in resp.text.lower()):
                logger.warning("Cloudflare 차단 감지: %s — 스킵", url)
                return {}

            # JS 렌더링 필요: 텍스트가 극히 짧고 차단이 아닌 경우에만 폴백
            if len(text) < MIN_CONTENT_LENGTH:
                logger.info("텍스트 %d자로 부족 (%s), browser-use 폴백", len(text), url)
                return await _fallback_browser_use(url, place_name, reason="insufficient content")

            # Gemini로 추출
            result = await _extract_with_gemini(text, place_name)
            if result:
                result["source_url"] = url
                result["crawl_method"] = "httpx"
                logger.info("httpx+Gemini 크롤 성공: %s (%s)", place_name, url)
                return result

            logger.warning("Gemini 추출 실패: %s", url)
            return {}

    except httpx.TimeoutException:
        logger.warning("httpx 타임아웃: %s — 스킵", url)
        return {}
    except httpx.RequestError as e:
        logger.warning("httpx 요청 에러: %s - %s — 스킵", url, e)
        return {}
    except Exception:
        logger.exception("크롤 에러: %s", url)
        return {}


async def _fallback_browser_use(url: str, place_name: str, reason: str) -> dict:
    """browser-use로 폴백 크롤링한다. 보수적으로만 사용."""
    logger.info("browser-use 폴백 시작 (reason: %s): %s", reason, url)

    try:
        from browser.website_crawl_task import crawl_website
        result = await crawl_website(url, place_name)
        if result:
            result["source_url"] = url
            result["crawl_method"] = "browser-use"
            return result
    except Exception:
        logger.exception("browser-use 폴백 실패: %s", url)

    return {}
