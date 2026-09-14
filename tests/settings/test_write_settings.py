import pytest

from fluent.settings.application.write_settings import WriteSettings
from fluent.settings.domain.errors import InvalidGoal

from .test_read_settings import MemoryState


def test_write_validates_bounds_and_type():
    store = MemoryState({})
    assert WriteSettings(store)({"daily_goal": "25"}) == {"daily_goal": 25}
    assert store.stored == {"daily_goal": 25}
    with pytest.raises(InvalidGoal):
        WriteSettings(store)({"daily_goal": 4})
    with pytest.raises(InvalidGoal):
        WriteSettings(store)({"daily_goal": "muchas"})
    assert WriteSettings(store)({})["daily_goal"] == 25  # sin cambios, no toca
