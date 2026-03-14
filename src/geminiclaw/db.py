import sqlite3
import os

DB_PATH = "claw.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            author_id TEXT NOT NULL,
            prompt TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS threads (
            thread_id TEXT PRIMARY KEY,
            is_active INTEGER DEFAULT 0,
            session_id TEXT
        )
    ''')
    try:
        cursor.execute("ALTER TABLE threads ADD COLUMN session_id TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def insert_message(channel_id, message_id, author_id, prompt, status='pending'):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (channel_id, message_id, author_id, prompt, status) VALUES (?, ?, ?, ?, ?)",
        (str(channel_id), str(message_id), str(author_id), prompt, status)
    )
    conn.commit()
    conn.close()

def get_pending_message():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE status = 'pending' LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row

def update_message_status(msg_id, status, response=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if response is not None:
        cursor.execute(
            "UPDATE messages SET status = ?, response = ? WHERE id = ?",
            (status, response, msg_id)
        )
    else:
        cursor.execute(
            "UPDATE messages SET status = ? WHERE id = ?",
            (status, msg_id)
        )
    conn.commit()
    conn.close()

def is_thread_active(thread_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM threads WHERE thread_id = ?", (str(thread_id),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return bool(row['is_active'])
    return False

def set_thread_active(thread_id, active=True):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO threads (thread_id, is_active) VALUES (?, ?)",
        (str(thread_id), 1 if active else 0)
    )
    conn.commit()
    conn.close()

def get_thread_session(thread_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT session_id FROM threads WHERE thread_id = ?", (str(thread_id),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row['session_id']
    return None

def set_thread_session(thread_id, session_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE threads SET session_id = ? WHERE thread_id = ?",
        (session_id, str(thread_id))
    )
    conn.commit()
    conn.close()
