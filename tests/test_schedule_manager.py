import datetime
from pmi_proxy_bot.schedule_manager import ScheduleManager
from pmi_proxy_bot.config import TIMEZONE


def test_calculate_week_parity(monkeypatch):
    fake_now = datetime.datetime(2024, 9, 30, tzinfo=TIMEZONE)

    class FakeDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return fake_now

    monkeypatch.setattr('pmi_proxy_bot.schedule_manager.datetime.datetime', FakeDateTime)
    parity = ScheduleManager.calculate_week_parity()
    assert parity == 'Числитель'
