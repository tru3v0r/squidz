"""Windows-only input injection and interaction-target detection."""
import ctypes
import math
import os
import time
from ctypes import wintypes
from pathlib import Path
import psutil

user32 = ctypes.windll.user32 if os.name == "nt" else None
VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "tab": 0x09, "win": 0x5B,
      "left": 0x25, "right": 0x27, "up": 0x26, "down": 0x28, "enter": 0x0D,
      "esc": 0x1B, "space": 0x20, "f": 0x46, "c": 0x43, "k": 0x4B,
      "volume_up": 0xAF, "volume_down": 0xAE, "media_play_pause": 0xB3}
MOUSE_FLAGS = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010),
               "middle": (0x0020, 0x0040)}
MAGNET_RADIUS = 110
MAGNET_SNAP_RADIUS = 40
_desktop_icon_cache: tuple[float, list[tuple[int, int]]] = (0.0, [])

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

def mouse_button_down(which: str) -> None:
    down, _ = MOUSE_FLAGS[which]
    user32.mouse_event(down, 0, 0, 0, 0)


def mouse_button_up(which: str) -> None:
    _, up = MOUSE_FLAGS[which]
    user32.mouse_event(up, 0, 0, 0, 0)


def click(which: str) -> None:
    mouse_button_down(which)
    mouse_button_up(which)


def _magnetized_delta(
    dx: float,
    dy: float,
    cursor: tuple[int, int],
    targets: list[tuple[int, int]],
    strength: float,
) -> tuple[float, float]:
    strength = max(0.0, min(100.0, strength)) / 100
    if not strength or not targets:
        return dx, dy
    x, y = cursor
    target_x, target_y = min(targets, key=lambda target: math.dist(cursor, target))
    distance = math.dist(cursor, (target_x, target_y))
    if distance >= MAGNET_RADIUS:
        return dx, dy
    proximity = 1 - distance / MAGNET_RADIUS
    pull = 0.035 * strength * proximity
    return dx + (target_x - x) * pull, dy + (target_y - y) * pull


def _magnet_snap_target(
    dx: float,
    dy: float,
    cursor: tuple[int, int],
    targets: list[tuple[int, int]],
    strength: float,
) -> tuple[int, int] | None:
    if strength <= 0 or not targets:
        return None

    start_x, start_y = cursor
    end_x, end_y = start_x + dx, start_y + dy
    segment_x, segment_y = end_x - start_x, end_y - start_y
    segment_length_squared = segment_x * segment_x + segment_y * segment_y
    snap_radius = MAGNET_SNAP_RADIUS * min(100.0, strength) / 100
    closest = None
    closest_distance = snap_radius

    for target_x, target_y in targets:
        if segment_length_squared:
            progress = ((target_x - start_x) * segment_x
                        + (target_y - start_y) * segment_y) / segment_length_squared
            progress = max(0.0, min(1.0, progress))
            nearest_x = start_x + progress * segment_x
            nearest_y = start_y + progress * segment_y
        else:
            nearest_x, nearest_y = start_x, start_y
        distance = math.hypot(target_x - nearest_x, target_y - nearest_y)
        if distance <= closest_distance:
            closest = (target_x, target_y)
            closest_distance = distance
    return closest


def _find_desktop_list_view() -> int | None:
    find_window = user32.FindWindowW
    find_window.restype = wintypes.HWND
    find_window.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    find_child = user32.FindWindowExW
    find_child.restype = wintypes.HWND
    find_child.argtypes = (wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR)

    def list_view(parent):
        shell_view = find_child(parent, None, "SHELLDLL_DefView", None)
        if shell_view:
            return find_child(shell_view, None, "SysListView32", None)
        return None

    desktop = find_window("Progman", None)
    found = list_view(desktop) if desktop else None
    if found:
        return found

    result = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL

    def inspect_window(hwnd, _):
        found_list = list_view(hwnd)
        if found_list:
            result.append(found_list)
            return False
        return True

    user32.EnumWindows(callback_type(inspect_window), 0)
    return result[0] if result else None


