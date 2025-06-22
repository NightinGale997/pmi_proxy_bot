import schedule
import time
import datetime
import logging
from .config import TIMEZONE, weekday_map, SEND_SCHEDULE_TIME, CHANGE_CHAT_NAME_TIME, vk_restart_flag

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
