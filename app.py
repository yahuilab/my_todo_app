from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from flask import Flask, abort, redirect, render_template, request, url_for


def _default_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "MyTodoApp"
    return Path.home() / "AppData" / "Local" / "MyTodoApp"


def _db_path() -> Path:
    override = (os.environ.get("TODO_DB_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    return _default_data_dir() / "todo.db"


DB_PATH = _db_path()


@dataclass(frozen=True)
class Todo:
    id: int
    title: str
    done: bool
    created_at: str


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
    init_db()

    @app.get("/")
    def index():
        todos = list(get_todos())
        return render_template("index.html", todos=todos)

    @app.post("/add")
    def add():
        title = (request.form.get("title") or "").strip()
        if not title:
            return redirect(url_for("index"))
        add_todo(title)
        return redirect(url_for("index"))

    @app.post("/toggle/<int:todo_id>")
    def toggle(todo_id: int):
        if not toggle_todo(todo_id):
            abort(404)
        return redirect(url_for("index"))

    @app.post("/delete/<int:todo_id>")
    def delete(todo_id: int):
        if not delete_todo(todo_id):
            abort(404)
        return redirect(url_for("index"))

    return app


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_done ON todos(done)")


def get_todos() -> Iterable[Todo]:
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT id, title, done, created_at
            FROM todos
            ORDER BY done ASC, id DESC
            """
        ).fetchall()
    for r in rows:
        yield Todo(
            id=int(r["id"]),
            title=str(r["title"]),
            done=bool(int(r["done"])),
            created_at=str(r["created_at"]),
        )


def add_todo(title: str) -> None:
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect_db() as conn:
        conn.execute(
            "INSERT INTO todos(title, done, created_at) VALUES(?, 0, ?)",
            (title, created_at),
        )


def toggle_todo(todo_id: int) -> bool:
    with connect_db() as conn:
        cur = conn.execute(
            """
            UPDATE todos
            SET done = CASE done WHEN 1 THEN 0 ELSE 1 END
            WHERE id = ?
            """,
            (todo_id,),
        )
        return cur.rowcount == 1


def delete_todo(todo_id: int) -> bool:
    with connect_db() as conn:
        cur = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        return cur.rowcount == 1


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

