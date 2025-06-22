import logging
import time

def get_local_model_response():
    return "Извините, произошла ошибка при обработке вашего запроса."

def supervise(service_run, service_name):
    while True:
        try:
            logging.info("Запуск сервиса: %s", service_name)
            service_run()
        except Exception as e:
            logging.error("Сервис %s аварийно завершился: %s", service_name, e)
        logging.info("Перезапуск сервиса %s через 5 секунд...", service_name)
        time.sleep(5)
