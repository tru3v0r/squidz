import pytest
from squidz.core.models import Settings, Profile, Binding

def test_defaults():
    p = Settings.defaults().profiles['Valentin']
    assert p.resolve('a').action == 'left_click'
    assert p.resolve('l', 'firefox.exe').action == 'tab_previous'
    assert p.resolve('b', 'brave.exe', 'youtube.com').action == 'right_click'
    assert p.resolve('x', 'firefox.exe', 'www.youtube.com').action == 'play_pause'
    assert p.resolve('y', 'brave.exe', 'm.youtube.com').action == 'fullscreen'

def test_roundtrip():
    original = Settings.defaults()
    assert Settings.parse(original.dump()).dump() == original.dump()

def test_legacy_profile_defaults_magnet_strength():
    raw = Settings.defaults().dump()
    raw["profiles"]["Valentin"].pop("magnet_strength")
    assert Settings.parse(raw).profiles["Valentin"].magnet_strength == 50

def test_legacy_youtube_subtitle_override_is_removed():
    raw = Settings.defaults().dump()
    raw["profiles"]["Valentin"]["sites"]["youtube.com"]["b"] = {"action": "subtitles"}
    profile = Settings.parse(raw).profiles["Valentin"]
    assert "b" not in profile.sites["youtube.com"]
    assert profile.resolve("b", domain="youtube.com").action == "right_click"

def test_startup_settings_roundtrip_and_legacy_defaults():
    original = Settings.defaults()
    original.startup_enabled = True
    original.start_minimized = True
    assert Settings.parse(original.dump()).start_minimized is True
    legacy = original.dump()
    legacy.pop("startup_enabled")
    legacy.pop("start_minimized")
    assert Settings.parse(legacy).startup_enabled is False

@pytest.mark.parametrize("name", ["startup_enabled", "start_minimized"])
def test_reject_invalid_startup_setting(name):
    raw = Settings.defaults().dump()
    raw[name] = "true"
    with pytest.raises(ValueError, match="Startup options"):
        Settings.parse(raw)

def test_primary_device_roundtrip():
    original = Settings.defaults()
    original.primary_device = "controller-guid#0"
    assert Settings.parse(original.dump()).primary_device == original.primary_device

def test_primary_device_defaults_for_existing_settings():
    original = Settings.defaults().dump()
    original.pop("primary_device")
    assert Settings.parse(original).primary_device is None

def test_reject_invalid_primary_device():
    raw = Settings.defaults().dump()
    raw["primary_device"] = 42
    with pytest.raises(ValueError, match="Primary device"):
        Settings.parse(raw)

def test_reject_invalid_action():
    with pytest.raises(ValueError):
        Binding.parse({'action': 'shell_command'})

def test_longest_site_match():
    p = Profile('test', sites={'example.com': {'a': Binding('left_click')}, 'app.example.com': {'a': Binding('right_click')}})
    assert p.resolve('a', domain='app.example.com').action == 'right_click'
