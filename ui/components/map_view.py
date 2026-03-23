import json

import folium
import streamlit as st
import streamlit.components.v1 as components

CATEGORY_COLORS = {
    "restaurant": "red",
    "cafe": "orange",
    "attraction": "blue",
    "shopping": "purple",
    "bar": "darkred",
    "hotel": "darkblue",
}


def _extract_coords(place: dict) -> tuple[float, float] | None:
    """Extract lat/lng from place data."""
    # Try raw_gmaps_data first
    raw = place.get("raw_gmaps_data")
    if raw:
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                raw = None
        if isinstance(raw, dict):
            lat = raw.get("lat") or raw.get("latitude")
            lng = raw.get("lng") or raw.get("longitude")
            if lat is not None and lng is not None:
                return float(lat), float(lng)

    # Try direct lat/lng fields
    if place.get("lat") is not None and place.get("lng") is not None:
        return float(place["lat"]), float(place["lng"])

    return None


def render_map(places: list[dict], height: int = 400) -> None:
    """Render a folium map with markers for the given places."""
    if not places:
        st.info("표시할 장소가 없습니다.")
        return

    # Collect places with valid coordinates
    located = []
    for p in places:
        coords = _extract_coords(p)
        if coords:
            located.append((p, coords))

    if not located:
        st.info("좌표 정보가 있는 장소가 없어 지도를 표시할 수 없습니다.")
        return

    # Calculate center
    avg_lat = sum(c[0] for _, c in located) / len(located)
    avg_lng = sum(c[1] for _, c in located) / len(located)

    m = folium.Map(location=[avg_lat, avg_lng], zoom_start=13)

    for place, (lat, lng) in located:
        name = place.get("name", "")
        category = place.get("category", "")
        color = CATEGORY_COLORS.get(category, "gray")

        popup_html = f"<b>{name}</b>"
        if category:
            popup_html += f"<br><small>{category}</small>"
        if place.get("address"):
            popup_html += f"<br><small>{place['address']}</small>"

        folium.Marker(
            location=[lat, lng],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=name,
            icon=folium.Icon(color=color, icon="info-sign"),
        ).add_to(m)

    # Render via st.components.v1.html
    map_html = m._repr_html_()
    components.html(map_html, height=height)
