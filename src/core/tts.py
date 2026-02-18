"""
core/tts.py — Offline Text-to-Speech
======================================
Single speak() function that works on both Windows (PowerShell System.Speech)
and Linux / Raspberry Pi (espeak-ng).

Usage:
    from core.tts import speak
    speak("नमस्ते!")           # blocking by default
    speak("पृष्ठभूमि में", blocking=False)
"""

import subprocess
import platform


def speak(text: str, blocking: bool = True) -> None:
    """
    Speak `text` using the platform's offline TTS engine.

    Args:
        text:     Hindi (or any) text to speak.
        blocking: If True, wait for speech to finish before returning.
                  If False, fire-and-forget (non-blocking Popen).
    """
    print(f"🔊 {text}")
    try:
        if platform.system() == "Windows":
            safe = text.replace('"', '\\"')
            cmd  = [
                "powershell", "-Command",
                f'Add-Type -AssemblyName System.Speech; '
                f'(New-Object System.Speech.Synthesis.SpeechSynthesizer)'
                f'.Speak("{safe}")',
            ]
        else:
            # Raspberry Pi / Linux — requires: sudo apt install espeak-ng
            cmd = ["espeak-ng", "-v", "hi", text]

        if blocking:
            subprocess.run(cmd, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(cmd,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    except Exception:
        pass   # TTS failure must never crash the assistant
