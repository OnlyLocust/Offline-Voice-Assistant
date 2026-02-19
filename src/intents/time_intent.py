from datetime import datetime
from core.tts import speak


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