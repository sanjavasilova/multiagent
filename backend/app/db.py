import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import get_settings


@contextmanager
def connection():
    conn = sqlite3.connect(get_settings().database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connection() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS experiments (
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          mode TEXT NOT NULL, rounds INTEGER NOT NULL, model TEXT NOT NULL,
          created_at TEXT NOT NULL, summary TEXT
        );
        CREATE TABLE IF NOT EXISTS question_outputs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id INTEGER NOT NULL,
          question_id INTEGER NOT NULL, output_json TEXT NOT NULL,
          FOREIGN KEY(experiment_id) REFERENCES experiments(id)
        );
        """)


def create_experiment(name: str, mode: str, rounds: int, model: str, summary: str = "") -> int:
    with connection() as c:
        cur = c.execute(
            "INSERT INTO experiments(name,mode,rounds,model,created_at,summary) VALUES(?,?,?,?,?,?)",
            (name, mode, rounds, model, datetime.now(timezone.utc).isoformat(), summary),
        )
        return cur.lastrowid


def save_output(experiment_id: int, question_id: int, output: dict):
    with connection() as c:
        c.execute("INSERT INTO question_outputs(experiment_id,question_id,output_json) VALUES(?,?,?)",
                  (experiment_id, question_id, json.dumps(output)))


def list_experiments():
    with connection() as c:
        return [dict(r) for r in c.execute("SELECT * FROM experiments ORDER BY id DESC")]


def get_experiment(experiment_id: int):
    with connection() as c:
        exp = c.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
        if not exp:
            return None
        outputs = c.execute("SELECT question_id,output_json FROM question_outputs WHERE experiment_id=?",
                            (experiment_id,)).fetchall()
        result = dict(exp)
        result["outputs"] = [{"question_id": r["question_id"], **json.loads(r["output_json"])} for r in outputs]
        return result
