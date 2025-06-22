import json
from pmi_proxy_bot.html_converter import HTMLConverter


def test_html_to_vk_format():
    html = '<b>Bold</b> and <i>italic</i> <a href="https://example.com">link</a>'
    plain, data = HTMLConverter.convert_html_to_vk_format(html)
    assert plain == 'Bold and italic link'
    fmt = json.loads(data)
    assert fmt['version'] == '1'
    assert len(fmt['items']) == 3
