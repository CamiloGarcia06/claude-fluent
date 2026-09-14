from fluent.settings.application.read_settings import ReadSettings


class MemoryState:
    def __init__(self, stored=None):
        self.stored = stored

    def read(self):
        return self.stored

    def write(self, state):
        self.stored = state
        return state


def test_defaults_fill_missing_and_garbage():
    assert ReadSettings(MemoryState({}))() == {"daily_goal": 40}
    assert ReadSettings(MemoryState(None))() == {"daily_goal": 40}
    assert ReadSettings(MemoryState({"daily_goal": 20, "last_sync": "x"}))() == {
        "daily_goal": 20,
        "last_sync": "x",
    }
