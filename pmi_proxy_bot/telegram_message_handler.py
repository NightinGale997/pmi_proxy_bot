import requests
import time
import logging
import hashlib
import os
import threading
from .html_converter import HTMLConverter
from .config import TIMEZONE, VK_CHAT_ID, TELEGRAM_BOT_NAME
from .utils import get_local_model_response

class TelegramMessageHandler:
    def __init__(self, telegram_service, vk_service, db_manager):
        self.telegram_service = telegram_service
        self.vk_service = vk_service
        self.db_manager = db_manager
        self.offset = None
        self.media_groups_buffer = {}
        self.media_group_timers = {}

    def handle_update(self, update):
        message = update.get("message")
        if not message:
            return
        chat_id = message["chat"]["id"]

        media_group_id = message.get("media_group_id")
        if media_group_id:
            if media_group_id not in self.media_groups_buffer:
                self.media_groups_buffer[media_group_id] = []
            self.media_groups_buffer[media_group_id].append(message)
            if media_group_id not in self.media_group_timers:
                timer = threading.Timer(1.0, self.flush_media_group, args=[media_group_id])
                timer.start()
                self.media_group_timers[media_group_id] = timer
            return

        text = message.get("text", "")
        if text.startswith("/help"):
            help_text = (
                "Доступные команды:\n"
                "/help - показать список команд\n"
                "/add_event DD.MM.YYYY HH:MM Название события | Описание события - добавить событие\n"
                "/list_events - показать список событий\n"
                "/delete_event <номер> - удалить событие\n"
                "/daily_schedule - получить расписание на сегодня и завтра\n"
                "При упоминании @pmib221 бот ответит на запрос."
            )
            self.telegram_service.send_text(help_text, chat_id=chat_id)
        elif text.startswith("/add_event"):
            reply = self.add_event_from_text(text)
            self.telegram_service.send_text(reply, chat_id=chat_id)
        elif text.startswith("/daily_schedule"):
            from .config import BotScheduler_instance
            BotScheduler_instance.send_daily_schedule_telegram(chat_id)
        elif text.startswith("/list_events"):
            events = self.db_manager.get_all_events()
            if not events:
                events_text = "Событий нет."
            else:
                events_text = "Список событий:\n"
                for idx, event in enumerate(events, 1):
                    event_date = event['datetime'].strftime("%d.%m.%Y %H:%M")
                    events_text += f"{idx}. {event_date} — {event['title']}: {event['description']}\n"
            self.telegram_service.send_text(events_text, chat_id=chat_id)
        elif text.startswith("/delete_event"):
            parts = text.split()
            if len(parts) < 2 or not parts[1].isdigit():
                reply = "Используйте: /delete_event НОМЕР_СОБЫТИЯ"
            else:
                index = int(parts[1])
                events = self.db_manager.get_all_events()
                if index < 1 or index > len(events):
                    reply = "Событие с таким номером не найдено."
                else:
                    event_to_delete = events[index-1]
                    if self.db_manager.delete_event(event_to_delete['id']):
                        reply = f"Событие '{event_to_delete['title']}' удалено."
                    else:
                        reply = "Ошибка при удалении события."
            self.telegram_service.send_text(reply, chat_id=chat_id)
        elif "@pmib221" in text:
            reply = get_local_model_response()
            self.telegram_service.send_text(reply, chat_id=chat_id)
        elif not text.startswith("/"):
            self.forward_to_vk(message)

    def forward_to_vk(self, message):
        text = message.get('text', '') or message.get('caption', '')
        if text == '' and message.get('sticker', None) is not None:
            text = message['sticker'].get('emoji', '')
        sender = message.get('from', {})
        sender_name = (sender.get('first_name', '') + " " + sender.get('last_name', '')).strip() or "Неизвестный"
        if sender.get('username'):
            profile_url = f"https://t.me/{sender['username']}"
        else:
            profile_url = f"tg://user?id={sender.get('id', '')}"
        emojis = [
            "🤡", "👺", "😈", "👾", "🦀", "🍪", "😺", "🌚", "😈", "👿",
            "👻", "💀", "🎅", "⭐", "🚀", "💃🏽", "🍀", "🐣", "🎮", "👀",
            "🫀", "☢️", "🍷", "🧃", "🎲", "👽", "🎤", "🎃", "🍻", "🤖"
        ]
        hashed_value = hashlib.sha256(sender_name.encode()).hexdigest()
        id = int(hashed_value, 16) % len(emojis)
        emoji = emojis[id]
        reply_to_message = message.get('reply_to_message', '')
        reply_to_message_str = ''
        if reply_to_message != '':
            reply_sender = reply_to_message.get('from', {})
            if reply_sender.get('username'):
                reply_profile_url = f"https://t.me/{reply_sender['username']}"
            else:
                reply_profile_url = f"tg://user?id={reply_sender.get('id', '')}"
            reply_text = reply_to_message.get('text', '') or reply_to_message.get('caption', '')
            if reply_text == '' and reply_to_message.get('sticker', None) is not None:
                reply_text = reply_to_message['sticker'].get('emoji', '')
            reply_sender_name = (reply_sender.get('first_name', '') + " " + reply_sender.get('last_name', '')).strip() or "Неизвестный"
            if reply_sender_name == TELEGRAM_BOT_NAME:
                reply_to_message_str = None
            else:
                reply_to_message_str = f"\n>> <i>от <a href=\"{reply_profile_url}\"><b>{reply_sender_name}</b></a>: {reply_text}</i>"
        combined_text = f"<a href=\"{profile_url}\">{emoji} {sender_name}</a>:\n"
        main_attachments = []
        if text:
            combined_text += text
        messages = [message]
        if message.get('media_group_id'):
            messages = self.media_groups_buffer.pop(message['media_group_id'], [message])
        media_items = []
        doc_attachments = []
        for msg in messages:
            if msg.get('media_group_id'):
                text = msg.get('caption', '')
            else:
                text = msg.get('text', '')
            if text:
                combined_text += "\n" + text
            if 'photo' in msg:
                photo_sizes = msg['photo']
                best_photo = max(photo_sizes, key=lambda p: p.get('width', 0))
                file_id = best_photo.get('file_id')
                file_path = self.telegram_service.get_telegram_file_path(file_id)
                if file_path:
                    local_file = self.telegram_service.download_telegram_file(file_path)
                    if local_file:
                        att = self.vk_service.upload_photo(local_file)
                        if att:
                            media_items.append(att)
                        try:
                            os.remove(local_file)
                        except Exception as e:
                            logging.error("Ошибка при удалении файла: %s", e)
            if 'document' in msg:
                doc = msg['document']
                file_id = doc.get('file_id')
                file_path = self.telegram_service.get_telegram_file_path(file_id)
                if file_path:
                    local_file = self.telegram_service.download_telegram_file(file_path)
                    if local_file:
                        title = doc.get('file_name', 'file')
                        att = self.vk_service.upload_document(local_file, title)
                        if att:
                            doc_attachments.append(att)
                        try:
                            os.remove(local_file)
                        except Exception as e:
                            logging.error("Ошибка при удалении файла: %s", e)
            if 'sticker' in msg:
                file_id = msg['sticker'].get('file_id')
                file_path = self.telegram_service.get_telegram_file_path(file_id)
                if file_path:
                    local_file = self.telegram_service.download_telegram_file(file_path)
                    if local_file:
                        if msg['sticker'].get('is_video', False):
                            att = self.vk_service.upload_document(local_file, file_id)
                        else:
                            att = self.vk_service.upload_photo(local_file)
                        if att:
                            media_items.append(att)
                        try:
                            os.remove(local_file)
                        except Exception as e:
                            logging.error("Ошибка при удалении файла: %s", e)
        attachments_str = ",".join(media_items + doc_attachments) if (media_items or doc_attachments) else None
        formatted_text_html = combined_text
        if reply_to_message_str is not None:
            formatted_text_html += reply_to_message_str
        plain_text, vk_format_data = HTMLConverter.convert_html_to_vk_format(formatted_text_html)
        self.vk_service.send_message(
            self.vk_service.chat_id + 2000000000,
            plain_text,
            attachment=attachments_str,
            format_data=vk_format_data)
        logging.info("Forwarded Telegram media group (id: %s) with %d messages to VK", messages[0].get("media_group_id"), len(messages))

    def add_event_from_text(self, text):
        parts = text.split(' ', 3)
        if len(parts) < 4:
            return ("Неверный формат команды. Используйте: \n"
                    "/add_event DD.MM.YYYY HH:MM Название события | Описание события")
        date_str = parts[1] + " " + parts[2]
        try:
            event_datetime = datetime.datetime.strptime(date_str, "%d.%m.%Y %H:%M")
            event_datetime = event_datetime.replace(tzinfo=TIMEZONE)
        except Exception:
            return "Неверный формат даты/времени. Используйте формат DD.MM.YYYY HH:MM."
        rest = parts[3]
        if '|' not in rest:
            return ("Неверный формат команды. Используйте: \n"
                    "/add_event DD.MM.YYYY HH:MM Название события | Описание события")
        title, description = map(str.strip, rest.split('|', 1))
        self.db_manager.add_event(event_datetime, title, description)
        return "Событие добавлено."

    def flush_media_group(self, media_group_id):
        if media_group_id in self.media_groups_buffer:
            messages = self.media_groups_buffer.pop(media_group_id)
            if media_group_id in self.media_group_timers:
                del self.media_group_timers[media_group_id]
            if messages:
                self.forward_to_vk(messages[-1])

    def run(self):
        logging.info("Telegram-бот запущен.")
        last_heartbeat = time.time()
        while True:
            try:
                url = f"{self.telegram_service.base_url}/getUpdates"
                params = {"timeout": 100}
                if self.offset:
                    params["offset"] = self.offset
                response = requests.get(url, params=params, timeout=120)
                result_json = response.json()
                if result_json.get("ok"):
                    for update in result_json.get("result", []):
                        self.offset = update["update_id"] + 1
                        self.handle_update(update)
                if time.time() - last_heartbeat >= 60:
                    logging.info("TelegramMessageHandler heartbeat: Bot is running normally.")
                    last_heartbeat = time.time()
                time.sleep(1)
            except Exception as e:
                logging.error("Ошибка при получении обновлений Telegram: %s", e)
                time.sleep(5)
