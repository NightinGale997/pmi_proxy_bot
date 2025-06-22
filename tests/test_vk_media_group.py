from pmi_proxy_bot.vk_message_handler import VKMessageHandler
from pmi_proxy_bot.database_manager import DatabaseManager


class DummyService:
    def __getattr__(self, name):
        def method(*args, **kwargs):
            return []

        return method


class CaptureTelegram:
    def __init__(self):
        self.chat_id = 1
        self.media_groups = []
        self.photos = []
        self.texts = []
        self.docs = []

    def send_media_group(self, media, chat_id=None):
        self.media_groups.append(media)

    def send_photo_with_caption(self, photo_url, caption, chat_id=None):
        self.photos.append((photo_url, caption))

    def send_document_with_caption(
        self, doc_url, caption, chat_id=None, file_name="file"
    ):
        self.docs.append((doc_url, caption))

    def send_text(self, text, parse_mode=None, chat_id=None):
        self.texts.append(text)


def test_forward_multiple_attachments(monkeypatch):
    class DummyLongPoll:
        def __init__(self, session, group_id):
            pass

    monkeypatch.setattr("pmi_proxy_bot.vk_message_handler.VkBotLongPoll", DummyLongPoll)
    tg = CaptureTelegram()
    handler = VKMessageHandler(DummyService(), tg, DatabaseManager(":memory:"))
    msg = {
        "text": "hello",
        "sender_name": "Alice",
        "attachments": [
            {"type": "photo", "photo": {"sizes": [{"width": 100, "url": "http://1"}]}},
            {"type": "photo", "photo": {"sizes": [{"width": 100, "url": "http://2"}]}},
        ],
    }
    handler.forward_to_telegram(msg)
    assert len(tg.media_groups) == 1
    media = tg.media_groups[0]
    assert len(media) == 2
    assert media[0]["media"] == "http://1"
    assert "hello" in media[-1]["caption"]
