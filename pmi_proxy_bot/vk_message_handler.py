import time
import logging
import hashlib
import re
import os
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from .config import TELEGRAM_BOT_NAME, TIMEZONE, vk_restart_flag
from .html_converter import HTMLConverter
from .utils import get_local_model_response


class VKMessageHandler:
    def __init__(self, vk_service, telegram_service, db_manager):
        self.vk_service = vk_service
        self.telegram_service = telegram_service
        self.db_manager = db_manager
        self.longpoll = VkBotLongPoll(self.vk_service.session, self.vk_service.group_id)

    def handle_message(self, message):
        text = message.get("text", "")
        peer_id = message.get("peer_id", message.get("from_id"))
        sender_id = message.get("from_id")
        if sender_id:
            try:
                sender_data = self.vk_service.api.users.get(user_ids=sender_id)
                if sender_data:
                    sender_info = sender_data[0]
                    message["sender_name"] = (
                        f"{sender_info['first_name']} {sender_info['last_name']}"
                    )
            except Exception as e:
                logging.error("Ошибка при получении данных отправителя: %s", e)

        if peer_id == 2000000000 + self.vk_service.chat_id:
            self.forward_to_telegram(message)

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
            self.vk_service.send_message(peer_id, help_text)
        elif text.startswith("/add_event"):
            reply = self.add_event_from_text(text)
            self.vk_service.send_message(peer_id, reply)
        elif text.startswith("/daily_schedule"):
            from .config import BotScheduler_instance

            BotScheduler_instance.send_daily_schedule_vk(peer_id)
        elif text.startswith("/list_events"):
            events = self.db_manager.get_all_events()
            if not events:
                events_text = "Событий нет."
            else:
                events_text = "Список событий:\n"
                for idx, event in enumerate(events, 1):
                    event_date = event["datetime"].strftime("%d.%m.%Y %H:%M")
                    events_text += f"{idx}. {event_date} — {event['title']}: {event['description']}\n"
            self.vk_service.send_message(peer_id, events_text)
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
                    event_to_delete = events[index - 1]
                    if self.db_manager.delete_event(event_to_delete["id"]):
                        reply = f"Событие '{event_to_delete['title']}' удалено."
                    else:
                        reply = "Ошибка при удалении события."
            self.vk_service.send_message(peer_id, reply)
        elif "@pmib221" in text:
            reply = get_local_model_response()
            self.vk_service.send_message(peer_id, reply)

    def forward_to_telegram(self, message):
        text = message.get("text", "")
        sender_name = message.get("sender_name", "Неизвестный")

        emojis = [
            "🤡",
            "👺",
            "😈",
            "👾",
            "🦀",
            "🍪",
            "🐔",
            "🌚",
            "😈",
            "👿",
            "👻",
            "💀",
            "🎅",
            "⭐",
            "🚀",
            "💃🏽",
            "🍀",
            "🐣",
            "🎮",
            "👀",
            "🫀",
            "☢️",
            "🍷",
            "🧃",
            "🎲",
            "👽",
            "🎤",
            "🎃",
            "🍻",
            "🤖",
        ]
        hashed_value = hashlib.sha256(sender_name.encode()).hexdigest()
        idx = int(hashed_value, 16) % len(emojis)
        emoji = emojis[idx]

        reply_text = ""
        reply_message = message.get("reply_message", "")
        if reply_message != "":
            cleaned_string = self.clean_string(reply_message["text"])
            if cleaned_string:
                reply_text += (
                    f"\n>> <i>от {self.clean_string(reply_message['text'])}</i>"
                )
            else:
                user = self.vk_service.get_user([reply_message["from_id"]])
                s = str(reply_message["text"]).replace("\n", "")
                if len(s) > 80:
                    s = s[:80] + "..."
                user_name = (
                    f"{user[0]['first_name']} {user[0]['last_name']}"
                    if len(user) > 0
                    else TELEGRAM_BOT_NAME
                )
                reply_text = f"\n>> <i>от <b>{user_name}</b>: " + s + "</i>"

        formatted_text = f"{emoji} {sender_name}:\n{text}{reply_text}"

        main_attachments = message.get("attachments", [])
        media_items = []
        doc_attachments = []
        wall_url = ""

        for att in main_attachments:
            att_type = att.get("type")
            if att_type == "photo":
                photo = att.get("photo", {})
                sizes = photo.get("sizes", [])
                if sizes:
                    best_size = max(sizes, key=lambda s: s.get("width", 0))
                    url = best_size.get("url")
                    if url:
                        media_items.append({"type": "photo", "media": url})
            elif att_type == "doc":
                doc = att.get("doc", {})
                url = doc.get("url")
                if url:
                    title = doc.get("title", "файл")
                    doc_attachments.append((url, title))
            elif att_type == "wall":
                wall = att.get("wall", {})
                id_val = wall.get("id")
                wall_author = wall.get("from", {})
                if wall_url:
                    wall_url += "\n"
                if wall_author.get("type") == "group":
                    wall_url += f"\nhttps://vk.com/{wall_author.get('screen_name')}?w=wall-{wall_author.get('id')}_{id_val}"
                elif wall_author.get("type") == "profile":
                    wall_url += f"\nhttps://vk.com/id{wall_author.get('id')}?w=wall{wall_author.get('id')}_{id_val}"

        if len(media_items) > 1:
            media_items[-1]["caption"] = formatted_text + wall_url
            media_items[-1]["parse_mode"] = "HTML"
            self.telegram_service.send_media_group(
                media_items, self.telegram_service.chat_id
            )
        elif len(media_items) == 1:
            item = media_items[0]
            if item["type"] == "photo":
                self.telegram_service.send_photo_with_caption(
                    item["media"],
                    formatted_text + wall_url,
                    chat_id=self.telegram_service.chat_id,
                )
            else:
                self.telegram_service.send_document_with_caption(
                    item["media"],
                    formatted_text + wall_url,
                    chat_id=self.telegram_service.chat_id,
                )
        else:
            self.telegram_service.send_text(
                formatted_text + wall_url,
                parse_mode="HTML",
                chat_id=self.telegram_service.chat_id,
            )

        for url, title in doc_attachments:
            self.telegram_service.send_document(
                url, chat_id=self.telegram_service.chat_id, file_name=title
            )

        logging.info(
            "Forwarded VK message from '%s' to Telegram chat ID %s. Text snippet: %.50s. FWD count=%d",
            sender_name,
            self.telegram_service.chat_id,
            text,
            len(main_attachments),
        )

    def clean_string(self, s):
        pattern = re.compile(
            r"^\S+ \S+.?(переслал от|переслал из)?.*: \n.+(\n>>.*)?$", re.DOTALL
        )
        if not pattern.match(s):
            return None
        s = s.split(">>")[0]
        s = s.replace("\n", " ")
        emoji_start = re.compile(
            r"^[\U0001F300-\U0001F6FF\U0001F600-\U0001F64F\U0001F1E0-\U0001F1FF]+"
        )
        s = emoji_start.sub("", s).lstrip()
        if len(s) > 80:
            s = s[:80] + "..."
        s = "<b>" + s
        s = s.replace(":", "</b>:", 1)
        return s.strip()

    def add_event_from_text(self, text):
        parts = text.split(" ", 3)
        if len(parts) < 4:
            return (
                "Неверный формат команды. Используйте: \n"
                "/add_event DD.MM.YYYY HH:MM Название события | Описание события"
            )
        date_str = parts[1] + " " + parts[2]
        try:
            event_datetime = datetime.datetime.strptime(date_str, "%d.%m.%Y %H:%M")
            event_datetime = event_datetime.replace(tzinfo=TIMEZONE)
        except Exception:
            return "Неверный формат даты/времени. Используйте формат DD.MM.YYYY HH:MM."
        rest = parts[3]
        if "|" not in rest:
            return (
                "Неверный формат команды. Используйте: \n"
                "/add_event DD.MM.YYYY HH:MM Название события | Описание события"
            )
        title, description = map(str.strip, rest.split("|", 1))
        self.db_manager.add_event(event_datetime, title, description)
        return "Событие добавлено."

    def run(self):
        logging.info("VK-бот запущен.")
        last_heartbeat = time.time()
        while True:
            if vk_restart_flag:
                logging.info("VK-бот завершает работу для перезапуска.")
                break
            try:
                for event in self.longpoll.check():
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        self.handle_message(event.message)
                if time.time() - last_heartbeat >= 60:
                    logging.info(
                        "VKMessageHandler heartbeat: No issues detected in VK polling."
                    )
                    last_heartbeat = time.time()
                time.sleep(1)
            except Exception as e:
                logging.error("Ошибка в обработчике VK-сообщений: %s", e)
                time.sleep(5)
