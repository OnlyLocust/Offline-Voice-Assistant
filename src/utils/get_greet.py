from datetime import datetime


def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    elif 17 <= hour < 22:
        return "Good evening"
    else:
        return "Good Night"
    
    
    # if 5 <= hour < 12:
    #     greeting_hi = "सुप्रभात"
    # elif 12 <= hour < 17:
    #     greeting_hi = "नमस्ते"
    # elif 17 <= hour < 22:
    #     greeting_hi = "शुभ संध्या"
    # else:
    #     greeting_hi = "नमस्कार"
    