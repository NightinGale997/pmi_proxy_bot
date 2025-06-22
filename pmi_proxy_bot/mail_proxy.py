import imaplib
import email
import uuid
import time
import logging
import os
from .config import VK_CHAT_ID


def decode_mime_words(s):
    decoded_fragments = email.header.decode_header(s)
    return ''.join(
        fragment.decode(encoding if encoding else 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

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
