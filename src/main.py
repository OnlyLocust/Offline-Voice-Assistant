"""
main.py — Hindi Voice Assistant Entry Point
============================================
Starts the alarm thread, opens the microphone stream, and runs forever.
All logic lives in core/ and utils/ — this file stays under 60 lines.

Run:
    cd speech
    python src/main.py
"""

import sounddevice as sd
import time
from datetime import datetime

from utils.constants      import SAMPLE_RATE, WAKE_WORD, EXIT_WORD
from utils.alarm_thread   import start_alarm_thread
from core.recognizer      import callback


def _print_banner() -> None:
    w = 60
    print("=" * w)
    print("🤖  Hindi Voice Assistant — Full Offline Suite")
    print("=" * w)
    print(f"   Wake word  : '{WAKE_WORD}'")
    print(f"   Exit word  : '{EXIT_WORD}'")
    print(f"   Time       : {datetime.now().strftime('%H:%M:%S')}")
    print("-" * w)
    print("   Alarm   : 'kal saat baje jagana'  (PIN + voice)")
    print("   Timer   : 'das minute ka timer lagao'")
    print("             'timer band karo' / 'timer kitna baaki hai'")
    print("   Math    : 'paanch plus saat' / 'das minus teen'")
    print("             'chhe guna chaar' / 'bees bhaag paanch'")
    print("   Volume  : 'volume badhao' / 'volume kam karo'")
    print("             'mute karo' / 'unmute karo' / 'volume 50 percent'")
    print("   Notice  : 'das minute baad notice lagao'")
    print("             'notice cancel karo' / 'notice kitna baaki hai'")
    print("   Time    : 'samay batao'")
    print("=" * w)
    print()


if __name__ == "__main__":
    _print_banner()

    # Start background alarm checker thread
    start_alarm_thread()

    print("Listening for wake word...\n")

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=callback,
    ):
        while True:
            time.sleep(0.1)
