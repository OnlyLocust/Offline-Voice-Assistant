import threading
import time
from datetime import datetime
from datetime import datetime, timedelta

alarm_time = None
alarm_running = False

def alarm_checker():
    global alarm_time, alarm_running

    while alarm_running:
        if alarm_time:
            now = datetime.now().strftime("%H:%M")
            if now == alarm_time:
                print("⏰ ALARM RINGING!")
                alarm_time = None
        time.sleep(1)

def start_alarm_thread():
    global alarm_running
    alarm_running = True
    thread = threading.Thread(target=alarm_checker, daemon=True)
    thread.start()

def set_alarm(t):
    global alarm_time
    alarm_time = t
    print(f"Alarm set for {t}")



# below code is to try how it will run

start_alarm_thread()

# set alarm 1 minute ahead for testing
now = datetime.now()
test_time = (now + timedelta(minutes=1)).strftime("%H:%M")

set_alarm(test_time)

# keep program alive
while True:
    time.sleep(1)