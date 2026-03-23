import re


def extract_reservation_info(text: str) -> dict:
    """Extract reservation-related information from crawled text."""
    if not text:
        return {"status": "unknown", "lead_time": None, "booking_method": None}

    text_lower = text.lower()

    # Determine reservation status
    required_patterns = [
        r"reservation\s+(is\s+)?required",
        r"reservations?\s+only",
        r"booking\s+(is\s+)?required",
        r"must\s+(be\s+)?book",
        r"예약\s*필수",
        r"예약이?\s*필요",
        r"advance\s+booking\s+required",
    ]
    recommended_patterns = [
        r"reservation\s+(is\s+)?recommended",
        r"booking\s+(is\s+)?recommended",
        r"reservations?\s+suggested",
        r"recommend\s+(making\s+)?(a\s+)?reservation",
        r"예약\s*추천",
        r"예약\s*권장",
        r"best\s+to\s+(make\s+)?(a\s+)?reservation",
    ]
    not_needed_patterns = [
        r"no\s+reservation\s+(needed|required|necessary)",
        r"walk[\s-]?ins?\s+(welcome|accepted|only)",
        r"first[\s-]come",
        r"예약\s*불필요",
        r"예약\s*없이",
        r"no\s+booking\s+(needed|required)",
    ]

    status = "unknown"
    if any(re.search(p, text_lower) for p in required_patterns):
        status = "required"
    elif any(re.search(p, text_lower) for p in recommended_patterns):
        status = "recommended"
    elif any(re.search(p, text_lower) for p in not_needed_patterns):
        status = "not_needed"

    # Extract lead time
    lead_time = None
    lead_patterns = [
        r"(\d+)\s*(days?|weeks?|months?)\s*(in\s+advance|before|ahead|prior)",
        r"(at\s+least\s+)?(\d+)\s*(days?|weeks?|months?)\s*(in\s+advance|before|ahead|prior)",
        r"book\s+(\d+)\s*(days?|weeks?|months?)\s*(in\s+advance|before|ahead)",
    ]
    for pattern in lead_patterns:
        match = re.search(pattern, text_lower)
        if match:
            groups = match.groups()
            # Find the numeric value and unit
            for i, g in enumerate(groups):
                if g and g.isdigit():
                    num = g
                    unit = groups[i + 1] if i + 1 < len(groups) else "days"
                    lead_time = f"{num} {unit}"
                    break
            if lead_time:
                break

    # Extract booking method
    booking_method = None
    method_patterns = [
        (r"book\s+(via|through|on|at)\s+([\w\s.]+\.(?:com|co\.kr|net|org))", "website"),
        (r"(call|phone|tel|전화)\s*[:\s]*([\d\-+()\s]{7,})", "phone"),
        (r"(online|website|web)\s*(booking|reservation)", "online"),
        (r"(email|이메일)\s*[:\s]*([\w.+-]+@[\w.-]+)", "email"),
    ]
    for pattern, method_type in method_patterns:
        match = re.search(pattern, text_lower)
        if match:
            booking_method = method_type
            break

    return {
        "status": status,
        "lead_time": lead_time,
        "booking_method": booking_method,
    }


