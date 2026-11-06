import pytest
from squidz.core.models import Settings, Profile, Binding

def test_defaults():
    p = Settings.defaults().profiles['Valentin']
    assert p.resolve('a').action == 'left_click'
    assert p.resolve('l', 'firefox.exe').action == 'tab_previous'
    assert p.resolve('x', 'firefox.exe', 'www.youtube.com').action == 'play_pause'
    assert p.resolve('y', 'brave.exe', 'm.youtube.com').action == 'fullscreen'

def test_roundtrip():
    original = Settings.defaults()
    assert Settings.parse(original.dump()).dump() == original.dump()

def test_reject_invalid_action():
    with pytest.raises(ValueError):
        Binding.parse({'action': 'shell_command'})

def test_longest_site_match():
    p = Profile('test', sites={'example.com': {'a': Binding('left_click')}, 'app.example.com': {'a': Binding('right_click')}})
    assert p.resolve('a', domain='app.example.com').action == 'right_click'
