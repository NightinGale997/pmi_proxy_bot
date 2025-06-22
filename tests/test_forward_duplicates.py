import re
from pmi_proxy_bot.telegram_message_handler import TelegramMessageHandler
from pmi_proxy_bot.database_manager import DatabaseManager

class DummyService:
    def __getattr__(self, name):
        def method(*args, **kwargs):
            return None
        return method

class CaptureVK:
    def __init__(self):
        self.chat_id = 1
        self.sent_messages = []
    def upload_photo(self, *a, **k):
        return None
    def upload_document(self, *a, **k):
        return None
    def send_message(self, peer_id, message, attachment=None, format_data=None, chat_id=None):
        self.sent_messages.append(message)

def test_forward_text_no_duplicate():
    vk = CaptureVK()
    handler = TelegramMessageHandler(DummyService(), vk, DatabaseManager(':memory:'))
    msg = {'chat': {'id': 1}, 'text': 'hello', 'from': {'first_name': 'John', 'last_name': 'Doe'}}
    handler.forward_to_vk(msg)
    assert len(vk.sent_messages) == 1
    assert len(re.findall('hello', vk.sent_messages[0])) == 1
