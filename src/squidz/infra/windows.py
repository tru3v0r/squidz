"""Windows-only input injection, active process and text field detection."""
import ctypes
import os
import subprocess
from ctypes import wintypes
import psutil

user32 = ctypes.windll.user32 if os.name == "nt" else None
VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "tab": 0x09, "win": 0x5B,
      "left": 0x25, "right": 0x27, "up": 0x26, "down": 0x28, "enter": 0x0D,
      "esc": 0x1B, "space": 0x20, "f": 0x46, "k": 0x4B,
      "volume_up": 0xAF, "volume_down": 0xAE, "media_play_pause": 0xB3}

# keybd_event is retained for simple desktop shortcuts; this process is not elevated.
def key_combo(keys: str) -> None:
    codes = []
    for token in keys.lower().replace(" ", "").split("+"):
        code = VK.get(token, ord(token.upper()) if len(token) == 1 and token.isalnum() else None)
        if code is None:
            raise ValueError(f"Unknown key: {token}")
        codes.append(code)
    for code in codes:
        user32.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        user32.keybd_event(code, 0, 2, 0)

def click(which: str) -> None:
    flags = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010), "middle": (0x0020, 0x0040)}
    down, up = flags[which]
    user32.mouse_event(down, 0, 0, 0, 0)
    user32.mouse_event(up, 0, 0, 0, 0)

def move(dx: float, dy: float) -> None:
    user32.mouse_event(0x0001, int(dx), int(dy), 0, 0)

def scroll(amount: int) -> None:
    user32.mouse_event(0x0800, 0, 0, int(amount * 120), 0)

def active_process() -> str:
    hwnd = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        return psutil.Process(pid.value).name().lower()
    except (psutil.Error, OSError):
        return ""

def is_text_field() -> bool:
    # UI Automation can identify focused editable controls in many native applications.
    # Browser contenteditable fields vary; detection is intentionally best effort.
    try:
        import comtypes.client
        uia = comtypes.client.CreateObject("UIAutomationClient.CUIAutomation")
        element = uia.GetFocusedElement()
        if element is None:
            return False
        control_type = element.CurrentControlType
        return control_type in (50004, 50020) and bool(element.CurrentIsKeyboardFocusable)
    except Exception:
        return False

def open_keyboard() -> None:
    try:
        subprocess.Popen(["osk.exe"], creationflags=0x08000000)
    except OSError:
        pass

def perform(action: str, keys: str = "") -> None:
    if action == "none": return
    if action.endswith("_click"):
        click(action.removesuffix("_click"))
        if action == "left_click" and is_text_field():
            open_keyboard()
    elif action == "win": key_combo("win")
    elif action == "volume_up": key_combo("volume_up")
    elif action == "volume_down": key_combo("volume_down")
    elif action == "previous": key_combo("ctrl+tab")
    elif action == "next": key_combo("tab")
    elif action == "tab_previous": key_combo("ctrl+shift+tab")
    elif action == "tab_next": key_combo("ctrl+tab")
    elif action == "play_pause": key_combo("k")
    elif action == "fullscreen": key_combo("f")
    elif action == "key_combo": key_combo(keys)
