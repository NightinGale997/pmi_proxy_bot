import datetime
from pmi_proxy_bot.database_manager import DatabaseManager
from pmi_proxy_bot.config import TIMEZONE


def test_add_and_get_event(tmp_path):
    db_file = tmp_path / "events.db"
    manager = DatabaseManager(str(db_file))
    event_time = datetime.datetime.now(TIMEZONE) + datetime.timedelta(hours=1)
    manager.add_event(event_time, "Title", "Desc")
    events = manager.get_all_events()
    assert len(events) == 1
    assert events[0]["title"] == "Title"
    upcoming = manager.get_upcoming_events()
    assert events[0]["id"] == upcoming[0]["id"]
    assert manager.delete_event(events[0]["id"]) is True
