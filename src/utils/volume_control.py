"""
utils/volume_control.py — Offline System Volume Control
========================================================
Cross-platform volume control:
  • Windows  : pycaw (preferred) → fallback to nircmd → fallback to PowerShell
  • Linux/Pi : amixer (ALSA)

All offline. No internet. Non-blocking.

Public API:
    get_volume()          → int   (0-100, current volume %)
    set_volume(pct)       → int   (clamped 0-100, new volume %)
    increase_volume(step) → int   (new volume %)
    decrease_volume(step) → int   (new volume %)
    mute()                → None
    unmute()              → None
    is_muted()            → bool
"""

import platform
import subprocess

_OS = platform.system()   # "Windows" or "Linux"

# ─────────────────────────────────────────────────────────────────────────────
# Windows backend — pycaw (best) → PowerShell (fallback)
# ─────────────────────────────────────────────────────────────────────────────

if _OS == "Windows":
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        _PYCAW = True
        print("🔊 Volume backend: pycaw (Windows)")
    except Exception:
        _PYCAW = False
        print("🔊 Volume backend: PowerShell (Windows fallback)")

    def _get_vol_interface():
        """Lazy COM init — must be called from the thread that uses it."""
        devices   = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def _ps_run(script: str) -> str:
        """Run a PowerShell one-liner and return stdout."""
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True,
        )
        return result.stdout.strip()

    def get_volume() -> int:
        if _PYCAW:
            try:
                return round(_get_vol_interface().GetMasterVolumeLevelScalar() * 100)
            except Exception:
                pass
        # PowerShell fallback: use nircmd or WScript
        try:
            out = _ps_run(
                "(New-Object -ComObject WScript.Shell).SendKeys('');"
                "[System.Math]::Round((Get-Volume).Volume)"
            )
            return int(float(out))
        except Exception:
            return 50

    def set_volume(pct: int) -> int:
        pct = max(0, min(100, pct))
        if _PYCAW:
            try:
                _get_vol_interface().SetMasterVolumeLevelScalar(pct / 100.0, None)
                return pct
            except Exception:
                pass
        # nircmd fallback (0-65535 scale)
        try:
            subprocess.run(
                ["nircmd", "setsysvolume", str(int(pct / 100 * 65535))],
                check=False, capture_output=True,
            )
        except FileNotFoundError:
            # PowerShell WScript key-press fallback (approximate)
            _ps_run(
                f"$o=New-Object -ComObject WScript.Shell;"
                f"for($i=0;$i-lt 50;$i++){{$o.SendKeys([char]174)}};"
                f"$s=[math]::Round({pct}/2);"
                f"for($i=0;$i-lt $s;$i++){{$o.SendKeys([char]175)}}"
            )
        return pct

    def mute() -> None:
        if _PYCAW:
            try:
                _get_vol_interface().SetMute(1, None)
                return
            except Exception:
                pass
        subprocess.run(["nircmd", "mutesysvolume", "1"],
                       check=False, capture_output=True)

    def unmute() -> None:
        if _PYCAW:
            try:
                _get_vol_interface().SetMute(0, None)
                return
            except Exception:
                pass
        subprocess.run(["nircmd", "mutesysvolume", "0"],
                       check=False, capture_output=True)

    def is_muted() -> bool:
        if _PYCAW:
            try:
                return bool(_get_vol_interface().GetMute())
            except Exception:
                pass
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Linux / Raspberry Pi backend — amixer (ALSA)
# ─────────────────────────────────────────────────────────────────────────────

else:
    import re as _re

    _AMIXER_CONTROL = "Master"   # change to "PCM" if Master doesn't work on Pi

    def _amixer(args: list[str]) -> str:
        result = subprocess.run(
            ["amixer", "sset", _AMIXER_CONTROL] + args,
            capture_output=True, text=True,
        )
        return result.stdout

    def get_volume() -> int:
        out = subprocess.run(
            ["amixer", "sget", _AMIXER_CONTROL],
            capture_output=True, text=True,
        ).stdout
        m = _re.search(r'\[(\d+)%\]', out)
        return int(m.group(1)) if m else 50

    def set_volume(pct: int) -> int:
        pct = max(0, min(100, pct))
        _amixer([f"{pct}%"])
        return pct

    def mute() -> None:
        _amixer(["mute"])

    def unmute() -> None:
        _amixer(["unmute"])

    def is_muted() -> bool:
        out = subprocess.run(
            ["amixer", "sget", _AMIXER_CONTROL],
            capture_output=True, text=True,
        ).stdout
        return "[off]" in out


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers (work on both platforms)
# ─────────────────────────────────────────────────────────────────────────────

def increase_volume(step: int = 10) -> int:
    """Increase volume by `step` percent. Returns new volume."""
    current = get_volume()
    return set_volume(current + step)


def decrease_volume(step: int = 10) -> int:
    """Decrease volume by `step` percent. Returns new volume."""
    current = get_volume()
    return set_volume(current - step)