def _desktop_icon_centers() -> list[tuple[int, int]]:
    global _desktop_icon_cache
    cached_at, cached_centers = _desktop_icon_cache
    if time.monotonic() - cached_at < 1:
        return cached_centers

    list_view = _find_desktop_list_view()
    if not list_view:
        _desktop_icon_cache = (time.monotonic(), [])
        return []

    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowThreadProcessId(list_view, ctypes.byref(process_id))
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.VirtualAllocEx.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                        wintypes.DWORD, wintypes.DWORD)
    kernel32.VirtualAllocEx.restype = ctypes.c_void_p
    kernel32.VirtualFreeEx.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                       wintypes.DWORD)
    kernel32.ReadProcessMemory.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
    kernel32.WriteProcessMemory.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    process = kernel32.OpenProcess(0x0038, False, process_id.value)
    if not process:
        _desktop_icon_cache = (time.monotonic(), [])
        return []

    class ItemRect(ctypes.Structure):
        _fields_ = (("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG))

    try:
        remote_rect = kernel32.VirtualAllocEx(process, None, ctypes.sizeof(ItemRect), 0x3000, 0x04)
        if not remote_rect:
            _desktop_icon_cache = (time.monotonic(), [])
            return []
        send_message = user32.SendMessageW
        send_message.argtypes = (wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t)
        send_message.restype = ctypes.c_ssize_t
        count = min(max(0, send_message(list_view, 0x1004, 0, 0)), 512)
        write = ctypes.windll.kernel32.WriteProcessMemory
        read = ctypes.windll.kernel32.ReadProcessMemory
        client_to_screen = user32.ClientToScreen
        client_to_screen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
        client_to_screen.restype = wintypes.BOOL
        centers = []
        transferred = ctypes.c_size_t()
        for index in range(count):
            rect = ItemRect(0, 0, 0, 0)
            if not write(process, remote_rect, ctypes.byref(rect), ctypes.sizeof(rect),
                         ctypes.byref(transferred)):
                continue
            if not send_message(list_view, 0x100E, index, remote_rect):
                continue
            if not read(process, remote_rect, ctypes.byref(rect), ctypes.sizeof(rect),
                        ctypes.byref(transferred)):
                continue
            point = wintypes.POINT((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
            if client_to_screen(list_view, ctypes.byref(point)):
                centers.append((point.x, point.y))
        _desktop_icon_cache = (time.monotonic(), centers)
        return centers
    finally:
        if "remote_rect" in locals() and remote_rect:
            kernel32.VirtualFreeEx(process, remote_rect, 0, 0x8000)
        kernel32.CloseHandle(process)


def _interaction_targets(cursor: tuple[int, int]) -> list[tuple[int, int]]:
    x, y = cursor
    targets = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
    user32.GetSystemMetrics.restype = ctypes.c_int
    hwnd = user32.GetForegroundWindow()
    rect = wintypes.RECT()
    if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
        targets.extend((
            (min(max(x, left), right), top),
            (min(max(x, left), right), bottom),
            (left, min(max(y, top), bottom)),
            (right, min(max(y, top), bottom)),
        ))
        button_width = user32.GetSystemMetrics(30)
        button_height = user32.GetSystemMetrics(31)
        if button_width > 0 and button_height > 0:
            button_y = top + button_height // 2
            targets.extend((right - button_width * step + button_width // 2, button_y)
                           for step in (1, 2, 3))

    if active_process() == "explorer.exe":
        targets.extend(_desktop_icon_centers())
    return targets


def move(dx: float, dy: float, magnet_strength: float = 0) -> None:
    if magnet_strength > 0:
        cursor = wintypes.POINT()
        user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
        user32.GetCursorPos.restype = wintypes.BOOL
        if not user32.GetCursorPos(ctypes.byref(cursor)):
            raise ctypes.WinError(ctypes.get_last_error())
        position = (cursor.x, cursor.y)
        targets = _interaction_targets(
            (round(cursor.x + dx), round(cursor.y + dy)))
        snap = _magnet_snap_target(dx, dy, position, targets, magnet_strength)
        if snap is not None:
            user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
            user32.SetCursorPos.restype = wintypes.BOOL
            if not user32.SetCursorPos(*snap):
                raise ctypes.WinError(ctypes.get_last_error())
            return
        dx, dy = _magnetized_delta(
            dx, dy, position, targets, magnet_strength)
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

def open_keyboard() -> None:
    keyboard = Path(os.environ["WINDIR"]) / "System32" / "osk.exe"
    if not keyboard.is_file():
        raise FileNotFoundError(f"Windows on-screen keyboard not found: {keyboard}")
    os.startfile(str(keyboard))

def perform(action: str, keys: str = "") -> None:
    if action == "none": return
    if action.endswith("_click"):
        click(action.removesuffix("_click"))
    elif action == "win": key_combo("win")
    elif action == "volume_up": key_combo("volume_up")
    elif action == "volume_down": key_combo("volume_down")
    elif action == "previous": key_combo("ctrl+tab")
    elif action == "next": key_combo("tab")
    elif action == "tab_previous": key_combo("ctrl+shift+tab")
    elif action == "tab_next": key_combo("ctrl+tab")
    elif action == "play_pause": key_combo("space")
    elif action == "fullscreen": key_combo("f")
    elif action == "subtitles": key_combo("c")
    elif action == "key_combo": key_combo(keys)
