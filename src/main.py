import sounddevice as sd
import json
from vosk import Model, KaldiRecognizer
import time
import subprocess
from datetime import datetime

from utils.constants import MODEL_PATH, SAMPLE_RATE, WAKE_WORD, EXIT_WORD
from utils.get_greet import get_greeting
from intents.time_intent import check_time_query
from intents.remainder_intent import extract_alarm_intent


model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, SAMPLE_RATE)

wake = False   # Wake word mode flag

def callback(indata, frames, time_info, status):
    global wake

    data = bytes(indata)

    if recognizer.AcceptWaveform(data):
        result = json.loads(recognizer.Result())
        text = result.get("text", "").strip()

        if not text:
            return

        # ===============================
        # 🔹 WAKE WORD MODE
        # ===============================
        if not wake:
            print("🛌 Sleeping | Heard:", text)
            if WAKE_WORD in text:
                    wake = True
                    # Time-based greeting in Hindi

                    greeting = get_greeting()                        

                    message = f"{greeting}! मैं आपकी कैसे मदद कर सकता हूँ?"
                    print("🔥 Wake word detected! Assistant is ACTIVE")
                    print(message + "\n")

                    # Try to speak the greeting on Windows using PowerShell/System.Speech
                    try:
                        safe_text = message.replace('"', '\\"')
                        subprocess.run([
                            "powershell",
                            "-Command",
                            f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\"{safe_text}\")"
                        ], check=False)
                    except Exception:
                        pass
            return

        # ===============================
        # 🔹 COMMAND MODE
        # ===============================
        print("👂 Command mode | Heard:", text)

        # EXIT command
        if EXIT_WORD in text:
            wake = False
            recognizer.Reset()
            print("🙏 धन्यवाद detected. Going back to sleep...\n")
            return

        # TIME command
        check_time_query(text)
        extract_alarm_intent(text)



print("🎧 Listening...")
with sd.RawInputStream(
    samplerate=SAMPLE_RATE,
    blocksize=8000,
    dtype="int16",
    channels=1,
    callback=callback
):
    while True:
        time.sleep(0.1)
