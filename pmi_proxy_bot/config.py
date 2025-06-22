import os
import datetime
import logging
from dotenv import load_dotenv

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

BotScheduler_instance = None
