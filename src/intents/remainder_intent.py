import re

def parse_reminder(text):
    text = text.strip()

    # 1. check trigger words (PURE HINDI)
    if "याद दिलाओ" not in text and "याद दिलाना" not in text:
        return None

    # 2. extract time (PURE HINDI)
    time_patterns = [
        r"(आज|कल|परसों)",
        r"(सुबह|शाम|रात|दोपहर)",
        r"(\d{1,2}\s*बजे)"
    ]

    time_found = []
    for pattern in time_patterns:
        matches = re.findall(pattern, text)
        time_found.extend(matches)

    time_str = " ".join(time_found) if time_found else "समय नहीं मिला"

    # 3. extract task (before 'याद दिलाना / याद दिलाओ')
    task_part = re.split(r"याद दिलाओ|याद दिलाना", text)[0]

    # remove time words from task
    task_part = re.sub(
        r"(आज|कल|परसों|सुबह|शाम|रात|दोपहर|\d{1,2}\s*बजे)",
        "",
        task_part
    )

    task = task_part.strip()

    print({"time": time_str, "task": task})
    return {
        "time": time_str,
        "task": task
    }
