import json
import os
import sqlite3
from datetime import datetime, timezone

from app.config import DB_PATH


def _conn():
    return sqlite3.connect(DB_PATH, timeout=30)


def init_db():
    d = os.path.dirname(DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'under_review',
                layer1_json TEXT,
                layer2_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        c.commit()


def publish(image_path: str, layer1_result: dict) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO posts (image_path, status, layer1_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (image_path, "under_review", json.dumps(layer1_result), now, now),
        )
        c.commit()
        return cur.lastrowid


def get_pending(limit: int = 5):
    with _conn() as c:
        cur = c.execute(
            "SELECT id, image_path, layer1_json FROM posts "
            "WHERE status = 'under_review' ORDER BY id LIMIT ?",
            (limit,),
        )
        return cur.fetchall()


def update_status(post_id: int, status: str, layer2_report: dict | None = None):
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        if layer2_report is not None:
            c.execute(
                "UPDATE posts SET status=?, layer2_json=?, updated_at=? WHERE id=?",
                (status, json.dumps(layer2_report), now, post_id),
            )
        else:
            c.execute(
                "UPDATE posts SET status=?, updated_at=? WHERE id=?",
                (status, now, post_id),
            )
        c.commit()


def get_post(post_id: int) -> dict | None:
    with _conn() as c:
        cur = c.execute(
            "SELECT id, image_path, status, layer1_json, layer2_json, created_at "
            "FROM posts WHERE id=?",
            (post_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "image_path": row[1],
        "status": row[2],
        "layer1": json.loads(row[3]) if row[3] else None,
        "layer2": json.loads(row[4]) if row[4] else None,
        "created_at": row[5],
    }
