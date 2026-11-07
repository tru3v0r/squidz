"""Opt-in Windows event sources used by the debug window."""
from __future__ import annotations

import ctypes
import csv
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

_CALLBACK = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
_WM_QUIT = 0x0012
_PM_NOREMOVE = 0x0000
_EVENT_OBJECT_CREATE = 0x8000
_EVENT_OBJECT_DESTROY = 0x8001
_EVENT_OBJECT_SHOW = 0x8002
_EVENT_OBJECT_HIDE = 0x8003
_EVENT_OBJECT_FOCUS = 0x8005
_EVENT_OBJECT_NAMECHANGE = 0x800C
_EVENT_OBJECT_VALUECHANGE = 0x800E
_EVENT_OBJECT_LOCATIONCHANGE = 0x800B
_EVENT_SYSTEM_FOREGROUND = 0x0003
_EVENT_SYSTEM_DIALOGSTART = 0x0010
_EVENT_SYSTEM_DIALOGEND = 0x0011
_EVENT_SYSTEM_MINIMIZESTART = 0x0016
_EVENT_SYSTEM_MINIMIZEEND = 0x0017
_WINEVENT_OUTOFCONTEXT = 0x0000
_WINEVENT_SKIPOWNPROCESS = 0x0002
_ETW_PROVIDERS = (
    ("Microsoft-Windows-UIAutomationCore", "820A42D8-38C4-465D-B64E-D7D56EA1D612"),
    ("Microsoft-Windows-InputSwitch", "BB8E7234-BBF4-48A7-8741-339206ED1DFB"),
    ("Microsoft-Windows-Win32k", "8C416C79-D49B-4F01-A467-E56D3AA8234C"),
)


class _MSG(ctypes.Structure):
    _fields_ = (
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    )


class _RawInputDevice(ctypes.Structure):
    _fields_ = (
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    )


class _RawInputHeader(ctypes.Structure):
    _fields_ = (
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    )


class _ShellExecuteInfo(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    )


