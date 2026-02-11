"""Конфигурация бота."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Корень проекта (папка, где лежит config.py) — БД всегда относительно него
PROJECT_ROOT = Path(__file__).resolve().parent

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
EMS_API_URL = os.getenv("EMS_API_URL", "https://ems-api.example.com")
EMS_API_KEY = os.getenv("EMS_API_KEY", "")

_db_raw = os.getenv("DATABASE_PATH", "data/bot.db")
DB_PATH = str(PROJECT_ROOT / _db_raw) if not os.path.isabs(_db_raw) else _db_raw
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

TIMEZONE = os.getenv("TIMEZONE", "Europe/Kyiv")

# Адміни (telegram_id через кому) — бачать кнопку Push-сповіщення
def _parse_ids(env_val: str) -> list[int]:
    out = []
    for x in (env_val or "").split(","):
        x = x.strip()
        if x and x.isdigit():
            out.append(int(x))
    return out

ADMIN_IDS = _parse_ids(os.getenv("ADMIN_IDS", ""))

# Розклад завантаження змін з API. Кожен запуск повністю замінює таблицю shifts (не кеш).
# Користувач завжди бачить дані з БД на момент запиту; після наступного FETCH — актуальні з API.
FETCH_TIMES = ["06:00", "10:00", "14:00", "18:00"]  # 4 рази на день; можна додати "12:00" тощо
