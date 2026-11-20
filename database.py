import sqlite3
import os
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_database.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Таблица настроек гильдии (сервера)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id INTEGER PRIMARY KEY,
        clan_name TEXT DEFAULT '116 clnx',
        review_channel_id INTEGER,
        applications_channel_id INTEGER,
        voice_channel_id INTEGER DEFAULT 1414100339820331039,
        member_role_id INTEGER,
        recruiter_role_id INTEGER,
        banner_url TEXT DEFAULT '',
        pubg_banner_url TEXT DEFAULT '',
        recruitment_open INTEGER DEFAULT 1
    )
    """)

    # Таблица заявок в клан
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        user_id INTEGER,
        user_tag TEXT,
        nickname_static TEXT,
        irl_name_age TEXT,
        rollbacks TEXT,
        status TEXT DEFAULT 'pending', -- pending, accepted, rejected, interview
        reject_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        review_message_id INTEGER
    )
    """)

    # Таблица мероприятий (PUBG)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        channel_id INTEGER,
        message_id INTEGER UNIQUE,
        thread_id INTEGER,
        team_name TEXT DEFAULT '116 clnx',
        game_server TEXT,
        event_time TEXT,
        reg_deadline TEXT,
        notes TEXT,
        organizer_id INTEGER,
        is_closed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Таблица участников мероприятий
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS event_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER,
        user_id INTEGER,
        user_name TEXT,
        static_id TEXT,
        team_name TEXT DEFAULT '',
        is_confirmed INTEGER DEFAULT 0,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(event_id, user_id),
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    )
    """)

    # Миграция колонок на случай существующей БД
    try:
        cursor.execute("ALTER TABLE guild_settings ADD COLUMN voice_channel_id INTEGER DEFAULT 1414100339820331039")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE guild_settings ADD COLUMN pubg_banner_url TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE events ADD COLUMN team_name TEXT DEFAULT '116 clnx'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE events ADD COLUMN thread_id INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE event_participants ADD COLUMN is_confirmed INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE event_participants ADD COLUMN team_name TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

# --- Настройки клана / сервера ---
def get_guild_settings(guild_id: int) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        "guild_id": guild_id,
        "clan_name": "116 clnx",
        "review_channel_id": None,
        "applications_channel_id": None,
        "voice_channel_id": 1414100339820331039,
        "member_role_id": None,
        "recruiter_role_id": 1372603820441468948,
        "banner_url": "",
        "pubg_banner_url": "",
        "recruitment_open": 1
    }

def update_guild_settings(guild_id: int, **kwargs):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
    for key, value in kwargs.items():
        cursor.execute(f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?", (value, guild_id))
    conn.commit()
    conn.close()

# --- Заявки ---
def create_application(guild_id: int, user_id: int, user_tag: str,
                       nickname_static: str, irl_name_age: str,
                       rollbacks: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO applications (guild_id, user_id, user_tag, nickname_static, irl_name_age, rollbacks)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (guild_id, user_id, user_tag, nickname_static, irl_name_age, rollbacks))
    app_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return app_id

def set_application_review_message(app_id: int, message_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE applications SET review_message_id = ? WHERE id = ?", (message_id, app_id))
    conn.commit()
    conn.close()

def get_application(app_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_last_application(guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM applications WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1
    """, (guild_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_application_status(app_id: int, status: str, reject_reason: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE applications SET status = ?, reject_reason = ? WHERE id = ?", (status, reject_reason, app_id))
    conn.commit()
    conn.close()

# --- Мероприятия PUBG ---
def create_event(guild_id: int, channel_id: int, message_id: int,
                 team_name: str, game_server: str, event_time: str, reg_deadline: str,
                 notes: str, organizer_id: int, thread_id: Optional[int] = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO events (guild_id, channel_id, message_id, thread_id, team_name, game_server, event_time, reg_deadline, notes, organizer_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (guild_id, channel_id, message_id, thread_id, team_name, game_server, event_time, reg_deadline, notes, organizer_id))
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id

def update_event_thread(event_id: int, thread_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET thread_id = ? WHERE id = ?", (thread_id, event_id))
    conn.commit()
    conn.close()

def get_event_by_message(message_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE message_id = ?", (message_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def close_event(event_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET is_closed = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

def add_event_participant(event_id: int, user_id: int, user_name: str, static_id: str, team_name: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO event_participants (event_id, user_id, user_name, static_id, team_name)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(event_id, user_id) DO UPDATE SET
        user_name = excluded.user_name,
        static_id = excluded.static_id,
        team_name = excluded.team_name
    """, (event_id, user_id, user_name, static_id, team_name))
    conn.commit()
    conn.close()

def toggle_participant_confirmed(event_id: int, user_id: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_confirmed FROM event_participants WHERE event_id = ? AND user_id = ?", (event_id, user_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return 0
    new_val = 0 if row["is_confirmed"] else 1
    cursor.execute("UPDATE event_participants SET is_confirmed = ? WHERE event_id = ? AND user_id = ?", (new_val, event_id, user_id))
    conn.commit()
    conn.close()
    return new_val

def remove_event_participant(event_id: int, user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM event_participants WHERE event_id = ? AND user_id = ?", (event_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_event_participants(event_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM event_participants WHERE event_id = ? ORDER BY id ASC", (event_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