def extract_operating_hours(text: str) -> dict:
    """Extract operating hours, break time, and last order from text."""
    if not text:
        return {"hours": {}, "break_time": None, "last_order": None}

    day_map = {
        "mon": "mon", "monday": "mon",
        "tue": "tue", "tuesday": "tue",
        "wed": "wed", "wednesday": "wed",
        "thu": "thu", "thursday": "thu",
        "fri": "fri", "friday": "fri",
        "sat": "sat", "saturday": "sat",
        "sun": "sun", "sunday": "sun",
    }
    day_range_map = {
        "weekdays": ["mon", "tue", "wed", "thu", "fri"],
        "weekends": ["sat", "sun"],
        "daily": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "everyday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "every day": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    }

    hours = {}
    time_pattern = r"(\d{1,2}:\d{2})\s*[-–~]\s*(\d{1,2}:\d{2})"

    # Match "Mon-Fri: 09:00-22:00" or "Monday to Friday 09:00-22:00"
    range_pattern = r"(mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\s*[-–~to]+\s*(mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\s*[:\s]*" + time_pattern
    for match in re.finditer(range_pattern, text, re.IGNORECASE):
        start_day = day_map.get(match.group(1).lower()[:3])
        end_day = day_map.get(match.group(2).lower()[:3])
        time_range = f"{match.group(3)}-{match.group(4)}"
        if start_day and end_day:
            all_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            si, ei = all_days.index(start_day), all_days.index(end_day)
            for i in range(si, ei + 1):
                hours[all_days[i]] = time_range

    # Match "Weekdays: 09:00-22:00"
    for key, days in day_range_map.items():
        pattern = re.compile(key + r"\s*[:\s]*" + time_pattern, re.IGNORECASE)
        match = pattern.search(text)
        if match:
            time_range = f"{match.group(1)}-{match.group(2)}"
            for d in days:
                hours[d] = time_range

    # Match individual day: "Monday: 09:00-22:00"
    single_pattern = r"(mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\s*[:\s]*" + time_pattern
    for match in re.finditer(single_pattern, text, re.IGNORECASE):
        day = day_map.get(match.group(1).lower()[:3])
        if day:
            hours[day] = f"{match.group(2)}-{match.group(3)}"

    # Extract break time
    break_time = None
    break_match = re.search(r"break\s*(?:time)?\s*[:\s]*" + time_pattern, text, re.IGNORECASE)
    if not break_match:
        break_match = re.search(r"브레이크\s*(?:타임)?\s*[:\s]*" + time_pattern, text, re.IGNORECASE)
    if break_match:
        break_time = f"{break_match.group(1)}-{break_match.group(2)}"

    # Extract last order
    last_order = None
    lo_match = re.search(r"last\s*order\s*[:\s]*(\d{1,2}:\d{2})", text, re.IGNORECASE)
    if not lo_match:
        lo_match = re.search(r"라스트\s*오더\s*[:\s]*(\d{1,2}:\d{2})", text, re.IGNORECASE)
    if lo_match:
        last_order = lo_match.group(1)

    return {"hours": hours, "break_time": break_time, "last_order": last_order}


def extract_restrictions(text: str) -> dict:
    """Extract restriction information from text."""
    if not text:
        return {"age": None, "group_size": None, "dress_code": None, "payment": None}

    text_lower = text.lower()

    # Age restrictions
    age = None
    age_patterns = [
        r"((?:minimum|min)\s+age\s*[:\s]*\d+)",
        r"(\d+\+?\s*(?:years?\s+old|and\s+over|and\s+above))",
        r"(no\s+children(?:\s+under\s+\d+)?)",
        r"(adults?\s+only)",
        r"(all\s+ages?\s+welcome)",
        r"(kids?\s+friendly|family\s+friendly|child(?:ren)?\s+welcome)",
    ]
    for pattern in age_patterns:
        match = re.search(pattern, text_lower)
        if match:
            age = match.group(1).strip()
            break

    # Group size
    group_size = None
    group_patterns = [
        r"(max(?:imum)?\s*(?:group\s*(?:size)?|party\s*(?:size)?|guests?)?\s*[:\s]*\d+)",
        r"(groups?\s+(?:of\s+)?up\s+to\s+\d+)",
        r"(no\s+(?:groups?\s+)?(?:larger|more)\s+than\s+\d+)",
        r"(\d+\s*(?:people|persons?|guests?)\s*max(?:imum)?)",
    ]
    for pattern in group_patterns:
        match = re.search(pattern, text_lower)
        if match:
            group_size = match.group(1).strip()
            break

    # Dress code
    dress_code = None
    dress_patterns = [
        r"dress\s*code\s*[:\s]*([\w\s,]+?)(?:\.|$|\n)",
        r"(smart\s+casual|business\s+casual|formal\s+(?:attire|dress)|casual\s+(?:attire|dress))",
        r"(no\s+(?:shorts|sandals|flip[\s-]?flops|sneakers|jeans))",
    ]
    for pattern in dress_patterns:
        match = re.search(pattern, text_lower)
        if match:
            dress_code = match.group(1).strip()
            break

    # Payment info
    payment = None
    payment_patterns = [
        r"(cash\s+only)",
        r"(credit\s+cards?\s+(?:accepted|welcome))",
        r"(cards?\s+(?:accepted|welcome))",
        r"(no\s+(?:credit\s+)?cards?)",
        r"(현금\s*만|카드\s*(?:가능|불가))",
    ]
    for pattern in payment_patterns:
        match = re.search(pattern, text_lower)
        if match:
            payment = match.group(1).strip()
            break

    return {
        "age": age,
        "group_size": group_size,
        "dress_code": dress_code,
        "payment": payment,
    }
