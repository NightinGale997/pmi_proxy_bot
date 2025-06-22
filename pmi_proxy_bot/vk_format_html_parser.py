from html.parser import HTMLParser

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
