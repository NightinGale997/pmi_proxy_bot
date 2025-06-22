import datetime
from pmi_proxy_bot import telegram_message_handler
from pmi_proxy_bot.telegram_message_handler import TelegramMessageHandler
from pmi_proxy_bot.database_manager import DatabaseManager

class DummyService:
    def __getattr__(self, name):
        def method(*args, **kwargs):
            return None
        return method

def test_add_event_integration(tmp_path, monkeypatch):
    db_file = tmp_path / 'db.sqlite'
    db = DatabaseManager(str(db_file))
    monkeypatch.setattr(telegram_message_handler, 'datetime', datetime, raising=False)
    handler = TelegramMessageHandler(DummyService(), DummyService(), db)
    reply = handler.add_event_from_text('/add_event 01.01.2099 12:00 Test | Desc')
    assert 'добавлено' in reply.lower()
    events = db.get_all_events()
    assert len(events) == 1
    assert events[0]['title'] == 'Test'
