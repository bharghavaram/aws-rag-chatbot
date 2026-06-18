import sqlite3
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            question      TEXT NOT NULL,
            answer        TEXT,
            source        TEXT,
            answer_found  INTEGER DEFAULT 1,
            response_time FLOAT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def log_query(question, answer, source, answer_found, response_time):
    conn = get_conn()
    conn.execute(
        "INSERT INTO queries (question, answer, source, answer_found, response_time, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (question, answer, source, int(answer_found), response_time, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_analytics():
    conn = get_conn()
    cur = conn.cursor()

    total = cur.execute("SELECT COUNT(*) FROM queries").fetchone()[0]

    most_asked = [
        {"question": r["question"], "count": r["count"]}
        for r in cur.execute(
            "SELECT question, COUNT(*) as count FROM queries "
            "GROUP BY question ORDER BY count DESC LIMIT 10"
        ).fetchall()
    ]

    no_answer = [
        {"question": r["question"], "answer": r["answer"], "created_at": r["created_at"]}
        for r in cur.execute(
            "SELECT question, answer, created_at FROM queries "
            "WHERE answer_found = 0 ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    ]

    avg_row = cur.execute(
        "SELECT AVG(response_time) as t FROM queries WHERE response_time IS NOT NULL"
    ).fetchone()
    avg_time = round(avg_row["t"], 3) if avg_row["t"] else 0.0

    daily = [
        {"date": r["date"], "count": r["count"]}
        for r in cur.execute(
            "SELECT DATE(created_at) as date, COUNT(*) as count FROM queries "
            "GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 7"
        ).fetchall()
    ]

    conn.close()
    return {
        "total_queries": total,
        "most_asked_questions": most_asked,
        "no_answer_queries": no_answer,
        "average_response_time_seconds": avg_time,
        "queries_per_day": daily,
    }
