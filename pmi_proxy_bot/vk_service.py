import vk_api
import logging

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
                field="screen_name",
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
