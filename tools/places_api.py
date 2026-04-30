"""Google Maps Places API로 장소 기본 정보를 수집한다."""

import logging

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

FIND_PLACE_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


async def search_place(place_name: str, city: str) -> dict:
    """Places API로 장소의 기본 정보를 조회합니다.

    영업시간, 평점, 주소, 전화번호, 가격대 등 정형 데이터를 수집합니다.

    Args:
        place_name: 장소 이름 (예: "Musée d'Orsay")
        city: 도시 이름 (예: "Paris")

    Returns:
        장소 기본 정보 dict. 실패 시 에러 메시지 포함.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Step 1: Find Place
            find_resp = await client.get(
                FIND_PLACE_URL,
                params={
                    "input": f"{place_name} {city}",
                    "inputtype": "textquery",
                    "fields": "place_id,name,formatted_address",
                    "key": settings.google_maps_api_key,
                },
            )
            find_data = find_resp.json()

            if find_data.get("status") != "OK" or not find_data.get("candidates"):
                logger.warning("Places API 검색 실패: %s (%s) - %s", place_name, city, find_data.get("status"))
                return {"error": f"Place not found: {find_data.get('status')}", "data": {}}

            place_id = find_data["candidates"][0]["place_id"]

            # Step 2: Place Details
            details_resp = await client.get(
                PLACE_DETAILS_URL,
                params={
                    "place_id": place_id,
                    "fields": "name,formatted_address,formatted_phone_number,website,url,rating,user_ratings_total,price_level,opening_hours,types,business_status,reservable,geometry",
                    "key": settings.google_maps_api_key,
                    "language": "en",
                },
            )
            details_data = details_resp.json()

            if details_data.get("status") != "OK":
                logger.warning("Places API 상세 조회 실패: %s - %s", place_id, details_data.get("status"))
                return {"error": f"Details failed: {details_data.get('status')}", "data": {}}

            result = details_data["result"]

            # 영업시간 파싱
            operating_hours = {}
            if "opening_hours" in result:
                for period_text in result["opening_hours"].get("weekday_text", []):
                    parts = period_text.split(": ", 1)
                    if len(parts) == 2:
                        operating_hours[parts[0].lower()] = parts[1]

            # 카테고리 매핑
            types = result.get("types", [])
            category = _map_category(types)

            # 가격대 매핑
            price_map = {0: "free", 1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}
            price_level = price_map.get(result.get("price_level"))

            # 좌표 추출
            lat = lng = None
            geom = result.get("geometry") or {}
            loc = geom.get("location") or {}
            if loc.get("lat") is not None and loc.get("lng") is not None:
                lat = float(loc["lat"])
                lng = float(loc["lng"])

            place_info = {
                "name": result.get("name"),
                "address": result.get("formatted_address"),
                "google_maps_url": result.get("url"),
                "phone": result.get("formatted_phone_number"),
                "website": result.get("website"),
                "rating": result.get("rating"),
                "review_count": result.get("user_ratings_total"),
                "price_level": price_level,
                "category": category,
                "operating_hours": operating_hours,
                "reservable": result.get("reservable"),
                "business_status": result.get("business_status"),
                "lat": lat,
                "lng": lng,
            }

            logger.info("Places API 조회 성공: %s (%s)", place_name, city)
            return {"error": None, "data": place_info}

    except httpx.TimeoutException:
        logger.error("Places API 타임아웃: %s (%s)", place_name, city)
        return {"error": "timeout", "data": {}}
    except Exception as e:
        logger.exception("Places API 에러: %s (%s)", place_name, city)
        return {"error": str(e), "data": {}}


def _map_category(types: list[str]) -> str:
    """Google Places 타입을 간단한 카테고리로 매핑."""
    category_map = {
        "restaurant": "restaurant",
        "cafe": "cafe",
        "museum": "museum",
        "art_gallery": "museum",
        "park": "park",
        "shopping_mall": "shopping",
        "store": "shopping",
        "tourist_attraction": "attraction",
        "church": "landmark",
        "landmark": "landmark",
        "night_club": "entertainment",
        "bar": "entertainment",
        "amusement_park": "entertainment",
        "market": "market",
    }
    for t in types:
        if t in category_map:
            return category_map[t]
    return "attraction"
