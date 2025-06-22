import threading
import logging
import time
from pmi_proxy_bot.config import (
    DB_FILE,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    VK_ACCESS_TOKEN,
    VK_GROUP_ID,
    VK_CHAT_ID,
    SCHEDULE_DATA,
    MAIL_USERNAME,
    MAIL_PASSWORD,
    MAIL_IMAP_SERVER,
    BotScheduler_instance,
    vk_restart_flag,
)
from pmi_proxy_bot.database_manager import DatabaseManager
from pmi_proxy_bot.telegram_service import TelegramService
from pmi_proxy_bot.vk_service import VKService
from pmi_proxy_bot.schedule_manager import ScheduleManager
from pmi_proxy_bot.bot_scheduler import BotScheduler
from pmi_proxy_bot.vk_message_handler import VKMessageHandler
from pmi_proxy_bot.telegram_message_handler import TelegramMessageHandler
from pmi_proxy_bot.mail_proxy import MailProxy
from pmi_proxy_bot.utils import supervise


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
