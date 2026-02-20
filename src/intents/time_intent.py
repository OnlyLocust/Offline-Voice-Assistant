from datetime import datetime
from core.tts import speak

_DAYS_HINDI = {
    "Monday":    "सोमवार",
    "Tuesday":   "मंगलवार",
    "Wednesday": "बुधवार",
    "Thursday":  "गुरुवार",
    "Friday":    "शुक्रवार",
    "Saturday":  "शनिवार",
    "Sunday":    "रविवार",
}

_MONTHS_HINDI = {
    "January":   "जनवरी",
    "February":  "फरवरी",
    "March":     "मार्च",
    "April":     "अप्रैल",
    "May":       "मई",
    "June":      "जून",
    "July":      "जुलाई",
    "August":    "अगस्त",
    "September": "सितंबर",
    "October":   "अक्टूबर",
    "November":  "नवंबर",
    "December":  "दिसंबर",
}


def check_time_query(text):
    """
    Detects 'समय' in Hindi text, prints and speaks the current time.
    """
    if "समय" in text:
        now = datetime.now()
        h   = now.strftime("%H")
        m   = now.strftime("%M")
        current_time = now.strftime("%H:%M:%S")
        print(f"⏰ वर्तमान समय है: {current_time}")
        speak(f"अभी समय है {h} बजकर {m} मिनट।")


def check_date_query(text):
    """
    Detects date/day keywords in Hindi text, prints and speaks today's date.
    Trigger keywords: तारीख, दिन, आज
    """
    keywords = ["तारीख", "दिन", "आज"]
    if not any(kw in text for kw in keywords):
        return

    now        = datetime.now()
    day_en      = now.strftime("%A")          # e.g. "Thursday"
    day_short   = now.strftime("%a")          # e.g. "Thu"
    month_short = now.strftime("%b")          # e.g. "Feb"
    date_num    = now.strftime("%d").lstrip("0") or "0"  # e.g. "20"
    month_en    = now.strftime("%B")          # e.g. "February"
    year        = now.strftime("%Y")          # e.g. "2026"

    day_hindi   = _DAYS_HINDI.get(day_en, day_en)
    month_hindi = _MONTHS_HINDI.get(month_en, month_en)

    print(f"📅 आज की तारीख: {day_short}, {date_num} {month_short} {year}")
    speak(f"आज {day_hindi} है, {date_num} {month_hindi} {year}।")