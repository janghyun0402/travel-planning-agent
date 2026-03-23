"""특정 URL에 직접 접속하여 여행 관련 실용 정보를 추출한다."""

import json
import logging

from browser_use import Agent

from browser.config import (
    MAX_RETRIES,
    delay_between_requests,
    get_browser,
    get_llm,
)

logger = logging.getLogger(__name__)

WEBSITE_CRAWL_PROMPT = """
다음 URL에 접속하여 "{place_name}"에 대한 실용적인 방문 정보를 추출해주세요.

URL: {url}

페이지를 읽고 다음 정보를 찾아주세요:
- reservation_status: 예약이 필요한지 (required / recommended / not_needed / unknown)
- reservation_lead_time: 예약 권장 시점 (예: "2 days before", "1 week")
- booking_url: 예약 페이지 URL (있는 경우)
- wait_time_info: 대기 시간 관련 정보
- tips: 방문 팁 (배열)
- restrictions: 제한사항 (드레스코드, 연령, 인원, 결제 방법 등)
- review_snippets: 유용한 리뷰/정보 발췌 (배열)
- break_time: 브레이크타임 정보 (있는 경우)
- last_order: 라스트오더 시간 (있는 경우)

결과를 다음 JSON 형식으로 반환해주세요:
```json
{{
  "reservation_status": "required",
  "reservation_lead_time": "2 days",
  "booking_url": null,
  "wait_time_info": null,
  "tips": [],
  "restrictions": {{"dress_code": null, "age": null, "group_size": null, "payment": null}},
  "review_snippets": [],
  "break_time": null,
  "last_order": null,
  "source_url": "{url}"
}}
```

정보를 찾을 수 없는 필드는 null로 설정하세요.
JSON 블록만 출력하세요.
"""


def _parse_result(result: str) -> dict:
    """Agent 결과 텍스트에서 JSON을 파싱한다."""
    text = result.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1]
        text = text.split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1]
        text = text.split("```", 1)[0]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        logger.warning("웹사이트 크롤 결과 JSON 파싱 실패: %s", text[:200])
        return {}


async def crawl_website(url: str, place_name: str) -> dict:
    """특정 URL에 접속하여 장소의 실용 정보를 추출한다.

    Args:
        url: 접속할 웹페이지 URL
        place_name: 장소 이름 (추출 컨텍스트 제공용)

    Returns:
        예약 정보, 팁, 제한사항 등이 담긴 dict. 실패 시 빈 dict.
    """
    task = WEBSITE_CRAWL_PROMPT.format(url=url, place_name=place_name)

    for attempt in range(1, MAX_RETRIES + 1):
        browser = get_browser()
        try:
            agent = Agent(
                task=task,
                llm=get_llm(),
                browser=browser,
                max_actions_per_step=5,
            )
            result = await agent.run()

            final_result = result.final_result()
            if final_result:
                parsed = _parse_result(final_result)
                if parsed:
                    # JSON 직렬화가 필요한 필드 변환
                    for field in ("tips", "review_snippets"):
                        if isinstance(parsed.get(field), list):
                            parsed[field] = json.dumps(parsed[field], ensure_ascii=False)
                    if isinstance(parsed.get("restrictions"), dict):
                        parsed["restrictions"] = json.dumps(parsed["restrictions"], ensure_ascii=False)
                    logger.info("웹사이트 크롤 성공: %s (%s)", place_name, url)
                    return parsed

            logger.warning("웹사이트 크롤 시도 %d/%d 결과 없음: %s", attempt, MAX_RETRIES, url)
        except Exception:
            logger.exception("웹사이트 크롤 시도 %d/%d 실패: %s", attempt, MAX_RETRIES, url)
        finally:
            await browser.stop()

        if attempt < MAX_RETRIES:
            await delay_between_requests()

    logger.error("웹사이트 크롤 최종 실패: %s (%s)", place_name, url)
    return {}
