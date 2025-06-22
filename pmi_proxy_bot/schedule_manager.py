import datetime
import os
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from .config import TIMEZONE
import logging

class ScheduleManager:
    def __init__(self, schedule_data, db_manager):
        self.schedule_data = schedule_data
        self.db_manager = db_manager

    @staticmethod
    def calculate_week_parity():
        # Задаём начальную неделю (пример)
        start_date = datetime.datetime(2024, 9, 30, tzinfo=TIMEZONE)
        now = datetime.datetime.now(TIMEZONE)
        current_week_start = now - datetime.timedelta(days=now.weekday())
        weeks_passed = (current_week_start - start_date).days // 7
        return "Числитель" if weeks_passed % 2 == 0 else "Знаменатель"

    def generate_schedule_image(self, today_name, today_schedule, tomorrow_name, tomorrow_schedule, week_parity, events):
        gradient_classes = {
            "Понедельник": "bg-gradient-to-br from-blue-50 to-indigo-50",
            "Вторник": "bg-gradient-to-br from-pink-50 to-red-50",
            "Среда": "bg-gradient-to-br from-green-50 to-emerald-50",
            "Четверг": "bg-gradient-to-br from-yellow-50 to-amber-50",
            "Пятница": "bg-gradient-to-br from-indigo-50 to-sky-50",
            "Суббота": "bg-gradient-to-br from-teal-50 to-green-50",
            "Воскресенье": "bg-gradient-to-br from-gray-50 to-gray-100"
        }
        today_gradient = gradient_classes.get(today_name, "bg-white")
        tomorrow_gradient = gradient_classes.get(tomorrow_name, "bg-white")
        html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Расписание на {today_name} и {tomorrow_name} ({week_parity})</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-r from-indigo-100 to-purple-100 py-8">
  <div class="max-w-5xl mx-auto">
    <h1 class="text-4xl font-bold text-center mb-6 text-purple-700">
      Расписание на {today_name} и {tomorrow_name} ({week_parity})
    </h1>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Сегодня -->
      <div class="border p-4 rounded-lg {today_gradient} shadow-lg">
        <h2 class="text-2xl font-semibold text-center mb-4">Сегодня ({today_name})</h2>
'''
        if not today_schedule:
            html += '<p class="text-center text-gray-600 italic">Нет пар</p>'
        else:
            for pair in today_schedule:
                time_str = pair.get('time', '')
                details = pair.get('details', '')
                lecturer = pair.get('lecturer', '')
                room = pair.get('room', '')
                subgroup = pair.get('subgroup', '')
                parity = pair.get('parity', '')
                if parity and parity.lower() != week_parity.lower():
                    continue
                html += '<div class="mb-3">'
                html += f'  <div class="flex justify-between font-semibold text-purple-700">'
                html += f'    <span>{time_str}</span>'
                if room:
                    html += f'    <span class="text-sm text-gray-500">{room}</span>'
                html += '  </div>'
                html += f'  <p class="text-gray-700">{details}</p>'
                if lecturer:
                    html += '  <p class="text-xs text-gray-500">'
                    html += f'{lecturer}'
                    if subgroup:
                        html += f' <span class="ml-1 bg-blue-200 text-blue-800 px-1 rounded">{subgroup}</span>'
                    html += '</p>'
                html += '</div>'
        html += f'''
      </div>
      <!-- Завтра -->
      <div class="border p-4 rounded-lg {tomorrow_gradient} shadow-lg">
        <h2 class="text-2xl font-semibold text-center mb-4">Завтра ({tomorrow_name})</h2>
'''
        if not tomorrow_schedule:
            html += '<p class="text-center text-gray-600 italic">Нет пар</p>'
        else:
            for pair in tomorrow_schedule:
                time_str = pair.get('time', '')
                details = pair.get('details', '')
                lecturer = pair.get('lecturer', '')
                room = pair.get('room', '')
                subgroup = pair.get('subgroup', '')
                parity = pair.get('parity', '')
                if parity and parity.lower() != week_parity.lower():
                    continue
                html += '<div class="mb-3">'
                html += f'  <div class="flex justify-between font-semibold text-purple-700">'
                html += f'    <span>{time_str}</span>'
                if room:
                    html += f'    <span class="text-sm text-gray-500">{room}</span>'
                html += '  </div>'
                html += f'  <p class="text-gray-700">{details}</p>'
                if lecturer:
                    html += '  <p class="text-xs text-gray-500">'
                    html += f'{lecturer}'
                    if subgroup:
                        html += f' <span class="ml-1 bg-blue-200 text-blue-800 px-1 rounded">{subgroup}</span>'
                    html += '</p>'
                html += '</div>'
        html += '''
      </div>
    </div>
    <!-- Ближайшие события -->
    <div class="mt-8 border p-4 rounded-lg bg-white shadow-lg">
      <h2 class="text-2xl font-semibold text-center mb-4">Ближайшие события</h2>
'''
        if events:
            for event in events:
                event_date = event['datetime'].strftime("%d.%m.%Y %H:%M")
                html += f'''<div class="mb-2">
  <strong class="text-purple-700">{event_date}</strong> — <em class="text-gray-700">{event["title"]}</em>: {event["description"]}
</div>'''
        else:
            html += '<p class="text-center text-gray-600 italic">Событий нет.</p>'
        html += '''
    </div>
  </div>
</body>
</html>
'''
        temp_html_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
        temp_html_file.write(html.encode('utf-8'))
        temp_html_file.close()

        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument("--user-data-dir=/tmp/chrome-temp-profile")
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_window_size(1100, 860)
        driver.get("file://" + temp_html_file.name)

        output_file = "schedule.png"
        driver.save_screenshot(output_file)

        driver.quit()
        os.remove(temp_html_file.name)
        return output_file
