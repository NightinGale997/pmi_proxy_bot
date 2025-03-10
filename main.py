import os
import threading
import datetime
import schedule
import time
import requests
import uuid
import json
import sqlite3
import logging
from html.parser import HTMLParser
from dotenv import load_dotenv
import vk_api
import re
import hashlib
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import imaplib
import email
import email.header
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import tempfile

# Настройка логирования
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

logger.info("Логи теперь выводятся и в консоль, и записываются в файл 'logs'.")

# Загрузка переменных окружения
load_dotenv()

# --- Глобальные настройки ---
TIMEZONE = datetime.timezone(datetime.timedelta(hours=3))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_BOT_NAME = os.getenv("TELEGRAM_BOT_NAME")

VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN")
VK_CHAT_ID = int(os.getenv("VK_CHAT_ID", "2"))
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
DB_FILE = "events.db"

MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_IMAP_SERVER = os.getenv("MAIL_IMAP_SERVER", "imap.mail.ru")

SEND_SCHEDULE_TIME = os.getenv("SEND_SCHEDULE_TIME")
CHANGE_CHAT_NAME_TIME = os.getenv("CHANGE_CHAT_NAME_TIME")

vk_to_telegram_message_ids = []
telegram_to_vk_message_ids = []

weekday_map = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}

SCHEDULE_DATA = {
    "Понедельник": [],
    "Вторник": [
        {"time": "8:30", "details": "Проектирование информационных систем (Л)", "lecturer": "доцент Васильченко А.А.", "room": "4-08 А"},
        {"time": "10:10", "parity": "числитель", "details": "Проектирование информационных систем (Пр)", "lecturer": "доцент Васильченко А.А.", "room": "4-05 А"},
        {"time": "10:10", "parity": "знаменатель", "details": "Программирование в 1С (Л)", "lecturer": "старший преподаватель Солодков С.А.", "room": "4-05 А"},
        {"time": "12:00", "subgroup": "подгруппа 1", "details": "Базы данных (Лаб)", "lecturer": "старший преподаватель Хижнякова Е.В.", "room": "4-03 А"},
        {"time": "13:40", "subgroup": "подгруппа 1", "details": "Программирование в 1С (Лаб)", "lecturer": "старший преподаватель Солодков С.А.", "room": "3-02 А"},
    ],
    "Среда": [
        {"time": "13:40", "details": "Технологии программирования в Интернет (Л)", "lecturer": "доцент Овчинников С.А.", "room": "3-02 М"},
        {"time": "15:20", "details": "Технологии программирования в Интернет (Лаб)", "lecturer": "старший преподаватель Ерофеев А.А.", "room": "1-06 М"},
        {"time": "17:00", "details": "Методы оптимизации и исследование операций (Л)", "lecturer": "доцент Харитонов М.А.", "room": "3-01 А"},
        {"time": "18:40", "details": "Методы оптимизации и исследование операций (Пр)", "lecturer": "доцент Харитонов М.А.", "room": "3-01 А"},
    ],
    "Четверг": [
        {"time": "12:00", "parity": "числитель", "details": "Уравнения математической физики (Пр)", "lecturer": "доцент Чернышев И.В.", "room": "4-05 А"},
        {"time": "12:00", "parity": "знаменатель", "details": "Уравнения математической физики (Л)", "lecturer": "доцент Чернышев И.В.", "room": "4-05 А"},
        {"time": "13:40", "details": "Численные методы (Л)", "lecturer": "профессор Васильев Е.И.", "room": "4-05 А"},
        {"time": "15:20", "details": "Численные методы (Пр)", "lecturer": "профессор Васильев Е.И.", "room": "4-05 А"},
    ],
    "Пятница": [
        {"time": "12:00", "subgroup": "подгруппа 2", "details": "Базы данных (Лаб)", "lecturer": "старший преподаватель Хижнякова Е.В.", "room": "4-03 А"},
        {"time": "13:40", "subgroup": "подгруппа 2", "details": "Программирование в 1С (Лаб)", "lecturer": "старший преподаватель Солодков С.А.", "room": "3-07 А"},
    ],
    "Суббота": [
        {"time": "12:00", "details": "Прикладная физическая культура (Пр)"},
        {"time": "13:40", "details": "Базы данных (Л)", "lecturer": "доцент Григорьева Е.Г.", "room": "4-08 А"},
        {"time": "15:20", "details": "Учебная практика, научно-исследовательская работа (получение первичных навыков научно-исследовательской работы) (Пр)", "lecturer": "доцент Зенович А.В.", "room": "3-07 А"},
    ],
    "Воскресенье": []
}

vk_restart_flag = False
os.environ["PYTHONHASHSEED"] = "0"

