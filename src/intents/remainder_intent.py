import re
import json
from datetime import datetime, timedelta

HINDI_NUMBERS = {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5,
    "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "ग्यारह": 11, "बारह": 12
}

def word_to_number(text):
    for word, num in HINDI_NUMBERS.items():
        if word in text:
            return num
    return None

def detect_date(text):
    today = datetime.now().date()

    if "परसों" in text:
        return str(today + timedelta(days=2))
    elif "कल" in text:
        return str(today + timedelta(days=1))
    elif "आज" in text:
        return str(today)
    else:
        return str(today)

def detect_period(text):
    if "सुबह" in text:
        return "AM"
    if "शाम" in text or "रात" in text:
        return "PM"
    return None

def extract_time(text):
    # Case 1: 10:30
    match = re.search(r'(\d{1,2})[:.](\d{2})', text)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Case 2: 10 बजे
    match = re.search(r'(\d{1,2})', text)
    if match:
        return int(match.group(1)), 0

    # Case 3: "सात बजे"
    num = word_to_number(text)
    if num:
        return num, 0

    return None, None

def extract_alarm_intent(text):
    text = text.lower()

    result = {
        "action": None,
        "date": None,
        "time": None,
        "period": None
    }

    # ACTION
    if "अलार्म" in text or "जगाना" in text or "उठाना" in text:
        result["action"] = "set_alarm"
    else:
        return json.dumps(result, ensure_ascii=False)

    # DATE
    result["date"] = detect_date(text)

    # PERIOD
    result["period"] = detect_period(text)

    # TIME
    hour, minute = extract_time(text)
    if hour is not None:
        result["time"] = f"{hour:02d}:{minute:02d}"

    print(result)

    return json.dumps(result, ensure_ascii=False, indent=2)
