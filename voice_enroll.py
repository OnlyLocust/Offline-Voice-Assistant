"""
voice_enroll.py — One-time Voice Enrollment
=============================================
Run this ONCE before using the assistant to register your voice profile.
After enrollment, the assistant uses this profile for voice authentication
when setting alarms.

Usage:
    cd speech
    python voice_enroll.py
"""

import sys
import os

# Allow imports from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from utils.auth.voice_auth import enroll_voice
from utils.constants       import VOICE_PROFILE_PATH

if __name__ == "__main__":
    print("=" * 50)
    print("🎤  Voice Enrollment — Hindi Voice Assistant")
    print("=" * 50)
    print()
    print("यह स्क्रिप्ट आपकी आवाज़ को रजिस्टर करेगी।")
    print("(This script will register your voice profile.)")
    print()
    print("निर्देश / Instructions:")
    print("  • शांत जगह पर बैठें  (Sit in a quiet place)")
    print("  • माइक के पास बोलें  (Speak close to the mic)")
    print("  • कोई भी हिंदी वाक्य बोलें (Say any Hindi sentence)")
    print()
    input("तैयार हैं? Enter दबाएं... (Ready? Press Enter...)")
    print()

    success = enroll_voice(duration=4.0)

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
        print("   pip install python_speech_features")
