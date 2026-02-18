from datetime import datetime


def get_greeting() -> str:
    """Return a time-appropriate Hindi greeting."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "सुप्रभात"       # Good morning
    elif 12 <= hour < 17:
        return "नमस्ते"         # Good afternoon
    elif 17 <= hour < 22:
        return "शुभ संध्या"     # Good evening
    else:
        return "शुभ रात्रि"     # Good night