class RawInputListener(QAbstractNativeEventFilter):
    """Receives raw keyboard and mouse message types without recording key data."""

    def __init__(self, emit):
        super().__init__()
        self.emit = emit
        self.enabled = False

    def set_enabled(self, enabled: bool, hwnd=None):
        if os.name != "nt":
            raise OSError("Raw Input is available only on Windows.")

        user32 = ctypes.windll.user32
        user32.RegisterRawInputDevices.argtypes = (
            ctypes.POINTER(_RawInputDevice), wintypes.UINT, wintypes.UINT)
        user32.RegisterRawInputDevices.restype = wintypes.BOOL
        flags = 0x0100 if enabled else 0x0001
        target = hwnd if enabled else None
        devices = (_RawInputDevice * 2)(
            _RawInputDevice(0x01, 0x02, flags, target),
            _RawInputDevice(0x01, 0x06, flags, target),
        )
        if not user32.RegisterRawInputDevices(
                devices, len(devices), ctypes.sizeof(_RawInputDevice)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.enabled = enabled

    def nativeEventFilter(self, event_type, message):
        if (not self.enabled
                or event_type not in (b"windows_generic_MSG", "windows_generic_MSG")):
            return False, 0
        try:
            native_message = ctypes.cast(message, ctypes.POINTER(_MSG)).contents
            if native_message.message != 0x00FF:
                return False, 0
            user32 = ctypes.windll.user32
            user32.GetRawInputData.argtypes = (
                wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p,
                ctypes.POINTER(wintypes.UINT), wintypes.UINT)
            user32.GetRawInputData.restype = wintypes.UINT
            size = wintypes.UINT()
            header_size = ctypes.sizeof(_RawInputHeader)
            result = user32.GetRawInputData(
                native_message.lParam, 0x10000003, None, ctypes.byref(size), header_size)
            if result == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
            if size.value < header_size:
                return False, 0
            buffer = ctypes.create_string_buffer(size.value)
            result = user32.GetRawInputData(
                native_message.lParam, 0x10000003, buffer, ctypes.byref(size), header_size)
            if result == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
            raw_input = ctypes.cast(buffer, ctypes.POINTER(_RawInputHeader)).contents
            event = {0: "mouse input", 1: "keyboard input", 2: "HID input"}.get(
                raw_input.dwType, "unknown raw input")
            self.emit("raw_input", event)
        except Exception as exc:
            self.emit("raw_input", f"ERROR: {exc}")
        return False, 0


class _Worker:
    def __init__(self, source: str, emit, report_error):
        self.source = source
        self.emit = emit
        self.report_error = report_error
        self.stop_event = threading.Event()
        self.thread_id: int | None = None
        self.thread: threading.Thread | None = None

    def start(self, target):
        self.thread = threading.Thread(
            target=self._run, args=(target,), daemon=self.source != "etw")
        self.thread.start()

    def _run(self, target):
        try:
            target(self)
        except Exception as exc:
            self.report_error(self.source, str(exc))

    def stop(self):
        self.stop_event.set()
        if self.thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(
                self.thread_id, _WM_QUIT, 0, 0)


class WindowsEventSources(QObject):
    """Starts and stops independent Windows event listeners."""

    event_received = Signal(str, str)
    source_error = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: dict[str, _Worker] = {}

    def set_enabled(self, source: str, enabled: bool):
        if source == "raw_input":
            raise ValueError("Raw Input is bound to the debug window handle.")
        if enabled:
            current = self._workers.get(source)
            if current is not None and current.thread and current.thread.is_alive():
                if current.stop_event.is_set():
                    raise RuntimeError(f"{source} is still stopping.")
                return
            targets = {
                "set_windows_hook": self._run_windows_hook,
                "win_event_hook": self._run_win_event_hook,
                "uia": self._run_uia,
                "etw": self._run_etw,
            }
            if source not in targets:
                raise ValueError(f"Unknown event source: {source}")
            worker = _Worker(source, self.event_received.emit, self.source_error.emit)
            self._workers[source] = worker
            worker.start(targets[source])
            return

        worker = self._workers.get(source)
        if worker is not None:
            worker.stop()

    def stop_all(self):
        workers = tuple(self._workers.values())
        self._workers.clear()
        for worker in workers:
            worker.stop()
        for worker in workers:
            if worker.thread is not None:
                worker.thread.join(timeout=3)

    @staticmethod
    def _message_loop(worker: _Worker):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        user32.PeekMessageW.argtypes = (
            ctypes.POINTER(_MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
            wintypes.UINT)
        user32.PeekMessageW.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = (
            ctypes.POINTER(_MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
        user32.GetMessageW.restype = ctypes.c_int
        user32.TranslateMessage.argtypes = (ctypes.POINTER(_MSG),)
        user32.DispatchMessageW.argtypes = (ctypes.POINTER(_MSG),)

        thread_id = kernel32.GetCurrentThreadId()
        worker.thread_id = thread_id
        message = _MSG()
        user32.PeekMessageW(ctypes.byref(message), None, 0, 0, _PM_NOREMOVE)
        while not worker.stop_event.is_set():
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result == -1:
                raise ctypes.WinError(ctypes.get_last_error())
            if result == 0:
                break
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

    @staticmethod
    def _run_windows_hook(worker: _Worker):
        if os.name != "nt":
            raise OSError("SetWindowsHookEx is available only on Windows.")

        user32 = ctypes.windll.user32
        hook_handles = []
        callbacks = []
        hook_proc_type = _CALLBACK(
            ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.argtypes = (
            ctypes.c_int, hook_proc_type, wintypes.HINSTANCE, wintypes.DWORD)
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = (
            wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL

        def hook_callback(hook_type):
            def callback(code, message, data):
                if code >= 0:
                    if hook_type == 13:
                        names = {
                            0x0100: "keyboard key down",
                            0x0101: "keyboard key up",
                            0x0104: "system key down",
                            0x0105: "system key up",
                        }
                    else:
                        names = {
                            0x0201: "left button down",
                            0x0202: "left button up",
                            0x0204: "right button down",
                            0x0205: "right button up",
                            0x0207: "middle button down",
                            0x0208: "middle button up",
                            0x020A: "mouse wheel",
                            0x020B: "X button down",
                            0x020C: "X button up",
                        }
                    event = names.get(message)
                    if event:
                        worker.emit(worker.source, event)
                return user32.CallNextHookEx(None, code, message, data)
            return hook_proc_type(callback)

        try:
            for hook_type in (13, 14):
                callback = hook_callback(hook_type)
                handle = user32.SetWindowsHookExW(hook_type, callback, None, 0)
                if not handle:
                    raise ctypes.WinError(ctypes.get_last_error())
                callbacks.append(callback)
                hook_handles.append(handle)
            WindowsEventSources._message_loop(worker)
        finally:
            for handle in hook_handles:
                if not user32.UnhookWindowsHookEx(handle):
                    worker.report_error(worker.source, "UnhookWindowsHookEx failed.")

    @staticmethod
    def _run_win_event_hook(worker: _Worker):
        if os.name != "nt":
            raise OSError("SetWinEventHook is available only on Windows.")

        user32 = ctypes.windll.user32
        win_event_proc = _CALLBACK(
            None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
            wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
        user32.SetWinEventHook.argtypes = (
            wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, win_event_proc,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD)
        user32.SetWinEventHook.restype = wintypes.HANDLE
        user32.UnhookWinEvent.argtypes = (wintypes.HANDLE,)
        user32.UnhookWinEvent.restype = wintypes.BOOL
        names = {
            _EVENT_OBJECT_CREATE: "object created",
            _EVENT_OBJECT_DESTROY: "object destroyed",
            _EVENT_OBJECT_SHOW: "object shown",
            _EVENT_OBJECT_HIDE: "object hidden",
            _EVENT_OBJECT_FOCUS: "object focused",
            _EVENT_OBJECT_NAMECHANGE: "object name changed",
            _EVENT_OBJECT_VALUECHANGE: "object value changed",
            _EVENT_OBJECT_LOCATIONCHANGE: "object moved",
            _EVENT_SYSTEM_FOREGROUND: "foreground window changed",
            _EVENT_SYSTEM_DIALOGSTART: "dialog opened",
            _EVENT_SYSTEM_DIALOGEND: "dialog closed",
            _EVENT_SYSTEM_MINIMIZESTART: "window minimized",
            _EVENT_SYSTEM_MINIMIZEEND: "window restored",
        }
        hooks = []
        callbacks = []

        def callback_for(event_id):
            def callback(*_args):
                worker.emit(worker.source, names[event_id])
            return win_event_proc(callback)

        try:
            for event_id in names:
                callback = callback_for(event_id)
                hook = user32.SetWinEventHook(
                    event_id, event_id, None, callback, 0, 0,
                    _WINEVENT_OUTOFCONTEXT | _WINEVENT_SKIPOWNPROCESS)
                if not hook:
                    raise ctypes.WinError(ctypes.get_last_error())
                callbacks.append(callback)
                hooks.append(hook)
            WindowsEventSources._message_loop(worker)
        finally:
            for hook in hooks:
                if not user32.UnhookWinEvent(hook):
                    worker.report_error(worker.source, "UnhookWinEvent failed.")

    @staticmethod
    def _run_uia(worker: _Worker):
        if os.name != "nt":
            raise OSError("UI Automation events are available only on Windows.")

        import pythoncom
        import comtypes
        from comtypes.client import CreateObject, GetModule

        pythoncom.CoInitialize()
        client = None
        try:
            uia = GetModule("UIAutomationCore.dll")

            class FocusHandler(comtypes.COMObject):
                _com_interfaces_ = [uia.IUIAutomationFocusChangedEventHandler]

                def HandleFocusChangedEvent(self, _sender):
                    worker.emit(worker.source, "focus changed")

            class StructureHandler(comtypes.COMObject):
                _com_interfaces_ = [uia.IUIAutomationStructureChangedEventHandler]

                def HandleStructureChangedEvent(self, _sender, change_type, _runtime_id):
                    worker.emit(worker.source, f"UI structure changed ({change_type})")

            client = CreateObject(uia.CUIAutomation, interface=uia.IUIAutomation)
            focus_handler = FocusHandler()
            structure_handler = StructureHandler()
            root = client.GetRootElement()
            client.AddFocusChangedEventHandler(None, focus_handler)
            client.AddStructureChangedEventHandler(root, 7, None, structure_handler)
            while not worker.stop_event.wait(0.05):
                pythoncom.PumpWaitingMessages()
        finally:
            if client is not None:
                client.RemoveAllEventHandlers()
            pythoncom.CoUninitialize()

    @staticmethod
    def _run_etw(worker: _Worker):
        if os.name != "nt":
            raise OSError("ETW is available only on Windows.")

        available = subprocess.run(
            ["logman", "query", "providers"], capture_output=True, text=True,
            check=False, timeout=10)
        if available.returncode:
            raise RuntimeError(available.stderr.strip() or available.stdout.strip())
        provider_lines = available.stdout.splitlines()
        providers = []
        for name, guid in _ETW_PROVIDERS:
            if any(line.strip().startswith(name) for line in provider_lines):
                providers.append((name, guid))
        if not providers:
            raise RuntimeError("No supported UI/input ETW providers are installed.")

        session = f"SquidzDebug-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        with tempfile.TemporaryDirectory(prefix="squidz-etw-") as directory:
            etl_path = os.path.join(directory, "events.etl")
            csv_path = os.path.join(directory, "events.csv")
            provider_file = os.path.join(directory, "providers.txt")
            ready_file = os.path.join(directory, "ready.txt")
            stop_file = os.path.join(directory, "stop.txt")
            result_file = os.path.join(directory, "result.txt")
            with open(provider_file, "w", encoding="utf-8") as stream:
                for _, guid in providers:
                    stream.write(f"{{{guid}}} 0xFFFFFFFFFFFFFFFF 5\n")

            helper_arguments = [
                "--session", session,
                "--providers", provider_file,
                "--etl", etl_path,
                "--ready", ready_file,
                "--stop", stop_file,
                "--result", result_file,
                "--parent-pid", str(os.getpid()),
            ]
            helper_process = WindowsEventSources._start_elevated_helper(helper_arguments)
            try:
                deadline = time.monotonic() + 30
                while not os.path.exists(ready_file) and not worker.stop_event.is_set():
                    if WindowsEventSources._helper_exited(helper_process):
                        raise RuntimeError(
                            WindowsEventSources._helper_failure(
                                helper_process, ready_file, result_file))
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Timed out while starting the elevated ETW session.")
                    worker.stop_event.wait(0.1)
                if worker.stop_event.is_set():
                    return
                with open(ready_file, encoding="utf-8") as stream:
                    ready_message = stream.read()
                if not ready_message.startswith("READY"):
                    raise RuntimeError(ready_message.removeprefix("ERROR\n").strip())

                worker.emit(
                    worker.source,
                    "listening to " + ", ".join(name for name, _ in providers))
                consumer = subprocess.Popen(
                    ["tracerpt", "-rt", session, "-o", csv_path, "-of", "CSV",
                     "-lr", "-y"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    text=True)
                offset = 0
                header: list[str] | None = None

                def read_available_events():
                    nonlocal offset, header
                    if not os.path.exists(csv_path):
                        return
                    with open(csv_path, encoding="utf-8-sig", errors="replace") as stream:
                        stream.seek(offset)
                        while line := stream.readline():
                            offset = stream.tell()
                            row = next(csv.reader([line]), [])
                            if not row:
                                continue
                            if header is None:
                                header = row
                                continue
                            fields = dict(zip(header, row))
                            event_id = next(
                                (value for key, value in fields.items()
                                 if "event id" in key.lower() or key.lower() == "id"),
                                "")
                            provider_name = next(
                                (value for key, value in fields.items()
                                 if "provider name" in key.lower()),
                                "Windows provider")
                            worker.emit(
                                worker.source,
                                f"{provider_name} event {event_id}".strip())

                while not worker.stop_event.wait(0.1):
                    if consumer.poll() is not None:
                        error = consumer.stderr.read() if consumer.stderr else ""
                        raise RuntimeError(error.strip() or "The ETW consumer stopped.")
                    read_available_events()
            finally:
                try:
                    with open(stop_file, "w", encoding="utf-8"):
                        pass
                    if not WindowsEventSources._wait_for_helper(helper_process, 35000):
                        raise TimeoutError(
                            "Timed out while stopping the elevated ETW session.")
                    if "consumer" in locals():
                        try:
                            consumer.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            consumer.terminate()
                            consumer.wait(timeout=2)
                        if "read_available_events" in locals():
                            read_available_events()
                    if os.path.exists(result_file):
                        with open(result_file, encoding="utf-8") as stream:
                            cleanup_error = stream.read().strip()
                        if cleanup_error:
                            worker.report_error(worker.source, cleanup_error)
                finally:
                    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
                    kernel32.CloseHandle.restype = wintypes.BOOL
                    if not kernel32.CloseHandle(helper_process):
                        raise ctypes.WinError(ctypes.get_last_error())

    @staticmethod
    def _start_elevated_helper(arguments: list[str]):
        if getattr(sys, "frozen", False):
            command_line = subprocess.list2cmdline(
                ["--squidz-etw-helper", *arguments])
        else:
            command_line = subprocess.list2cmdline(
                ["-m", "squidz.infra.etw_helper", *arguments])
        info = _ShellExecuteInfo()
        info.cbSize = ctypes.sizeof(info)
        info.fMask = 0x00000040
        info.lpVerb = "runas"
        info.lpFile = sys.executable
        info.lpParameters = command_line
        info.nShow = 0
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        shell32.ShellExecuteExW.argtypes = (ctypes.POINTER(_ShellExecuteInfo),)
        shell32.ShellExecuteExW.restype = wintypes.BOOL
        if not shell32.ShellExecuteExW(ctypes.byref(info)):
            error = ctypes.get_last_error()
            if error == 1223:
                raise PermissionError("ETW elevation was cancelled in the UAC prompt.")
            raise ctypes.WinError(error)
        return info.hProcess

    @staticmethod
    def _helper_exited(process_handle) -> bool:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        result = kernel32.WaitForSingleObject(process_handle, 0)
        if result == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return result == 0

    @staticmethod
    def _wait_for_helper(process_handle, timeout_ms: int) -> bool:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        result = kernel32.WaitForSingleObject(process_handle, timeout_ms)
        if result == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return result == 0

    @staticmethod
    def _helper_failure(process_handle, ready_file: str, result_file: str) -> str:
        for path in (ready_file, result_file):
            if os.path.exists(path):
                with open(path, encoding="utf-8") as stream:
                    message = stream.read().strip()
                if message:
                    return message.removeprefix("ERROR\n")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetExitCodeProcess.argtypes = (
            wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(
                process_handle, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return f"The elevated ETW helper exited with code {exit_code.value}."