def decode_mime_words(s):
    decoded_fragments = email.header.decode_header(s)
    return ''.join(
        fragment.decode(encoding if encoding else 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

# =======================
# КЛАСС РАБОТЫ С БД
# =======================
class DatabaseManager:
    def __init__(self, db_file):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_datetime TEXT,
                title TEXT,
                description TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def add_event(self, event_datetime, title, description):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (event_datetime, title, description) VALUES (?, ?, ?)",
            (event_datetime.isoformat(), title, description)
        )
        conn.commit()
        conn.close()

    def get_upcoming_events(self, limit=5):
        now = datetime.datetime.now(TIMEZONE).isoformat()
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, event_datetime, title, description FROM events WHERE event_datetime > ? ORDER BY event_datetime ASC LIMIT ?",
            (now, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        events = []
        for row in rows:
            event_id, event_datetime_str, title, description = row
            event_datetime = datetime.datetime.fromisoformat(event_datetime_str)
            events.append({"id": event_id, "datetime": event_datetime, "title": title, "description": description})
        return events

    def get_all_events(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT id, event_datetime, title, description FROM events ORDER BY event_datetime ASC")
        rows = cursor.fetchall()
        conn.close()
        events = []
        for row in rows:
            event_id, event_datetime_str, title, description = row
            event_datetime = datetime.datetime.fromisoformat(event_datetime_str)
            events.append({"id": event_id, "datetime": event_datetime, "title": title, "description": description})
        return events

    def delete_event(self, event_id):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        changes = conn.total_changes
        conn.commit()
        conn.close()
        return changes > 0

# =======================
# HTML-Парсер и конвертер для VK
# =======================
class VKFormatHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.plain_text = ""
        self.format_items = []
        self.tag_stack = []

    def handle_starttag(self, tag, attrs):
        if tag in ("b", "i", "u", "a"):
            if tag == "a":
                href = None
                for name, value in attrs:
                    if name == "href":
                        href = value
                        break
                self.tag_stack.append((tag, len(self.plain_text), href))
            else:
                self.tag_stack.append((tag, len(self.plain_text)))

    def handle_endtag(self, tag):
        for i in range(len(self.tag_stack) - 1, -1, -1):
            if self.tag_stack[i][0] == tag:
                if tag == "a":
                    _, start_index, href = self.tag_stack.pop(i)
                else:
                    _, start_index = self.tag_stack.pop(i)
                    href = None
                end_index = len(self.plain_text)
                length = end_index - start_index
                vk_type = {"b": "bold", "i": "italic", "u": "underline", "a": "url"}.get(tag, tag)
                format_item = {
                    "type": vk_type,
                    "offset": start_index,
                    "length": length,
                }
                if tag == "a":
                    format_item["url"] = href
                self.format_items.append(format_item)
                break

    def handle_data(self, data):
        self.plain_text += data

class HTMLConverter:
    @staticmethod
    def convert_html_to_vk_format(html_text):
        parser = VKFormatHTMLParser()
        parser.feed(html_text)
        plain_text = parser.plain_text
        format_data = {"version": "1", "items": parser.format_items}
        return plain_text, json.dumps(format_data)

# =======================
# Telegram-сервис
# =======================
class TelegramService:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_text(self, text, parse_mode=None, chat_id=None):
        chat = chat_id or self.chat_id
        url = f"{self.base_url}/sendMessage"
        data = {"chat_id": chat, "text": text}
        if parse_mode:
            data["parse_mode"] = parse_mode
        try:
            requests.post(url, data=data)
        except Exception as e:
            logging.error("Ошибка при отправке текста в Telegram: %s", e)

    def send_photo(self, photo_url, chat_id=None):
        chat = chat_id or self.chat_id
        try:
            response = requests.get(photo_url)
            if response.status_code == 200:
                files = {'photo': ('image.jpg', response.content)}
                data = {'chat_id': chat}
                url = f"{self.base_url}/sendPhoto"
                requests.post(url, data=data, files=files)
        except Exception as e:
            logging.error("Ошибка при отправке фото в Telegram: %s", e)

    def send_document(self, doc_url, chat_id=None, file_name="file"):
        chat = chat_id or self.chat_id
        try:
            response = requests.get(doc_url)
            if response.status_code == 200:
                files = {'document': (file_name, response.content)}
                data = {'chat_id': chat}
                url = f"{self.base_url}/sendDocument"
                requests.post(url, data=data, files=files)
        except Exception as e:
            logging.error("Ошибка при отправке документа в Telegram: %s", e)

    def send_photo_with_caption(self, photo_url, caption, chat_id=None):
        chat = chat_id or self.chat_id
        try:
            response = requests.get(photo_url)
            if response.status_code == 200:
                files = {'photo': ('image.jpg', response.content)}
                data = {'chat_id': chat, 'caption': caption, 'parse_mode': 'HTML'}
                url = f"{self.base_url}/sendPhoto"
                requests.post(url, data=data, files=files)
        except Exception as e:
            logging.error("Ошибка при отправке фото с подписью в Telegram: %s", e)

    def send_document_with_caption(self, doc_url, caption, chat_id=None, file_name="file"):
        chat = chat_id or self.chat_id
        try:
            response = requests.get(doc_url)
            if response.status_code == 200:
                files = {'document': (file_name, response.content)}
                data = {'chat_id': chat, 'caption': caption, 'parse_mode': 'HTML'}
                url = f"{self.base_url}/sendDocument"
                requests.post(url, data=data, files=files)
        except Exception as e:
            logging.error("Ошибка при отправке документа с подписью в Telegram: %s", e)

    def send_photo_file(self, image_path, chat_id=None):
        chat = chat_id or self.chat_id
        try:
            with open(image_path, 'rb') as f:
                files = {'photo': f}
                data = {'chat_id': chat}
                url = f"{self.base_url}/sendPhoto"
                requests.post(url, data=data, files=files)
        except Exception as e:
            logging.error("Ошибка при отправке фото (файл) в Telegram: %s", e)

    def send_document_file(self, file_path, chat_id=None, file_name=None):
        chat = chat_id or self.chat_id
        try:
            with open(file_path, 'rb') as f:
                files = {'document': (file_name or os.path.basename(file_path), f)}
                data = {'chat_id': chat}
                url = f"{self.base_url}/sendDocument"
                requests.post(url, data=data, files=files)
        except Exception as e:
            logging.error("Ошибка при отправке документа (файл) в Telegram: %s", e)

    def get_telegram_file_path(self, file_id):
        try:
            url = f"{self.base_url}/getFile"
            params = {"file_id": file_id}
            response = requests.get(url, params=params)
            result = response.json()
            if result.get("ok"):
                return result["result"]["file_path"]
        except Exception as e:
            logging.error("Ошибка при получении пути файла Telegram: %s", e)
        return None

    def send_media_group(self, media, chat_id=None):
        chat = chat_id or self.chat_id
        url = f"{self.base_url}/sendMediaGroup"
        data = {"chat_id": chat, "media": json.dumps(media)}
        try:
            requests.post(url, data=data)
        except Exception as e:
            logging.error("Ошибка при отправке медиа группы в Telegram: %s", e)

    def download_telegram_file(self, file_path):
        try:
            file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            response = requests.get(file_url)
            if response.status_code == 200:
                local_filename = str(uuid.uuid4()) + "_" + os.path.basename(file_path)
                with open(local_filename, 'wb') as f:
                    f.write(response.content)
                return local_filename
        except Exception as e:
            logging.error("Ошибка при загрузке файла Telegram: %s", e)
        return None

# =======================
# VK-сервис
# =======================
class VKService:
    def __init__(self, access_token, group_id, chat_id):
        self.access_token = access_token
        self.group_id = group_id
        self.chat_id = chat_id
        self.session = vk_api.VkApi(token=self.access_token)
        self.api = self.session.get_api()

    def send_message(self, peer_id, message, attachment=None, format_data=None, chat_id=None):
        try:
            self.api.messages.send(
                peer_id=peer_id,
                chat_id=chat_id,
                message=message,
                attachment=attachment,
                format_data=format_data,
                random_id=0
            )
        except Exception as e:
            logging.error("Ошибка при отправке сообщения в VK: %s", e)
    
    def get_user(self, user_id):
        try:
            return self.api.users.get(
                user_id=user_id,
                field="screen_name"
            )
        except Exception as e:
            logging.error("Ошибка при отправке сообщения в VK: %s", e)

    def edit_chat_title(self, chat_id, title):
        try:
            self.api.messages.editChat(chat_id=chat_id, title=title)
        except Exception as e:
            logging.error("Ошибка при изменении названия чата в VK: %s", e)

    def upload_photo(self, image_path):
        try:
            upload = vk_api.VkUpload(self.session)
            photo = upload.photo_messages(image_path)[0]
            return f"photo{photo['owner_id']}_{photo['id']}"
        except Exception as e:
            logging.error("Ошибка при загрузке фото в VK: %s", e)
            return None

    def upload_document(self, file_path, title="file"):
        try:
            upload = vk_api.VkUpload(self.session)
            doc = upload.document_message(file_path, peer_id=self.chat_id + 2000000000, title=title)['doc']
            return f"doc{doc['owner_id']}_{doc['id']}"
        except Exception as e:
            logging.error("Ошибка при загрузке документа в VK: %s", e)
            return None

# =======================
# Менеджер расписания и генерации изображения
# =======================
class ScheduleManager:
    def __init__(self, schedule_data, db_manager):
        self.schedule_data = schedule_data
        self.db_manager = db_manager

    @staticmethod
    def calculate_week_parity():
        # Задаём начальную неделю (пример)
        start_date = datetime.datetime(2024, 9, 30, tzinfo=TIMEZONE)
        now = datetime.datetime.now(TIMEZONE)
        current_week_start = now - datetime.timedelta(days=now.weekday())
        weeks_passed = (current_week_start - start_date).days // 7
        return "Числитель" if weeks_passed % 2 == 0 else "Знаменатель"

    def generate_schedule_image(self, today_name, today_schedule, tomorrow_name, tomorrow_schedule, week_parity, events):
        gradient_classes = {
            "Понедельник": "bg-gradient-to-br from-blue-50 to-indigo-50",
            "Вторник": "bg-gradient-to-br from-pink-50 to-red-50",
            "Среда": "bg-gradient-to-br from-green-50 to-emerald-50",
            "Четверг": "bg-gradient-to-br from-yellow-50 to-amber-50",
            "Пятница": "bg-gradient-to-br from-indigo-50 to-sky-50",
            "Суббота": "bg-gradient-to-br from-teal-50 to-green-50",
            "Воскресенье": "bg-gradient-to-br from-gray-50 to-gray-100"
        }
        today_gradient = gradient_classes.get(today_name, "bg-white")
        tomorrow_gradient = gradient_classes.get(tomorrow_name, "bg-white")
        html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Расписание на {today_name} и {tomorrow_name} ({week_parity})</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-r from-indigo-100 to-purple-100 py-8">
  <div class="max-w-5xl mx-auto">
    <h1 class="text-4xl font-bold text-center mb-6 text-purple-700">
      Расписание на {today_name} и {tomorrow_name} ({week_parity})
    </h1>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Сегодня -->
      <div class="border p-4 rounded-lg {today_gradient} shadow-lg">
        <h2 class="text-2xl font-semibold text-center mb-4">Сегодня ({today_name})</h2>
'''
        if not today_schedule:
            html += '<p class="text-center text-gray-600 italic">Нет пар</p>'
        else:
            for pair in today_schedule:
                time_str = pair.get('time', '')
                details = pair.get('details', '')
                lecturer = pair.get('lecturer', '')
                room = pair.get('room', '')
                subgroup = pair.get('subgroup', '')
                parity = pair.get('parity', '')
                if parity and parity.lower() != week_parity.lower():
                    continue
                html += '<div class="mb-3">'
                html += f'  <div class="flex justify-between font-semibold text-purple-700">'
                html += f'    <span>{time_str}</span>'
                if room:
                    html += f'    <span class="text-sm text-gray-500">{room}</span>'
                html += '  </div>'
                html += f'  <p class="text-gray-700">{details}</p>'
                if lecturer:
                    html += '  <p class="text-xs text-gray-500">'
                    html += f'{lecturer}'
                    if subgroup:
                        html += f' <span class="ml-1 bg-blue-200 text-blue-800 px-1 rounded">{subgroup}</span>'
                    html += '</p>'
                html += '</div>'
        html += f'''
      </div>
      <!-- Завтра -->
      <div class="border p-4 rounded-lg {tomorrow_gradient} shadow-lg">
        <h2 class="text-2xl font-semibold text-center mb-4">Завтра ({tomorrow_name})</h2>
'''
        if not tomorrow_schedule:
            html += '<p class="text-center text-gray-600 italic">Нет пар</p>'
        else:
            for pair in tomorrow_schedule:
                time_str = pair.get('time', '')
                details = pair.get('details', '')
                lecturer = pair.get('lecturer', '')
                room = pair.get('room', '')
                subgroup = pair.get('subgroup', '')
                parity = pair.get('parity', '')
                if parity and parity.lower() != week_parity.lower():
                    continue
                html += '<div class="mb-3">'
                html += f'  <div class="flex justify-between font-semibold text-purple-700">'
                html += f'    <span>{time_str}</span>'
                if room:
                    html += f'    <span class="text-sm text-gray-500">{room}</span>'
                html += '  </div>'
                html += f'  <p class="text-gray-700">{details}</p>'
                if lecturer:
                    html += '  <p class="text-xs text-gray-500">'
                    html += f'{lecturer}'
                    if subgroup:
                        html += f' <span class="ml-1 bg-blue-200 text-blue-800 px-1 rounded">{subgroup}</span>'
                    html += '</p>'
                html += '</div>'
        html += '''
      </div>
    </div>
    <!-- Ближайшие события -->
    <div class="mt-8 border p-4 rounded-lg bg-white shadow-lg">
      <h2 class="text-2xl font-semibold text-center mb-4">Ближайшие события</h2>
'''
        if events:
            for event in events:
                event_date = event['datetime'].strftime("%d.%m.%Y %H:%M")
                html += f'''<div class="mb-2">
  <strong class="text-purple-700">{event_date}</strong> — <em class="text-gray-700">{event["title"]}</em>: {event["description"]}
</div>'''
        else:
            html += '<p class="text-center text-gray-600 italic">Событий нет.</p>'
        html += '''
    </div>
  </div>
</body>
</html>
'''

        # Сохраняем HTML во временный файл
        temp_html_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
        temp_html_file.write(html.encode('utf-8'))
        temp_html_file.close()

        # Настройка Selenium (Chrome headless)
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument("--user-data-dir=/tmp/chrome-temp-profile")
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_window_size(1100, 860)  # При необходимости увеличьте высоту
        driver.get("file://" + temp_html_file.name)

        output_file = "schedule.png"
        driver.save_screenshot(output_file)

        driver.quit()
        os.remove(temp_html_file.name)
        return output_file

# =======================
# Менеджер периодических задач (расписание, перезапуск ВК-бота)
# =======================
class BotScheduler:
    def __init__(self, vk_service, telegram_service, schedule_manager):
        self.vk_service = vk_service
        self.telegram_service = telegram_service
        self.schedule_manager = schedule_manager

    def send_daily_schedule_vk(self, peer_id):
        try:
            now = datetime.datetime.now(TIMEZONE)
            today_weekday = now.weekday()
            today_name = weekday_map.get(today_weekday, "Неизвестный день")
            tomorrow_time = now + datetime.timedelta(days=1)
            tomorrow_weekday = tomorrow_time.weekday()
            tomorrow_name = weekday_map.get(tomorrow_weekday, "Неизвестный день")
            week_parity = self.schedule_manager.calculate_week_parity()
            today_schedule = self.schedule_manager.schedule_data.get(today_name, [])
            tomorrow_schedule = self.schedule_manager.schedule_data.get(tomorrow_name, [])
            upcoming_events = self.schedule_manager.db_manager.get_upcoming_events()
            
            image_path = self.schedule_manager.generate_schedule_image(
                today_name, today_schedule, tomorrow_name, tomorrow_schedule, week_parity, upcoming_events
            )
            attachment = self.vk_service.upload_photo(image_path)
            message = "Расписание и ближайшие события"
            if peer_id == self.vk_service.chat_id or peer_id == self.vk_service.chat_id + 2000000000:
                self.vk_service.send_message(None, message, attachment=attachment, chat_id=self.vk_service.chat_id)
            else:
                self.vk_service.send_message(peer_id, message, attachment=attachment)
            logging.info("Расписание отправлено в VK.")
        except Exception as e:
            logging.error("Ошибка при отправке расписания в VK: %s", e)

    def send_daily_schedule_telegram(self, chat_id):
        try:
            now = datetime.datetime.now(TIMEZONE)
            today_weekday = now.weekday()
            today_name = weekday_map.get(today_weekday, "Неизвестный день")
            tomorrow_time = now + datetime.timedelta(days=1)
            tomorrow_weekday = tomorrow_time.weekday()
            tomorrow_name = weekday_map.get(tomorrow_weekday, "Неизвестный день")
            week_parity = self.schedule_manager.calculate_week_parity()
            today_schedule = self.schedule_manager.schedule_data.get(today_name, [])
            tomorrow_schedule = self.schedule_manager.schedule_data.get(tomorrow_name, [])
            upcoming_events = self.schedule_manager.db_manager.get_upcoming_events()
            
            image_path = self.schedule_manager.generate_schedule_image(
                today_name, today_schedule, tomorrow_name, tomorrow_schedule, week_parity, upcoming_events
            )
            self.telegram_service.send_text("Расписание и ближайшие события", chat_id=chat_id)
            self.telegram_service.send_photo_file(image_path, chat_id)
            logging.info("Расписание отправлено в Telegram.")
        except Exception as e:
            logging.error("Ошибка при отправке расписания в Telegram: %s", e)

    def send_daily_schedule(self):
        self.send_daily_schedule_vk(self.vk_service.chat_id)
        self.send_daily_schedule_telegram(self.telegram_service.chat_id)

    def scheduled_weekly_job(self):
        week_parity = self.schedule_manager.calculate_week_parity()
        new_title = f"ПМИб-221 ({week_parity})"
        self.vk_service.edit_chat_title(self.vk_service.chat_id, new_title)
        logging.info("Название беседы изменено на '%s'", new_title)

    def request_vk_restart(self):
        global vk_restart_flag
        logging.info("Запрошен перезапуск ВК-бота (00:00).")
        vk_restart_flag = True

    def run(self):
        schedule.every().monday.at(CHANGE_CHAT_NAME_TIME).do(self.scheduled_weekly_job)
        schedule.every().day.at(SEND_SCHEDULE_TIME).do(self.send_daily_schedule)
        last_heartbeat = time.time()
        while True:
            schedule.run_pending()
            if time.time() - last_heartbeat >= 60:
                logging.info("Scheduler heartbeat: Scheduler is running normally.")
                last_heartbeat = time.time()
            time.sleep(1)

# =======================
# Обработчик сообщений ВК
# =======================
class VKMessageHandler:
    def __init__(self, vk_service, telegram_service, db_manager):
        self.vk_service = vk_service
        self.telegram_service = telegram_service
        self.db_manager = db_manager
        self.longpoll = VkBotLongPoll(self.vk_service.session, self.vk_service.group_id)

    def handle_message(self, message):
        text = message.get('text', '')
        peer_id = message.get('peer_id', message.get('from_id'))
        sender_id = message.get('from_id')
        if sender_id:
            try:
                sender_data = self.vk_service.api.users.get(user_ids=sender_id)
                if sender_data:
                    sender_info = sender_data[0]
                    message['sender_name'] = f"{sender_info['first_name']} {sender_info['last_name']}"
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
            BotScheduler_instance.send_daily_schedule_vk(peer_id)
        elif text.startswith("/list_events"):
            events = self.db_manager.get_all_events()
            if not events:
                events_text = "Событий нет."
            else:
                events_text = "Список событий:\n"
                for idx, event in enumerate(events, 1):
                    event_date = event['datetime'].strftime("%d.%m.%Y %H:%M")
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
                    event_to_delete = events[index-1]
                    if self.db_manager.delete_event(event_to_delete['id']):
                        reply = f"Событие '{event_to_delete['title']}' удалено."
                    else:
                        reply = "Ошибка при удалении события."
            self.vk_service.send_message(peer_id, reply)
        elif '@pmib221' in text:
            reply = get_local_model_response()
            self.vk_service.send_message(peer_id, reply)

    def forward_to_telegram(self, message):
        text = message.get('text', '')
        sender_name = message.get('sender_name', 'Неизвестный')

        # Вычислим эмодзи для автора основного сообщения
        emojis = [
            "🤡", "👺", "😈", "👾", "🦀", "🍪", "🐔", "🌚", "😈", "👿",
            "👻", "💀", "🎅", "⭐", "🚀", "💃🏽", "🍀", "🐣", "🎮", "👀",
            "🫀", "☢️", "🍷", "🧃", "🎲", "👽", "🎤", "🎃", "🍻", "🤖"
        ]
        hashed_value = hashlib.sha256(sender_name.encode()).hexdigest()
        idx = int(hashed_value, 16) % len(emojis)
        emoji = emojis[idx]

        # --- 1) Готовим и отправляем "основное" сообщение (если есть) ---
        reply_text = ''
        reply_message = message.get('reply_message', '')
        if reply_message != '':
            cleaned_string = self.clean_string(reply_message['text'])
            if cleaned_string:
                reply_text += f"\n>> <i>от {self.clean_string(reply_message['text'])}</i>"
            else:
                user = self.vk_service.get_user([reply_message['from_id']])
                s = str(reply_message['text']).replace('\n', '')
                if len(s) > 80:
                    s = s[:80] + '...'
                user_name = f"{user[0]['first_name']} {user[0]['last_name']}" if len(user) > 0 else TELEGRAM_BOT_NAME
                reply_text = f"\n>> <i>от <b>{user_name}</b>: " + s + "</i>"

        formatted_text = f"{emoji} {sender_name}:\n{text}{reply_text}"

        # Вложения основного сообщения
        main_attachments = message.get('attachments', [])
        media_items = []
        doc_attachments = []
        wall_url = ""  # если есть прикреплённая ссылка на пост VK (type=wall), дописываем её

        # Сюда вставьте вашу логику обхода main_attachments (photo, doc, sticker, wall и т.д.)
        # и заполните media_items, doc_attachments, wall_url. 
        # ---------------------------------------
        # Пример:
        for att in main_attachments:
            att_type = att.get('type')
            if att_type == "photo":
                photo = att.get('photo', {})
                sizes = photo.get('sizes', [])
                if sizes:
                    best_size = max(sizes, key=lambda s: s.get('width', 0))
                    url = best_size.get('url')
                    if url:
                        media_items.append({"type": "photo", "media": url})
            elif att_type == "doc":
                doc = att.get('doc', {})
                url = doc.get('url')
                if url:
                    title = doc.get('title', 'файл')
                    doc_attachments.append((url, title))
            elif att_type == "sticker":
                photo = att.get('sticker', {})
                sizes = photo.get('images', [])
                if sizes:
                    best_size = max(sizes, key=lambda s: s.get('width', 0) if s.get('width', 0) < 300 else 0)
                    url = best_size.get('url')
                    if url:
                        media_items.append({"type": "photo", "media": url})
            elif att_type == 'wall':
                wall = att.get('wall', {})
                id = wall.get('id')
                wall_author = wall.get('from', {})
                
                if text:
                    wall_url = '\n'

                if wall_author['type'] == 'group':
                    wall_url += f"\nhttps://vk.com/{wall_author['screen_name']}?w=wall-{wall_author['id']}_{id}"
                elif wall_author['type'] == 'profile':
                    wall_url += f"\nhttps://vk.com/id{wall_author['id']}?w=wall{wall_author['id']}_{id}"

        # Если есть фото/стикеры – отправляем "медиа-группу":
        if media_items:
            media_items[0]["caption"] = formatted_text + wall_url
            media_items[0]["parse_mode"] = "HTML"
            self.telegram_service.send_media_group(media_items, self.telegram_service.chat_id)
        else:
            # Иначе просто текст
            self.telegram_service.send_text(formatted_text + wall_url,
                                            parse_mode="HTML",
                                            chat_id=self.telegram_service.chat_id)
        # Документы отправляем отдельно
        for url, title in doc_attachments:
            self.telegram_service.send_document(url,
                                                chat_id=self.telegram_service.chat_id,
                                                file_name=title)

        # --- 2) Теперь обрабатываем пересланные сообщения по отдельности ---
        fwd_messages = message.get('fwd_messages', [])
        for fwd in fwd_messages:
            # Выясняем, от кого пришло исходно
            fwd_sender = self.vk_service.get_user([fwd['from_id']]) if fwd.get('from_id') else None
            if fwd_sender:
                fwd_sender_name = f"{fwd_sender[0].get('first_name','?')} {fwd_sender[0].get('last_name','?')}"
            else:
                fwd_sender_name = TELEGRAM_BOT_NAME

            # Текст пересланного сообщения
            fwd_text = fwd.get('text', '')

            # Добавим метку:
            #   - "кто переслал" -> это всё ещё sender_name (т.к. он «принёс» этот fwd_message)
            #   - "Пересланно от {fwd_sender_name}"
            fwd_formatted_text = (
                f"{emoji} {sender_name}:\n"  # укажем, кто переслал
                f"<i>Пересланно от </i><b>{fwd_sender_name}</b>\n"
                f"{fwd_text}"
            )

            # Собираем вложения для каждого пересланного сообщения
            fwd_attachments = fwd.get('attachments', [])
            fwd_media_items = []
            fwd_doc_attachments = []
            fwd_wall_url = ""

            for att in fwd_attachments:
                att_type = att.get('type')
                if att_type == "photo":
                    photo = att.get('photo', {})
                    sizes = photo.get('sizes', [])
                    if sizes:
                        best_size = max(sizes, key=lambda s: s.get('width', 0))
                        url = best_size.get('url')
                        if url:
                            fwd_media_items.append({
                                "type": "photo",
                                "media": url
                            })
                elif att_type == "sticker":
                    sticker = att.get('sticker', {})
                    sizes = sticker.get('images', [])
                    if sizes:
                        best_size = max(sizes, key=lambda s: s.get('width', 0) if s.get('width', 0) < 300 else 0)
                        url = best_size.get('url')
                        if url:
                            fwd_media_items.append({
                                "type": "photo",
                                "media": url
                            })
                elif att_type == "doc":
                    doc = att.get('doc', {})
                    url = doc.get('url')
                    if url:
                        title = doc.get('title', 'файл')
                        fwd_doc_attachments.append((url, title))
                elif att_type == 'wall':
                    wall = att.get('wall', {})
                    id_val = wall.get('id')
                    wall_author = wall.get('from', {})
                    if fwd_text:
                        fwd_wall_url = "\n"
                    if wall_author.get('type') == 'group':
                        fwd_wall_url += f"\nhttps://vk.com/{wall_author.get('screen_name')}?w=wall-{wall_author.get('id')}_{id_val}"
                    elif wall_author.get('type') == 'profile':
                        fwd_wall_url += f"\nhttps://vk.com/id{wall_author.get('id')}?w=wall{wall_author.get('id')}_{id_val}"

            # Отправляем пересланное сообщение отдельно
            if fwd_media_items:
                fwd_media_items[0]["caption"] = fwd_formatted_text + fwd_wall_url
                fwd_media_items[0]["parse_mode"] = "HTML"
                self.telegram_service.send_media_group(fwd_media_items, self.telegram_service.chat_id)
            else:
                self.telegram_service.send_text(fwd_formatted_text + fwd_wall_url,
                                                parse_mode="HTML",
                                                chat_id=self.telegram_service.chat_id)

            # Отправим документы пересланного сообщения
            for url, title in fwd_doc_attachments:
                self.telegram_service.send_document(url,
                                                    chat_id=self.telegram_service.chat_id,
                                                    file_name=title)

        logging.info(
            "Forwarded VK message from '%s' to Telegram chat ID %s. Text snippet: %.50s. "
            "FWD count=%d",
            sender_name,
            self.telegram_service.chat_id,
            text,
            len(fwd_messages)
        )


    def clean_string(self, s):
        pattern = re.compile(r'^\S+ \S+.?(переслал от|переслал из)?.*: \n.+(\n>>.*)?$', re.DOTALL)
        if not pattern.match(s):
            return None
        s = s.split(">>")[0]
        s = s.replace("\n", " ")
        emoji_start = re.compile(r'^[\U0001F300-\U0001F6FF\U0001F600-\U0001F64F\U0001F1E0-\U0001F1FF]+')
        s = emoji_start.sub("", s).lstrip()
        if len(s) > 80:
            s = s[:80] + '...'
        s = '<b>' + s
        s = s.replace(':', '</b>:', 1)
        return s.strip()

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
                    logging.info("VKMessageHandler heartbeat: No issues detected in VK polling.")
                    last_heartbeat = time.time()
                time.sleep(1)
            except Exception as e:
                logging.error("Ошибка в обработчике VK-сообщений: %s", e)
                time.sleep(5)

# =======================
# Обработчик сообщений Telegram
# =======================
class TelegramMessageHandler:
    def __init__(self, telegram_service, vk_service, db_manager):
        self.telegram_service = telegram_service
        self.vk_service = vk_service
        self.db_manager = db_manager
        self.offset = None
        # Буфер для сообщений, принадлежащих медиа-группе: {media_group_id: [message1, message2, ...]}
        self.media_groups_buffer = {}
        # Словарь для хранения таймеров, чтобы по истечении задержки объединить сообщения
        self.media_group_timers = {}
        

    def handle_update(self, update):
        message = update.get("message")
        if not message:
            return
        chat_id = message["chat"]["id"]

        # Если сообщение входит в медиа-группу, накапливаем его в буфере
        media_group_id = message.get("media_group_id")
        if media_group_id:
            if media_group_id not in self.media_groups_buffer:
                self.media_groups_buffer[media_group_id] = []
            self.media_groups_buffer[media_group_id].append(message)
            # Если для этой медиа-группы ещё не установлен таймер, устанавливаем его
            if media_group_id not in self.media_group_timers:
                timer = threading.Timer(1.0, self.flush_media_group, args=[media_group_id])
                timer.start()
                self.media_group_timers[media_group_id] = timer
            return

        # Если сообщение не является частью медиа-группы, обрабатываем его как обычно
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
            # Если сообщение не является командой, перенаправляем его в ВК
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
            forward_text = self.get_forward_text(reply_to_message)
            if len(reply_text) > 80:
                reply_text = reply_text[:80] + '...'
            if forward_text != '':
                reply_to_message_str = "\n>> " + forward_text + f"{reply_text}"
            elif reply_sender_name == TELEGRAM_BOT_NAME:
                reply_to_message_str = "\n>> <i>от " + self.clean_string(reply_text) + "</i>"
            else:
                reply_to_message_str = f"\n>> <i>от <a href=\"{reply_profile_url}\">{reply_sender_name}:</a> {reply_text} </i>"
        forward_from_chat = message.get('forward_from_chat', '')
        forward_from = message.get('forward_from', '')
        forward_text = ''
        if forward_from_chat != '':
            forward_signature = message.get('forward_signature', '')
            if forward_signature != '':
                forward_text = f"переслал из <b>{forward_from_chat['title']} </b>"
                forward_text += f'({forward_signature}):'
            else:
                forward_text = f"переслал из <b>{forward_from_chat['title']}: </b>"
            formatted_text_html = (
                f"<a href=\"{profile_url}\">{emoji} {sender_name} </a>{forward_text}\n"
                f"{text}"
            )
        elif forward_from != '':
            forward_title = (forward_from.get('first_name', '') + " " + forward_from.get('last_name', '')).strip() or "Неизвестный"
            forward_text = f"переслал от <b>{forward_title}: </b>"
            formatted_text_html = (
                f"<a href=\"{profile_url}\">{emoji} {sender_name} </a>{forward_text}\n"
                f"{text}"
            )
        else:
            formatted_text_html = (
                f"<a href=\"{profile_url}\">{emoji} {sender_name}: </a>\n"
                f"{text}"
            )
        if reply_to_message_str is not None:
            formatted_text_html += reply_to_message_str
        plain_text, vk_format_data = HTMLConverter.convert_html_to_vk_format(formatted_text_html)
        attachments = []
        if 'photo' in message:
            photo_sizes = message['photo']
            best_photo = max(photo_sizes, key=lambda p: p.get('width', 0))
            file_id = best_photo.get('file_id')
            file_path = self.telegram_service.get_telegram_file_path(file_id)
            if file_path:
                local_file = self.telegram_service.download_telegram_file(file_path)
                if local_file:
                    att = self.vk_service.upload_photo(local_file)
                    if att:
                        attachments.append(att)
                    os.remove(local_file)
        if 'document' in message:
            doc = message['document']
            file_id = doc.get('file_id')
            file_path = self.telegram_service.get_telegram_file_path(file_id)
            if file_path:
                local_file = self.telegram_service.download_telegram_file(file_path)
                if local_file:
                    title = doc.get('file_name', 'file')
                    att = self.vk_service.upload_document(local_file, title)
                    if att:
                        attachments.append(att)
                    os.remove(local_file)
        if 'sticker' in message:
            file_id = message['sticker']['file_id']
            file_path = self.telegram_service.get_telegram_file_path(file_id)
            if file_path:
                local_file = self.telegram_service.download_telegram_file(file_path)
                if local_file:
                    if message['sticker'].get('is_video', False) == True:
                        att = self.vk_service.upload_document(local_file, file_id)
                    else:
                        att = self.vk_service.upload_photo(local_file)
                    if att:
                        attachments.append(att)
                    os.remove(local_file)
        attachments_str = ",".join(attachments) if attachments else None
        if text == '' and attachments_str is None:
            return
        self.vk_service.send_message(self.vk_service.chat_id + 2000000000,
                                     plain_text,
                                     attachment=attachments_str,
                                     format_data=vk_format_data)
        logging.info("Forwarded Telegram message from '%s' to VK chat ID %s. Text snippet: %.50s. Attachments: %s",
                     sender_name, self.vk_service.chat_id, text, attachments_str)

    def get_forward_text(self, message):
        forward_from_chat = message.get('forward_from_chat', '')
        forward_from = message.get('forward_from', '')
        forward_text = ''
        if forward_from_chat != '':
            forward_signature = message.get('forward_signature', '')
            if forward_signature != '':
                forward_text = f"из <b>{forward_from_chat['title']} </b>"
                forward_text += f'({forward_signature}):'
            else:
                forward_text = f"из <b>{forward_from_chat['title']}: </b>"
            return forward_text
        elif forward_from != '':
            forward_title = (forward_from.get('first_name', '') + " " + forward_from.get('last_name', '')).strip() or "Неизвестный"
            forward_text = f"<i>от <b>{forward_title}: </b></i>"
        return forward_text

    def clean_string(self, s):
        pattern = re.compile(r'^\S+ \S+.?.*:\n.+(\n>>.*)?$', re.DOTALL)
        if not pattern.match(s):
            return None
        s = s.split(">>")[0]
        s = s.replace("\n", " ")
        emoji_start = re.compile(r'^[\U0001F300-\U0001F6FF\U0001F600-\U0001F64F\U0001F1E0-\U0001F1FF]+')
        s = emoji_start.sub("", s).lstrip()
        if len(s) > 80:
            s = s[:80] + '...'
        s = '<b>' + s
        s = s.replace(':', '</b>:', 1)
        return s.strip()

    def flush_media_group(self, media_group_id):
        # Извлекаем все накопленные сообщения с данным media_group_id
        messages = self.media_groups_buffer.pop(media_group_id, [])
        if media_group_id in self.media_group_timers:
            del self.media_group_timers[media_group_id]
        if not messages:
            return
        # Объединяем сообщения и отправляем одно сообщение в ВК
        self.forward_media_group_to_vk(messages)

    def forward_media_group_to_vk(self, messages):
        """
        Объединяет тексты и вложения всех сообщений из медиа-группы и отправляет их одним сообщением в ВК.
        """
        combined_text = ""
        media_items = []      # список для фото и стикеров (для которых можно объединить вложения)
        doc_attachments = []  # документы отправляем отдельно, так как их нельзя объединить в медиа группу
        # Используем данные отправителя из первого сообщения
        first_msg = messages[0]
        sender = first_msg.get('from', {})
        if sender.get('username'):
            profile_url = f"https://t.me/{sender['username']}"
        else:
            profile_url = f"tg://user?id={sender.get('id', '')}"
        emojis = [
            "🤡", "👺", "😈", "👾", "🦀", "🍪", "😺", "🌚", "😈", "👿",
            "👻", "💀", "🎅", "⭐", "🚀", "💃🏽", "🍀", "🐣", "🎮", "👀",
            "🫀", "☢️", "🍷", "🧃", "🎲", "👽", "🎤", "🎃", "🍻", "🤖"
        ]
        sender_name = (sender.get('first_name', '') + " " + sender.get('last_name', '')).strip() or "Неизвестный"
        hashed_value = hashlib.sha256(sender_name.encode()).hexdigest()
        id = int(hashed_value, 16) % len(emojis)
        emoji = emojis[id]
        reply_to_message = first_msg.get('reply_to_message', '')
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
            forward_text = self.get_forward_text(reply_to_message)
            if len(reply_text) > 80:
                reply_text = reply_text[:80] + '...'
            if forward_text != '':
                reply_to_message_str = "\n>> " + forward_text + f"{reply_text}"
            elif reply_sender_name == TELEGRAM_BOT_NAME:
                reply_to_message_str = "\n>> <i>от " + self.clean_string(reply_text) + "</i>"
            else:
                reply_to_message_str = f"\n>> <i>от <a href=\"{reply_profile_url}\">{reply_sender_name}:</a> {reply_text} </i>"

        forward_from_chat = first_msg.get('forward_from_chat', '')
        forward_from = first_msg.get('forward_from', '')
        forward_text = ''
        if forward_from_chat != '':
            forward_signature = first_msg.get('forward_signature', '')
            if forward_signature != '':
                forward_text = f"переслал из <b>{forward_from_chat['title']} </b>"
                forward_text += f'({forward_signature}):'
            else:
                forward_text = f"переслал из <b>{forward_from_chat['title']}: </b>"
            formatted_text_html = (
                f"<a href=\"{profile_url}\">{emoji} {sender_name} </a>{forward_text}\n"
            )
        elif forward_from != '':
            forward_title = (forward_from.get('first_name', '') + " " + forward_from.get('last_name', '')).strip() or "Неизвестный"
            forward_text = f"переслал от <b>{forward_title}: </b>"
            formatted_text_html = (
                f"<a href=\"{profile_url}\">{emoji} {sender_name} </a>{forward_text}\n"
            )
        else:
            formatted_text_html = (
                f"<a href=\"{profile_url}\">{emoji} {sender_name}: </a>\n"
            )

        # Обходим все сообщения медиа-группы
        for msg in messages:
            msg_text = msg.get("text", "") or msg.get("caption", "")
            if msg_text:
                combined_text += msg_text + "\n"

            # Обработка фото (если присутствует поле "photo")
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
            # Обработка документов
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
            # Обработка стикеров
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

        # Формируем итоговое сообщение для ВК
        attachments_str = ",".join(media_items + doc_attachments) if (media_items or doc_attachments) else None
        formatted_text_html += f"{combined_text}"
        if reply_to_message_str is not None:
            formatted_text_html += reply_to_message_str
        plain_text, vk_format_data = HTMLConverter.convert_html_to_vk_format(formatted_text_html)
        # Отправляем одно сообщение в ВК с объединёнными вложениями
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

# =======================
# Класс для проксирования писем (IMAP)
# =======================
class MailProxy:
    def __init__(self, imap_server, email_user, email_pass, vk_service, telegram_service):
        self.imap_server = imap_server
        self.email_user = email_user
        self.email_pass = email_pass
        self.vk_service = vk_service
        self.telegram_service = telegram_service

    def run(self):
        last_heartbeat = time.time()
        while True:
            try:
                mail = imaplib.IMAP4_SSL(self.imap_server)
                mail.login(self.email_user, self.email_pass)
                mail.select('inbox')
                result, data = mail.search(None, 'UNSEEN')
                if result == 'OK':
                    email_ids = data[0].split()
                    for e_id in email_ids:
                        result, data = mail.fetch(e_id, '(RFC822)')
                        raw_email = data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        subject = decode_mime_words(msg.get('Subject', 'Без темы'))
                        from_ = decode_mime_words(msg.get('From', 'Неизвестный'))
                        date = msg.get('Date', '')
                        body = ""
                        attachments = []
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disp = str(part.get("Content-Disposition", ""))
                                if content_type == 'text/plain' and 'attachment' not in content_disp:
                                    charset = part.get_content_charset() or 'utf-8'
                                    body = part.get_payload(decode=True).decode(charset, errors='ignore')
                                elif "attachment" in content_disp:
                                    filename = part.get_filename()
                                    if filename:
                                        decoded_filename = decode_mime_words(filename)
                                        att_data = part.get_payload(decode=True)
                                        temp_filename = f"temp_{uuid.uuid4().hex}_{decoded_filename}"
                                        with open(temp_filename, "wb") as f:
                                            f.write(att_data)
                                        attachments.append((temp_filename, decoded_filename, content_type))
                        else:
                            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                        
                        text = f"Новая почта:\nОт: {from_}\nТема: {subject}\nДата: {date}\n\n{body[:500]}"
                        
                        vk_attachment_list = []
                        for file_path, filename, content_type in attachments:
                            if content_type.startswith("image/"):
                                att = self.vk_service.upload_photo(file_path)
                            else:
                                att = self.vk_service.upload_document(file_path, title=filename)
                            if att:
                                vk_attachment_list.append(att)
                        vk_attachments_str = ",".join(vk_attachment_list) if vk_attachment_list else None
                        
                        self.vk_service.send_message(None, text, attachment=vk_attachments_str, chat_id=VK_CHAT_ID)
                        self.telegram_service.send_text(text)
                        for file_path, filename, content_type in attachments:
                            if content_type.startswith("image/"):
                                self.telegram_service.send_photo_file(file_path)
                            else:
                                self.telegram_service.send_document_file(file_path, file_name=filename)
                            try:
                                os.remove(file_path)
                            except Exception as e:
                                logging.error("Ошибка при удалении временного файла %s: %s", file_path, e)
                        mail.store(e_id, '+FLAGS', '\\Seen')
                mail.logout()
            except Exception as e:
                logging.error("Ошибка при проверке почты: %s", e)
            if time.time() - last_heartbeat >= 60:
                logging.info("MailProxy heartbeat: Mail checking process is active.")
                last_heartbeat = time.time()
            time.sleep(60)

# =======================
# Локальная модель для ответов на упоминания
# =======================
def get_local_model_response():
    return "Извините, произошла ошибка при обработке вашего запроса."

# =======================
# Супервизор для автоперезапуска сервисов
# =======================
def supervise(service_run, service_name):
    while True:
        try:
            logging.info("Запуск сервиса: %s", service_name)
            service_run()
        except Exception as e:
            logging.error("Сервис %s аварийно завершился: %s", service_name, e)
        logging.info("Перезапуск сервиса %s через 5 секунд...", service_name)
        time.sleep(5)

# =======================
# Основная функция
# =======================
def main():
    db_manager = DatabaseManager(DB_FILE)
    telegram_service = TelegramService(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    vk_service = VKService(VK_ACCESS_TOKEN, VK_GROUP_ID, VK_CHAT_ID)
    schedule_manager = ScheduleManager(SCHEDULE_DATA, db_manager)
    global BotScheduler_instance
    BotScheduler_instance = BotScheduler(vk_service, telegram_service, schedule_manager)

    scheduler_thread = threading.Thread(target=lambda: supervise(BotScheduler_instance.run, "Scheduler"), name="Scheduler")
    scheduler_thread.daemon = True
    scheduler_thread.start()

    telegram_thread = threading.Thread(target=lambda: supervise(
        lambda: TelegramMessageHandler(telegram_service, vk_service, db_manager).run(), "TelegramHandler"), name="TelegramHandler")
    telegram_thread.daemon = True
    telegram_thread.start()

    if MAIL_USERNAME and MAIL_PASSWORD:
        mail_proxy = MailProxy(MAIL_IMAP_SERVER, MAIL_USERNAME, MAIL_PASSWORD, vk_service, telegram_service)
        mail_proxy_thread = threading.Thread(target=lambda: supervise(mail_proxy.run, "MailProxy"), name="MailProxy")
        mail_proxy_thread.daemon = True
        mail_proxy_thread.start()
    else:
        logging.warning("Переменные MAIL_USERNAME и MAIL_PASSWORD не заданы. Проксирование почты не запущено.")

    while True:
        global vk_restart_flag
        vk_restart_flag = False
        vk_handler = VKMessageHandler(vk_service, telegram_service, db_manager)
        vk_handler.run()
        logging.info("Перезапуск ВК-бота...")
        time.sleep(5)

if __name__ == '__main__':
    main()
