"""Validated, versioned configuration domain model."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

BUTTONS = ("a", "b", "x", "y", "l", "r", "minus", "plus", "home", "right_stick")
ACTIONS = ("none", "left_click", "right_click", "middle_click", "win", "volume_up", "volume_down", "previous", "next", "tab_previous", "tab_next", "play_pause", "fullscreen", "subtitles", "key_combo", "open_settings")
DEFAULT_BINDINGS = {"a": "left_click", "b": "right_click", "l": "previous", "r": "next", "minus": "volume_down", "plus": "volume_up", "home": "win", "right_stick": "middle_click"}
BROWSER_BINDINGS = {"l": "tab_previous", "r": "tab_next"}
YOUTUBE_BINDINGS = {"x": "play_pause", "y": "fullscreen"}

@dataclass
class Binding:
    action: str = "none"
    keys: str = ""

    @classmethod
    def parse(cls, value: Any) -> "Binding":
        if isinstance(value, str):
            value = {"action": value}
        if not isinstance(value, dict) or value.get("action", "none") not in ACTIONS:
            raise ValueError(f"Invalid binding: {value!r}")
        return cls(value.get("action", "none"), str(value.get("keys", "")))

@dataclass
class Profile:
    name: str
    global_bindings: dict[str, Binding] = field(default_factory=dict)
    apps: dict[str, dict[str, Binding]] = field(default_factory=dict)
    sites: dict[str, dict[str, Binding]] = field(default_factory=dict)
    mouse_speed: float = 16.0
    scroll_speed: float = 3.0
    deadzone: float = 0.18
    magnet_strength: float = 50.0

    @classmethod
    def parse(cls, name: str, raw: dict) -> "Profile":
        def parse_map(m):
            if not isinstance(m, dict):
                raise ValueError("Bindings must be a dictionary")
            if any(k not in BUTTONS for k in m):
                raise ValueError("Unknown controller button")
            return {k: Binding.parse(v) for k, v in m.items()}
        return cls(name, parse_map(raw.get("global_bindings", {})),
                   {k.lower(): parse_map(v) for k, v in raw.get("apps", {}).items()},
                   {k.lower(): parse_map(v) for k, v in raw.get("sites", {}).items()},
                   float(raw.get("mouse_speed", 16)), float(raw.get("scroll_speed", 3)),
                   float(raw.get("deadzone", .18)), float(raw.get("magnet_strength", 50)))

    def resolve(self, button: str, app: str = "", domain: str = "") -> Binding:
        result = self.global_bindings.get(button, Binding())
        result = self.apps.get(app.lower(), {}).get(button, result)
        domain = domain.lower().removeprefix("www.")
        matching = sorted((host for host in self.sites if domain == host or domain.endswith("." + host)), key=len)
        for host in matching:
            result = self.sites[host].get(button, result)
        return result

    def dump(self) -> dict:
        return asdict(self) | {"name": self.name}

@dataclass
class Settings:
    profiles: dict[str, Profile]
    assignments: dict[str, str] = field(default_factory=dict)
    known_devices: dict[str, str] = field(default_factory=dict)
    browser_token: str = ""
    port: int = 8765
    primary_device: str | None = None
    startup_enabled: bool = False
    start_minimized: bool = False

    @classmethod
    def defaults(cls) -> "Settings":
        p = Profile("Valentin", {k: Binding(v) for k, v in DEFAULT_BINDINGS.items()},
                    {"firefox.exe": {k: Binding(v) for k, v in BROWSER_BINDINGS.items()},
                     "brave.exe": {k: Binding(v) for k, v in BROWSER_BINDINGS.items()}},
                    {"youtube.com": {k: Binding(v) for k, v in YOUTUBE_BINDINGS.items()}})
        return cls({"Valentin": p, "Invité 1": Profile("Invité 1", {k: Binding(v) for k, v in DEFAULT_BINDINGS.items()})})

    @classmethod
    def parse(cls, raw: dict) -> "Settings":
        if raw.get("schema_version") != 1:
            raise ValueError("Unsupported settings schema version")
        profiles = {name: Profile.parse(name, p) for name, p in raw["profiles"].items()}
        if not profiles:
            raise ValueError("At least one profile required")
        for profile in profiles.values():
            youtube = profile.sites.get("youtube.com")
            if youtube and youtube.get("b", Binding()).action == "subtitles":
                youtube.pop("b")
        assignments = dict(raw.get("assignments", {}))
        if any(v not in profiles for v in assignments.values()):
            raise ValueError("An assignment references a missing profile")
        primary_device = raw.get("primary_device")
        if primary_device is not None and not isinstance(primary_device, str):
            raise ValueError("Primary device must be a device key or null")
        startup_enabled = raw.get("startup_enabled", False)
        start_minimized = raw.get("start_minimized", False)
        if not isinstance(startup_enabled, bool) or not isinstance(start_minimized, bool):
            raise ValueError("Startup options must be booleans")
        return cls(profiles, assignments, dict(raw.get("known_devices", {})),
                   str(raw.get("browser_token", "")), int(raw.get("port", 8765)),
                   primary_device, startup_enabled, start_minimized)

    def dump(self) -> dict:
        return {"schema_version": 1, "profiles": {k: v.dump() for k, v in self.profiles.items()},
                "assignments": self.assignments, "known_devices": self.known_devices,
                "browser_token": self.browser_token, "port": self.port,
                "primary_device": self.primary_device,
                "startup_enabled": self.startup_enabled,
                "start_minimized": self.start_minimized}
