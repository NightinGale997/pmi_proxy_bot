import datetime
import os
from pmi_proxy_bot import telegram_message_handler
from pmi_proxy_bot.telegram_message_handler import TelegramMessageHandler
from pmi_proxy_bot.database_manager import DatabaseManager

class DummyService:
    def __getattr__(self, name):
        def method(*args, **kwargs):
            return None
        return method

class DummyTelegram:
    def __init__(self, tmp_dir):
        self.tmp_dir = tmp_dir
        self.base_url = ""

    def get_telegram_file_path(self, file_id):
        return os.path.join(self.tmp_dir, file_id)

    def download_telegram_file(self, file_path):
        open(file_path, "wb").close()
        return file_path

    def __getattr__(self, name):
        def method(*args, **kwargs):
            return None
        return method

class CaptureVK:
    def __init__(self):
        self.chat_id = 1
        self.sent_messages = []

    def upload_photo(self, file_path):
        return os.path.basename(file_path)

    def upload_document(self, file_path, title="file"):
        return os.path.basename(file_path)

    def send_message(self, peer_id, message, attachment=None, format_data=None, chat_id=None):
        self.sent_messages.append({"message": message, "attachment": attachment})

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


def test_forward_media_group(tmp_path):
    tg = DummyTelegram(tmp_path)
    vk = CaptureVK()
    handler = TelegramMessageHandler(tg, vk, DatabaseManager(':memory:'))

    msg1 = {
        'chat': {'id': 1},
        'media_group_id': 'g1',
        'caption': 'first',
        'photo': [{'file_id': 'photo1', 'width': 100}],
        'from': {'first_name': 'Alice'}
    }
    msg2 = {
        'chat': {'id': 1},
        'media_group_id': 'g1',
        'caption': 'second',
        'photo': [{'file_id': 'photo2', 'width': 100}],
        'from': {'first_name': 'Alice'}
    }

    handler.handle_update({'message': msg1})
    handler.handle_update({'message': msg2})

    handler.flush_media_group('g1')

    assert len(vk.sent_messages) == 1
    sent = vk.sent_messages[0]
    assert 'first' in sent['message']
    assert 'second' in sent['message']
    assert sent['attachment'] == 'photo1,photo2'
