"""База данных SQLite. Дати змін зберігаються в форматі dd-mm-yyyy; для пошуку приймаємо dd-mm-yyyy або dd-mm."""
import re
from datetime import datetime
import aiosqlite
from config import DB_PATH


def _normalize_ddmmyyyy(value: str, default_year: int | None = None) -> str:
    """Привести до dd-mm-yyyy для збереження. Якщо рік відсутній — default_year (за замовч. поточний)."""
    if not value or not isinstance(value, str):
        return ""
    value = value.strip()
    year = default_year if default_year is not None else datetime.now().year
    # Вже dd-mm-yyyy
    m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", value)
    if m:
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}-{m.group(3)}"
    # dd-mm — додати рік
    m = re.match(r"^(\d{1,2})-(\d{1,2})$", value)
    if m:
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}-{year}"
    # ISO 2025-02-12
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if m:
        return f"{int(m.group(3)):02d}-{int(m.group(2)):02d}-{m.group(1)}"
    # 12.02 або 12.02.2025
    m = re.match(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?$", value)
    if m:
        y = m.group(3) if m.group(3) else str(year)
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}-{y}"
    return value

async def get_connection():
    """Подключение к БД."""
    return await aiosqlite.connect(DB_PATH, check_same_thread=False)


async def init_db():
    """Создание таблиц."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS activation_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_text TEXT UNIQUE NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                key_id INTEGER NOT NULL,
                fio TEXT,
                created_at TEXT,
                FOREIGN KEY (key_id) REFERENCES activation_keys(id)
            );
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_ddmm TEXT NOT NULL,
                fio TEXT NOT NULL,
                shift_type TEXT NOT NULL,
                location TEXT NOT NULL,
                fetched_at TEXT
            );
            CREATE TABLE IF NOT EXISTS notification_settings (
                user_id INTEGER PRIMARY KEY,
                hour INTEGER NOT NULL,
                minute INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_shifts_fio ON shifts(fio);
            CREATE INDEX IF NOT EXISTS idx_shifts_date ON shifts(date_ddmm);
            CREATE TABLE IF NOT EXISTS notification_sent (
                user_id INTEGER NOT NULL,
                target_ddmm TEXT NOT NULL,
                sent_at TEXT,
                PRIMARY KEY (user_id, target_ddmm),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)
        await db.commit()
        try:
            await db.execute("ALTER TABLE users ADD COLUMN phone TEXT")
            await db.commit()
        except Exception:
            pass


async def get_key_by_text(key_text: str):
    """Найти ключ по строке. Возвращает (id, used) или None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, used FROM activation_keys WHERE key_text = ?", (key_text.strip(),)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def mark_key_used(key_id: int):
    """Пометить ключ использованным."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE activation_keys SET used = 1 WHERE id = ?", (key_id,))
        await db.commit()


async def get_user_by_telegram_id(telegram_id: int):
    """Пользователь по telegram_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, telegram_id, key_id, fio, phone FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def create_user(telegram_id: int, key_id: int, phone: str | None = None):
    """Создать пользователя после активации."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO users (telegram_id, key_id, phone) VALUES (?, ?, ?)",
            (telegram_id, key_id, phone or ""),
        )
        await db.commit()
        return cur.lastrowid


async def get_all_users():
    """Усі користувачі (для адмін-панелі та push «Всім»)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, telegram_id, fio, phone FROM users ORDER BY id"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_available_keys(limit: int = 100):
    """Доступні ключі (used=0). Дані з БД при кожному запиті."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT key_text FROM activation_keys WHERE used = 0 ORDER BY id LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def delete_user_by_telegram_id(telegram_id: int) -> bool:
    """Видалити користувача та всю повʼязану інфу. Повертає True якщо був видалений."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cur.fetchone()
        if not row:
            return False
        uid = row[0]
        await db.execute("DELETE FROM notification_sent WHERE user_id = ?", (uid,))
        await db.execute("DELETE FROM notification_settings WHERE user_id = ?", (uid,))
        await db.execute("DELETE FROM users WHERE id = ?", (uid,))
        await db.commit()
        return True


async def set_user_fio(user_id: int, fio: str):
    """Привязать ФИО к пользователю."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET fio = ? WHERE id = ?", (fio, user_id))
        await db.commit()


async def reset_user_fio(user_id: int):
    """Сбросить ФИО (установить NULL)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET fio = NULL WHERE id = ?", (user_id,))
        await db.commit()


async def get_shifts_by_fio(fio: str):
    """Все смены по ФИО, отсортированные по дате."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT date_ddmm, shift_type, location FROM shifts WHERE fio = ? ORDER BY date_ddmm",
            (fio,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_all_fio_from_shifts():
    """Список уникальных ФИО из смен (для выбора при активации)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT DISTINCT fio FROM shifts ORDER BY fio")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def replace_shifts(rows: list[dict]):
    """Повна заміна даних змін. date_ddmm зберігається як dd-mm-yyyy (з API може приходити dd-mm — додається рік)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM shifts")
        for r in rows:
            raw = (r.get("date_ddmm") or r.get("date") or "").strip()
            if not raw:
                continue
            # Якщо API вже віддав dd-mm-yyyy — зберегти; інакше нормалізувати з поточним роком
            date_key = _normalize_ddmmyyyy(raw)
            if not date_key:
                continue
            await db.execute(
                "INSERT INTO shifts (date_ddmm, fio, shift_type, location, fetched_at) VALUES (?, ?, ?, ?, datetime('now'))",
                (date_key, r["fio"], r["shift_type"], r["location"]),
            )
        await db.commit()


async def get_notification_settings(user_id: int):
    """Настройки уведомлений пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT hour, minute, enabled FROM notification_settings WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_notification_settings(user_id: int, hour: int, minute: int, enabled: int = 1):
    """Установить время уведомления."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO notification_settings (user_id, hour, minute, enabled)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET hour=?, minute=?, enabled=?""",
            (user_id, hour, minute, enabled, hour, minute, enabled),
        )
        await db.commit()


async def get_users_with_notifications_enabled():
    """Все пользователи с включёнными уведомлениями."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT u.id, u.telegram_id, u.fio, n.hour, n.minute
               FROM users u
               JOIN notification_settings n ON u.id = n.user_id
               WHERE n.enabled = 1 AND u.fio IS NOT NULL"""
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def was_notification_sent(user_id: int, target_ddmm: str) -> bool:
    """Чи вже надсилали нагадування цьому користувачу на цю дату."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM notification_sent WHERE user_id = ? AND target_ddmm = ?",
            (user_id, target_ddmm),
        )
        return (await cur.fetchone()) is not None


async def mark_notification_sent(user_id: int, target_ddmm: str):
    """Позначити, що нагадування на дату надіслано."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO notification_sent (user_id, target_ddmm, sent_at) VALUES (?, ?, datetime('now'))",
            (user_id, target_ddmm),
        )
        await db.commit()


async def get_shifts_for_date(date_str: str):
    """Зміни на конкретну дату (для нагадувань). Приймає dd-mm-yyyy або dd-mm (парсимо до dd-mm-yyyy)."""
    key = _normalize_ddmmyyyy(date_str)
    if not key:
        return []
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT fio, shift_type, location FROM shifts WHERE date_ddmm = ?",
            (key,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def add_keys_batch(keys: list[str]):
    """Добавить ключи в БД."""
    import datetime
    now = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        for k in keys:
            await db.execute(
                "INSERT OR IGNORE INTO activation_keys (key_text, used, created_at) VALUES (?, 0, ?)",
                (k.strip(), now),
            )
        await db.commit()
