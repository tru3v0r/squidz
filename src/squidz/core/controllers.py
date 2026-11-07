"""Controller polling, independent device profiles and long-press detection."""
from __future__ import annotations
import time
import pygame
from pygame._sdl2 import controller as sdl_controller
from PySide6.QtCore import QObject, QTimer, Signal
from squidz.core.models import Settings
from squidz.infra import windows

# Standard SDL gamecontroller mapping; button ids may differ for unsupported devices.
BUTTON_MAP = {0: "a", 1: "b", 2: "x", 3: "y", 9: "l", 10: "r", 4: "minus", 6: "plus", 5: "home", 8: "right_stick"}
POWER_PERCENTAGES = {"empty": 0, "low": 20, "medium": 60, "full": 100, "max": 100}

def battery_percentage(power_level: str) -> int | None:
    return POWER_PERCENTAGES.get(power_level.lower())

class ControllerManager(QObject):
    settings_requested = Signal(str)
    devices_changed = Signal()
    error = Signal(str)

    def __init__(self, settings: Settings, bridge):
        super().__init__()
        self.settings, self.bridge = settings, bridge
        self.controllers: dict[str, sdl_controller.Controller] = {}
        self.joysticks: dict[str, pygame.joystick.JoystickType] = {}
        self.power_levels: dict[str, str] = {}
        self.pressed: dict[tuple[str, str], float] = {}
        self.long_handled: set[tuple[str, str]] = set()
        self.held_actions: dict[tuple[str, str], str] = {}
        self.click_presses: set[tuple[str, str]] = set()
        self.scroll_acc: dict[str, float] = {}
        self.last_poll = time.monotonic()
        self.last_power_poll = 0.0
        pygame.init()
        pygame.joystick.init()
        sdl_controller.init()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.poll)
        self.refresh()
        self.timer.start()

    def refresh(self):
        pygame.event.pump()
        previous = set(self.controllers)
        discovered = {}
        joysticks = {}
        power_levels = {}
        # GUID + occurrence index disambiguates identical connected controllers.
        occurrences = {}
        for index in range(pygame.joystick.get_count()):
            if not sdl_controller.is_controller(index):
                continue
            joy = pygame.joystick.Joystick(index)
            joy.init()
            controller = sdl_controller.Controller(index)
            guid = joy.get_guid()
            count = occurrences.get(guid, 0)
            occurrences[guid] = count + 1
            key = f"{guid}#{count}"
            discovered[key] = controller
            joysticks[key] = joy
            power_levels[key] = joy.get_power_level().lower()
            self.settings.known_devices[key] = joy.get_name()
        for token in tuple(self.click_presses):
            if token[0] not in discovered:
                self._release_click(token)
                self.pressed.pop(token, None)
                self.long_handled.discard(token)
        self.controllers = discovered
        self.joysticks = joysticks
        self.power_levels = power_levels
        primary_changed = False
        if discovered and self.settings.primary_device not in discovered:
            self.settings.primary_device = next(iter(discovered))
            primary_changed = True
        if set(discovered) != previous or primary_changed:
            self.devices_changed.emit()

    def _profile(self, key):
        name = self.settings.assignments.get(key)
        return self.settings.profiles.get(name) or next(iter(self.settings.profiles.values()))

    def _dispatch(self, device, button):
        try:
            binding = self._binding(device, button)
            if binding.action == "open_settings":
                if device == self.settings.primary_device:
                    self.settings_requested.emit(device)
            else: windows.perform(binding.action, binding.keys)
        except Exception as exc:
            self.error.emit(str(exc))

    def _binding(self, device, button):
        profile = self._profile(device)
        app = windows.active_process()
        domain = self.bridge.domain(app) if app in ("firefox.exe", "brave.exe") else ""
        return profile.resolve(button, app, domain)

    def _press_button(self, device, button, now):
        token = (device, button)
        self.pressed[token] = now
        try:
            action = self._binding(device, button).action
            if action.endswith("_click"):
                self.click_presses.add(token)
                windows.mouse_button_down(action.removesuffix("_click"))
                self.held_actions[token] = action
        except Exception as exc:
            self.error.emit(str(exc))

    def _release_click(self, token):
        self.click_presses.discard(token)
        action = self.held_actions.pop(token, None)
        if action:
            try:
                windows.mouse_button_up(action.removesuffix("_click"))
            except Exception as exc:
                self.error.emit(str(exc))

    def _release_button(self, device, button):
        token = (device, button)
        if token in self.click_presses:
            self._release_click(token)
        elif token not in self.long_handled:
            self._dispatch(device, button)
        self.pressed.pop(token, None)
        self.long_handled.discard(token)

    def poll(self):
        try:
            pygame.event.pump()
            if pygame.joystick.get_count() != len(self.controllers):
                self.refresh()
            now = time.monotonic()
            dt = min(now - self.last_poll, .05)
            self.last_poll = now
            if now - self.last_power_poll >= 5:
                self.power_levels = {
                    key: joystick.get_power_level().lower()
                    for key, joystick in self.joysticks.items()
                }
                self.last_power_poll = now
            for key, joy in list(self.controllers.items()):
                for index, button in BUTTON_MAP.items():
                    token = (key, button)
                    down = bool(joy.get_button(index))
                    if down and token not in self.pressed:
                        self._press_button(key, button, now)
                    if button == "home" and down and token not in self.long_handled and now - self.pressed[token] >= .8:
                        self.long_handled.add(token)
                        if key == self.settings.primary_device:
                            self.settings_requested.emit(key)
                    if not down and token in self.pressed:
                        self._release_button(key, button)
                p = self._profile(key)
                dz = max(0.0, min(.9, p.deadzone))
                def axis(n):
                    v = joy.get_axis(n) / 32767.0
                    return 0.0 if abs(v) < dz else (abs(v) - dz) / (1 - dz) * (1 if v > 0 else -1)
                # Speed normalized to ~60 Hz; right stick vertical scroll with accumulation.
                x, y = axis(0), axis(1)
                if x or y:
                    windows.move(x * p.mouse_speed * dt * 60, y * p.mouse_speed * dt * 60,
                                 p.magnet_strength)
                wheel = axis(3) * p.scroll_speed * dt * 10
                acc = self.scroll_acc.get(key, 0) - wheel
                steps = int(acc)
                if steps:
                    windows.scroll(steps)
                    acc -= steps
                self.scroll_acc[key] = acc
        except pygame.error as exc:
            self.error.emit(str(exc))
            self.refresh()
