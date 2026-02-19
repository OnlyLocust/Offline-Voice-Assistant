"""
voice_enroll.py — One-time Voice Enrollment
=============================================
Run this ONCE before using the assistant to register your voice profile.
The script records you saying your PIN phrase THREE times and saves the
averaged MFCC profile so the assistant can recognise your voice reliably.

IMPORTANT: Say the SAME phrase you will say when setting an alarm
(your PIN words, e.g. "एक दो तीन चार") during all three passes.
This ensures the enrollment and verification audio are acoustically
as close as possible, giving the highest similarity score.

Usage:
    cd Offline-Voice-Assistant
    python voice_enroll.py
"""

import sys
import os

# Allow imports from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from utils.auth.voice_auth import enroll_voice
from utils.constants       import VOICE_PROFILE_PATH

if __name__ == "__main__":
    print("=" * 55)
    print("🎤  Voice Enrollment — Hindi Voice Assistant")
    print("=" * 55)
    print()
    print("यह स्क्रिप्ट आपकी आवाज़ को 3 बार रिकॉर्ड करेगी।")
    print("(This script records your voice 3 times and averages them.)")
    print()
    print("⚠️  महत्वपूर्ण — IMPORTANT:")
    print("   हर बार अपना PIN बोलें (the words you use as your alarm PIN)")
    print("   For example, if your PIN is 1234, say: 'एक दो तीन चार'")
    print("   Use the EXACT same words every time and when setting alarms.")
    print()
    print("निर्देश / Instructions:")
    print("  • शांत जगह पर बैठें     (Sit in a quiet place)")
    print("  • माइक के पास बोलें     (Speak close to the mic)")
    print("  • हर बार अपना PIN बोलें  (Say your PIN phrase each time)")
    print()
    input("तैयार हैं? Enter दबाएं... (Ready? Press Enter...)")
    print()

    success = enroll_voice(duration=4.0, passes=3)

    if success:
        print()
        print("✅ नामांकन पूर्ण! (Enrollment complete!)")
        print(f"   Profile: {VOICE_PROFILE_PATH}.npy")
        print()
        print("अब आप main.py चला सकते हैं।")
        print("(You can now run:  python src/main.py)")
    else:
        print()
        print("❌ नामांकन विफल। (Enrollment failed.)")
        print("   Make sure python_speech_features is installed:")
        print("   pip install python_speech_features")
