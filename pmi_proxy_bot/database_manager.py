import sqlite3
import datetime
from .config import TIMEZONE

class DatabaseManager:
    def __init__(self, db_file):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_datetime TEXT,
                title TEXT,
                description TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def add_event(self, event_datetime, title, description):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (event_datetime, title, description) VALUES (?, ?, ?)",
            (event_datetime.isoformat(), title, description)
        )
        conn.commit()
        conn.close()

    def get_upcoming_events(self, limit=5):
        now = datetime.datetime.now(TIMEZONE).isoformat()
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, event_datetime, title, description FROM events WHERE event_datetime > ? ORDER BY event_datetime ASC LIMIT ?",
            (now, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        events = []
        for row in rows:
            event_id, event_datetime_str, title, description = row
            event_datetime = datetime.datetime.fromisoformat(event_datetime_str)
            events.append({"id": event_id, "datetime": event_datetime, "title": title, "description": description})
        return events

    def get_all_events(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT id, event_datetime, title, description FROM events ORDER BY event_datetime ASC")
        rows = cursor.fetchall()
        conn.close()
        events = []
        for row in rows:
            event_id, event_datetime_str, title, description = row
            event_datetime = datetime.datetime.fromisoformat(event_datetime_str)
            events.append({"id": event_id, "datetime": event_datetime, "title": title, "description": description})
        return events

    def delete_event(self, event_id):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        changes = conn.total_changes
        conn.commit()
        conn.close()
        return changes > 0
