"""
Клиент API EMS. Дати зберігаються як dd-mm-yyyy; при парсингу з API якщо є лише dd-mm — підставляється поточний рік.
"""
import re
from datetime import datetime
import httpx
from config import EMS_API_URL, EMS_API_KEY


def normalize_date_to_ddmmyyyy(value: str, default_year: int | None = None) -> str:
    """Привести дату з API до dd-mm-yyyy. Якщо рік не заданий — default_year (за замовчуванням поточний)."""
    if not value or not isinstance(value, str):
        return ""
    value = value.strip()
    year = default_year if default_year is not None else datetime.now().year
    # Вже dd-mm-yyyy
    m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", value)
    if m:
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}-{m.group(3)}"
    # dd-mm або d-m — додати рік
    m = re.match(r"^(\d{1,2})-(\d{1,2})$", value)
    if m:
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}-{year}"
    # ISO: 2025-02-12
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if m:
        return f"{int(m.group(3)):02d}-{int(m.group(2)):02d}-{m.group(1)}"
    # 12.02.2025 або 12.02
    m = re.match(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?$", value)
    if m:
        y = m.group(3) if m.group(3) else str(year)
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}-{y}"
    # 12/02/2025
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if m:
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}-{m.group(3)}"
    return value

# Мок-данные для разработки (когда API ещё нет)
MOCK_SHIFTS = [
    {"date_ddmm": "11-02", "fio": "Yevhenii Shut", "shift_type": "D", "location": "SK"},
    {"date_ddmm": "12-02", "fio": "Yevhenii Shut", "shift_type": "N", "location": "FD"},
    {"date_ddmm": "13-02", "fio": "Yevhenii Shut", "shift_type": "M", "location": "MT"},
    {"date_ddmm": "14-02", "fio": "Yevhenii Shut", "shift_type": "8", "location": "SK"},
    {"date_ddmm": "15-02", "fio": "Yevhenii Shut", "shift_type": "9", "location": "FD"},
    {"date_ddmm": "16-02", "fio": "Yevhenii Shut", "shift_type": "10", "location": "MT"},
    {"date_ddmm": "11-02", "fio": "John Smith", "shift_type": "N", "location": "SK"},
    {"date_ddmm": "12-02", "fio": "John Smith", "shift_type": "D", "location": "FD"},
    {"date_ddmm": "13-02", "fio": "Anna Brown", "shift_type": "M", "location": "MT"},
]


async def fetch_shifts_from_api() -> list[dict] | None:
    """
    Загрузить смены с API EMS.
    Возвращает список dict: date_ddmm, fio, shift_type, location.
    При ошибке или отсутствии API возвращает None (можно подставить мок).
    """
    if not EMS_API_URL or "example.com" in EMS_API_URL:
        # Реального API нет — возвращаем мок
        return MOCK_SHIFTS.copy()

    headers = {}
    if EMS_API_KEY:
        headers["Authorization"] = f"Bearer {EMS_API_KEY}"
        # или headers["X-API-Key"] = EMS_API_KEY

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Подставь нужный метод и путь когда API будет готов
            resp = await client.get(
                f"{EMS_API_URL.rstrip('/')}/shifts",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            # Зберігаємо дати як dd-mm-yyyy; якщо API віддає тільки dd-mm — підставляємо поточний рік
            return [
                {
                    "date_ddmm": normalize_date_to_ddmmyyyy(item.get("date_ddmm", item.get("date", ""))),
                    "fio": item.get("fio", item.get("name", "")),
                    "shift_type": str(item.get("shift_type", item.get("shift", ""))),
                    "location": item.get("location", item.get("place", "")),
                }
                for item in (data if isinstance(data, list) else data.get("shifts", []))
            ]
    except Exception:
        return MOCK_SHIFTS.copy()
