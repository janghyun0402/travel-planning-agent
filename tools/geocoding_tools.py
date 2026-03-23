import httpx

from config.settings import settings

DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


async def calculate_distance(origin: str, destination: str) -> dict:
    """Calculate distance and travel time between two places using Google Maps Distance Matrix API.

    Args:
        origin: Starting location (place name or address).
        destination: Ending location (place name or address).

    Returns:
        Dict with distance_km, duration_minutes, and method.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try walking first
            resp = await client.get(
                DISTANCE_MATRIX_URL,
                params={
                    "origins": origin,
                    "destinations": destination,
                    "mode": "walking",
                    "key": settings.google_maps_api_key,
                    "language": "en",
                },
            )
            data = resp.json()

            if data.get("status") == "OK":
                element = data["rows"][0]["elements"][0]
                if element.get("status") == "OK":
                    distance_m = element["distance"]["value"]
                    duration_s = element["duration"]["value"]
                    distance_km = round(distance_m / 1000, 2)
                    duration_min = round(duration_s / 60)

                    # If walking takes > 30 min, also check transit
                    if duration_min > 30:
                        transit_resp = await client.get(
                            DISTANCE_MATRIX_URL,
                            params={
                                "origins": origin,
                                "destinations": destination,
                                "mode": "transit",
                                "key": settings.google_maps_api_key,
                                "language": "en",
                            },
                        )
                        transit_data = transit_resp.json()
                        if transit_data.get("status") == "OK":
                            t_element = transit_data["rows"][0]["elements"][0]
                            if t_element.get("status") == "OK":
                                t_duration_s = t_element["duration"]["value"]
                                t_duration_min = round(t_duration_s / 60)
                                if t_duration_min < duration_min:
                                    return {
                                        "distance_km": distance_km,
                                        "duration_minutes": t_duration_min,
                                        "method": "transit",
                                    }

                    return {
                        "distance_km": distance_km,
                        "duration_minutes": duration_min,
                        "method": "walk",
                    }

        return {
            "distance_km": 0,
            "duration_minutes": 0,
            "method": "unknown",
            "error": "Could not calculate distance",
        }

    except Exception as e:
        return {
            "distance_km": 0,
            "duration_minutes": 0,
            "method": "unknown",
            "error": str(e),
        }
