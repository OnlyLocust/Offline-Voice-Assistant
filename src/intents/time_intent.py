from datetime import datetime

def check_time_query(text):
    """
    Detects 'समय' in Hindi text and prints current time
    """
    if "समय" in text:
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        print(f"⏰ वर्तमान समय है: {current_time}")