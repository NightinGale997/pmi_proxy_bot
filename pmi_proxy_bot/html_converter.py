import json
from .vk_format_html_parser import VKFormatHTMLParser

class HTMLConverter:
    @staticmethod
    def convert_html_to_vk_format(html_text):
        parser = VKFormatHTMLParser()
        parser.feed(html_text)
        plain_text = parser.plain_text
        format_data = {"version": "1", "items": parser.format_items}
        return plain_text, json.dumps(format_data)
