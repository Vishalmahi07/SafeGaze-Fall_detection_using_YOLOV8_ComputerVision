import sqlite3
import os
from datetime import datetime

DB_PATH = "fall_detection.db"
SNAPSHOTS_DIR = "snapshots"

def init_db():
    """Initializes the database and creates the necessary tables."""
    if not os.path.exists(SNAPSHOTS_DIR):
        os.makedirs(SNAPSHOTS_DIR)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            snapshot_path TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_alert(status, snapshot_path=None):
    """Logs an alert event into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO alerts (timestamp, status, snapshot_path)
        VALUES (?, ?, ?)
    ''', (timestamp, status, snapshot_path))
    conn.commit()
    conn.close()

def get_recent_alerts(limit=20):
    """Fetches the most recent alerts from the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # To return dict-like objects
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, timestamp, status, snapshot_path
        FROM alerts
        ORDER BY id DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
