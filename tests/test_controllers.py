import pytest

from squidz.core.controllers import battery_percentage


@pytest.mark.parametrize(
    ("level", "percentage"),
    [
        ("empty", 0),
        ("LOW", 20),
        ("medium", 60),
        ("full", 100),
        ("max", 100),
        ("wired", None),
        ("unknown", None),
    ],
)
def test_battery_percentage(level, percentage):
    assert battery_percentage(level) == percentage
