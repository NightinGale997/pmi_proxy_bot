import datetime
from pmi_proxy_bot.schedule_manager import ScheduleManager
from pmi_proxy_bot.config import TIMEZONE


@pytest.mark.parametrize(
    "test_date, expected_parity",
    [
        (datetime.datetime(2024, 9, 30, tzinfo=TIMEZONE), "Числитель"),  # Start date, week 0
        (datetime.datetime(2024, 10, 6, tzinfo=TIMEZONE), "Числитель"),  # End of week 0
        (datetime.datetime(2024, 10, 7, tzinfo=TIMEZONE), "Знаменатель"), # Start of week 1
    ],
)
def test_calculate_week_parity(monkeypatch, test_date, expected_parity):
    class FakeDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return test_date

    monkeypatch.setattr("pmi_proxy_bot.schedule_manager.datetime.datetime", FakeDateTime)
    parity = ScheduleManager.calculate_week_parity()
    assert parity == expected_parity
