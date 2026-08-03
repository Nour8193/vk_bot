"""
Модуль базы данных v3: персистентное хранение сессий + LLM-диагностика ошибок.

Ключевые улучшения по сравнению с v2:
- Состояния сессий сохраняются в SQLite (не теряются при перезапуске)
- Детекция ошибок выполняется через запрос к GigaChat (не эвристика)
- threading.Lock предотвращает гонки при параллельных запросах
"""

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Глобальный lock для SQLite (один файл БД — один lock)
_db_lock = threading.Lock()


class Database:
    def __init__(self, db_path: str = "french_bot.db"):
        self.db_path = db_path

    @contextmanager
    def _conn(self):
        """Контекстный менеджер: открывает соединение, фиксирует или откатывает."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self):
        """Создаёт таблицы при первом запуске."""
        with _db_lock, self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id     INTEGER PRIMARY KEY,
                    name        TEXT    NOT NULL,
                    errors      TEXT    DEFAULT '{}',
                    completed   TEXT    DEFAULT '[]',
                    total_sess  INTEGER DEFAULT 0,
                    created_at  TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    user_id     INTEGER PRIMARY KEY,
                    state       TEXT    NOT NULL DEFAULT 'menu',
                    module      TEXT,
                    mode        TEXT,
                    msg_count   INTEGER DEFAULT 0,
                    history     TEXT    DEFAULT '[]',
                    last_bot    TEXT    DEFAULT '',
                    updated_at  TEXT    DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS interactions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    module      TEXT,
                    mode        TEXT,
                    user_msg    TEXT,
                    bot_msg     TEXT,
                    ts          TEXT    DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
            """)
        logger.info("База данных инициализирована: %s", self.db_path)

    # ── Пользователи ─────────────────────────────────────────────────────────

    def create_user(self, user_id: int, name: str):
        with _db_lock, self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)",
                (user_id, name)
            )
            # Гарантируем наличие строки сессии
            conn.execute(
                "INSERT OR IGNORE INTO sessions (user_id, state) VALUES (?, 'menu')",
                (user_id,)
            )

    def get_user_profile(self, user_id: int) -> dict:
        with _db_lock, self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        if not row:
            return {}
        return {
            "user_id":          row["user_id"],
            "name":             row["name"],
            "errors":           json.loads(row["errors"] or "{}"),
            "completed_modules": json.loads(row["completed"] or "[]"),
            "total_sessions":   row["total_sess"],
        }

    def update_errors(self, user_id: int, new_errors: list):
        """Добавляет счётчики ошибок к профилю пользователя."""
        if not new_errors:
            return
        with _db_lock, self._conn() as conn:
            row = conn.execute(
                "SELECT errors FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            errors = json.loads(row["errors"] or "{}") if row else {}
            for e in new_errors:
                errors[e] = errors.get(e, 0) + 1
            conn.execute(
                "UPDATE users SET errors = ? WHERE user_id = ?",
                (json.dumps(errors, ensure_ascii=False), user_id)
            )

    def complete_module_session(self, user_id: int, module_key: str):
        with _db_lock, self._conn() as conn:
            row = conn.execute(
                "SELECT completed, total_sess FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not row:
                return
            completed = json.loads(row["completed"] or "[]")
            if module_key not in completed:
                completed.append(module_key)
            conn.execute(
                "UPDATE users SET completed = ?, total_sess = total_sess + 1 WHERE user_id = ?",
                (json.dumps(completed), user_id)
            )

    def save_interaction(self, user_id: int, module: str, mode: str,
                         user_msg: str, bot_msg: str):
        with _db_lock, self._conn() as conn:
            conn.execute(
                "INSERT INTO interactions (user_id, module, mode, user_msg, bot_msg) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, module, mode, user_msg, bot_msg)
            )

    # ── Персистентные сессии ──────────────────────────────────────────────────

    def get_session(self, user_id: int) -> dict:
        """Загружает состояние сессии из БД."""
        with _db_lock, self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE user_id = ?", (user_id,)
            ).fetchone()
        if not row:
            return {"state": "menu", "module": None, "mode": None,
                    "msg_count": 0, "history": [], "last_bot_msg": ""}
        return {
            "state":        row["state"],
            "module":       row["module"],
            "mode":         row["mode"],
            "msg_count":    row["msg_count"],
            "history":      json.loads(row["history"] or "[]"),
            "last_bot_msg": row["last_bot"] or "",
        }

    def save_session(self, user_id: int, session: dict):
        """Сохраняет состояние сессии в БД."""
        # Ограничиваем историю 20 сообщениями (кроме системного)
        history = session.get("history", [])
        if len(history) > 21:
            history = [history[0]] + history[-20:]

        with _db_lock, self._conn() as conn:
            conn.execute("""
                INSERT INTO sessions (user_id, state, module, mode, msg_count, history, last_bot, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    state      = excluded.state,
                    module     = excluded.module,
                    mode       = excluded.mode,
                    msg_count  = excluded.msg_count,
                    history    = excluded.history,
                    last_bot   = excluded.last_bot,
                    updated_at = excluded.updated_at
            """, (
                user_id,
                session.get("state", "menu"),
                session.get("module"),
                session.get("mode"),
                session.get("msg_count", 0),
                json.dumps(history, ensure_ascii=False),
                session.get("last_bot_msg", ""),
            ))

    def reset_session(self, user_id: int):
        """Сбрасывает сессию в состояние меню."""
        self.save_session(user_id, {
            "state": "menu", "module": None, "mode": None,
            "msg_count": 0, "history": [], "last_bot_msg": ""
        })

    # ── Аналитика для преподавателя ───────────────────────────────────────────

    def get_all_users_report(self) -> list[dict]:
        """Сводный отчёт по всем студентам для преподавателя."""
        with _db_lock, self._conn() as conn:
            rows = conn.execute("""
                SELECT u.user_id, u.name, u.total_sess, u.errors, u.completed,
                       COUNT(i.id) as total_msgs
                FROM users u
                LEFT JOIN interactions i ON i.user_id = u.user_id
                GROUP BY u.user_id
                ORDER BY u.total_sess DESC
            """).fetchall()
        report = []
        for row in rows:
            errors = json.loads(row["errors"] or "{}")
            top_errors = sorted(errors.items(), key=lambda x: x[1], reverse=True)[:3]
            report.append({
                "user_id":    row["user_id"],
                "name":       row["name"],
                "sessions":   row["total_sess"],
                "messages":   row["total_msgs"],
                "modules":    json.loads(row["completed"] or "[]"),
                "top_errors": top_errors,
            })
        return report

    def get_group_top_errors(self) -> dict:
        """Агрегирует топ ошибок по всей группе."""
        with _db_lock, self._conn() as conn:
            rows = conn.execute("SELECT errors FROM users").fetchall()
        total: dict = {}
        for row in rows:
            errors = json.loads(row["errors"] or "{}")
            for k, v in errors.items():
                total[k] = total.get(k, 0) + v
        return dict(sorted(total.items(), key=lambda x: x[1], reverse=True))


# ── LLM-диагностика ошибок ────────────────────────────────────────────────────

def detect_errors_llm(giga, user_msg: str) -> list:
    """
    Анализирует сообщение студента через GigaChat.
    Возвращает список кодов ошибок (пустой, если ошибок нет).

    Преимущество перед эвристикой: обнаруживает контекстные ошибки,
    которые невозможно найти простым поиском подстрок.
    """
    from config import ERROR_DETECTION_PROMPT
    from gigachat.models import Chat, Messages, MessagesRole

    try:
        prompt = ERROR_DETECTION_PROMPT + f'"{user_msg}"'
        response = giga.chat(Chat(messages=[
            Messages(role=MessagesRole.USER, content=prompt)
        ]))
        raw = response.choices[0].message.content.strip()

        # Очистка от markdown-обёрток если модель добавила их
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        errors = data.get("errors", [])
        if isinstance(errors, list):
            return [str(e) for e in errors if e]
    except (json.JSONDecodeError, KeyError):
        logger.warning("LLM вернул некорректный JSON для детекции ошибок: %s", raw if 'raw' in dir() else '?')
    except Exception as e:
        logger.warning("Ошибка LLM-детекции: %s", e)

    # Fallback: базовая эвристика если LLM недоступен
    return _detect_errors_fallback(user_msg)


def _detect_errors_fallback(msg: str) -> list:
    """Резервная эвристическая детекция — используется только при сбое LLM."""
    errors = []
    m = msg.lower()
    if " je habite" in m or m.startswith("je habite"):
        errors.append("élision_je")
    if " je aime" in m or m.startswith("je aime"):
        errors.append("élision_je")
    if "je est" in m or "tu est " in m:
        errors.append("conjugaison_être")
    if any(w in m for w in ["le école", "le université", "le eau"]):
        errors.append("article_genre")
    if " je va " in m or m.startswith("je va "):
        errors.append("conjugaison_aller")
    return errors
