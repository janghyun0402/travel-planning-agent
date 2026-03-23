import streamlit as st

CATEGORY_ICONS = {
    "restaurant": "🍽️",
    "cafe": "☕",
    "attraction": "🏛️",
    "shopping": "🛍️",
    "bar": "🍸",
    "hotel": "🏨",
}

RESERVATION_BADGE = {
    "required": ("예약 필수", "#e74c3c", "#fff"),
    "recommended": ("예약 권장", "#f39c12", "#fff"),
    "not_needed": ("워크인 가능", "#27ae60", "#fff"),
    "unknown": ("예약 정보 없음", "#95a5a6", "#fff"),
}


def _badge_html(text: str, bg: str, fg: str) -> str:
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:10px;font-size:0.8em;font-weight:600;">{text}</span>'
    )


def _stars(score: float, max_stars: int = 5) -> str:
    """Convert 0-1 confidence score to star display."""
    filled = round(score * max_stars)
    return "★" * filled + "☆" * (max_stars - filled)


def render_place_card(place: dict, key_prefix: str = "") -> None:
    """Render a place card component in Streamlit."""
    name = place.get("name", "알 수 없는 장소")
    category = place.get("category", "")
    icon = CATEGORY_ICONS.get(category, "📍")
    reservation_status = place.get("reservation_status", "unknown")
    badge_text, badge_bg, badge_fg = RESERVATION_BADGE.get(
        reservation_status, RESERVATION_BADGE["unknown"]
    )

    # Header: icon + name + reservation badge
    st.markdown(
        f"### {icon} {name} {_badge_html(badge_text, badge_bg, badge_fg)}",
        unsafe_allow_html=True,
    )

    # Address
    if place.get("address"):
        st.caption(f"📍 {place['address']}")

    # Operating info row
    info_parts = []
    if place.get("operating_hours"):
        hours = place["operating_hours"]
        if isinstance(hours, dict):
            # Show today or first available
            display = next(iter(hours.values()), None) if hours else None
            if display:
                info_parts.append(f"🕐 {display}")
        elif isinstance(hours, str):
            info_parts.append(f"🕐 {hours}")
    if place.get("break_time"):
        info_parts.append(f"☕ 브레이크타임: {place['break_time']}")
    if place.get("last_order"):
        info_parts.append(f"⏰ 라스트오더: {place['last_order']}")

    if info_parts:
        st.markdown(" · ".join(info_parts))

    # Restrictions
    restrictions = place.get("restrictions")
    if restrictions and isinstance(restrictions, dict):
        restriction_items = []
        if restrictions.get("age"):
            restriction_items.append(f"👤 연령: {restrictions['age']}")
        if restrictions.get("dress_code"):
            restriction_items.append(f"👔 드레스코드: {restrictions['dress_code']}")
        if restrictions.get("group_size"):
            restriction_items.append(f"👥 인원: {restrictions['group_size']}")
        for k, v in restrictions.items():
            if k not in ("age", "dress_code", "group_size"):
                restriction_items.append(f"⚠️ {k}: {v}")
        if restriction_items:
            st.markdown(" · ".join(restriction_items))

    # Confidence score + rating
    col1, col2 = st.columns(2)
    with col1:
        confidence = place.get("confidence_score", 0.5)
        st.markdown(f"**신뢰도:** {_stars(confidence)} ({confidence:.1%})")
    with col2:
        rating = place.get("rating")
        review_count = place.get("review_count")
        if rating is not None:
            rating_text = f"**평점:** {'⭐' * round(rating)} {rating:.1f}"
            if review_count:
                rating_text += f" ({review_count:,}개 리뷰)"
            st.markdown(rating_text)

    # Price level
    if place.get("price_level"):
        st.markdown(f"**가격대:** {place['price_level']}")

    # Action buttons
    booking = place.get("booking_method") or {}
    booking_url = booking.get("url") if isinstance(booking, dict) else None
    phone = booking.get("phone") if isinstance(booking, dict) else None
    maps_url = place.get("google_maps_url")

    has_actions = booking_url or phone or maps_url
    if has_actions:
        btn_cols = st.columns(3)
        with btn_cols[0]:
            if booking_url:
                st.link_button("📞 예약", booking_url, use_container_width=True)
        with btn_cols[1]:
            if phone:
                st.link_button("📱 전화", f"tel:{phone}", use_container_width=True)
        with btn_cols[2]:
            if maps_url:
                st.link_button("🗺️ 지도", maps_url, use_container_width=True)

    # Evidence section
    snippets = place.get("review_snippets") or []
    urls = place.get("evidence_urls") or []
    if snippets or urls:
        with st.expander("📎 근거 및 리뷰", expanded=False):
            if snippets:
                for snippet in snippets:
                    st.markdown(f"> {snippet}")
            if urls:
                st.markdown("**출처:**")
                for url in urls:
                    st.markdown(f"- [{url}]({url})")
