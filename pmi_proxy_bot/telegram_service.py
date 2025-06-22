import os
import requests
import uuid
import json
import logging

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

