"""Клавиатуры бота."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import ADMIN_IDS

def main_menu(telegram_id: int | None = None):
    """Головне меню після активації та вибору ПІБ. Якщо telegram_id в ADMIN_IDS — додається кнопка Push та Панель."""
    rows = [
        [KeyboardButton("📅 Мої зміни")],
        [KeyboardButton("🔔 Сповіщення"), KeyboardButton("🔄 Скинути ПІБ")],
    ]
    if telegram_id is not None and telegram_id in ADMIN_IDS:
        rows.append([KeyboardButton("📤 Push-сповіщення"), KeyboardButton("📋 Панель")])
        rows.append([KeyboardButton("🔑 Ключі")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def request_contact_keyboard():
    """Кнопка «Поділитися контактом» для отримання номера/айді."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Поділитися контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def fio_keyboard(fio_list: list[str]):
    """Инлайн-кнопки выбора ФИО."""
    if not fio_list:
        return None
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"fio:{name}")]
        for name in fio_list
    ]
    return InlineKeyboardMarkup(buttons)


def time_keyboard():
    """Вибір часу для сповіщення (години, свій час, тест)."""
    row1 = [InlineKeyboardButton(f"{h}:00", callback_data=f"notify_hr:{h}") for h in range(6, 11)]
    row2 = [InlineKeyboardButton(f"{h}:00", callback_data=f"notify_hr:{h}") for h in range(11, 16)]
    row3 = [InlineKeyboardButton(f"{h}:00", callback_data=f"notify_hr:{h}") for h in range(16, 22)]
    row4 = [InlineKeyboardButton("✏️ Свій час (ГГ:ХХ)", callback_data="notify_custom")]
    row5 = [InlineKeyboardButton("🧪 Тест зараз", callback_data="notify_test_now")]
    return InlineKeyboardMarkup([row1, row2, row3, row4, row5])


def notify_toggle_keyboard(enabled: bool):
    """Увімк/вимк сповіщень + тест зараз (завжди доступний, навіть після вимк/вкл)."""
    text = "🔕 Вимкн. сповіщення" if enabled else "🔔 Увімкн. сповіщення"
    buttons = [
        [InlineKeyboardButton(text, callback_data="notify_toggle")],
        [InlineKeyboardButton("🧪 Тест зараз", callback_data="notify_test_now")],
    ]
    return InlineKeyboardMarkup(buttons)


def panel_admin_keyboard():
    """Кнопка під повідомленням панелі: видалити користувача. Ключі — окрема вкладка «🔑 Ключі»."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Видалити користувача", callback_data="admin_delete_user")],
    ])


def push_recipients_keyboard(users: list[dict]):
    """Вибір одержувачів push: Всім, один або кілька (батч). users: [{"telegram_id", "fio"}, ...]"""
    buttons = [[InlineKeyboardButton("Всім", callback_data="push_to:all")]]
    for u in users:
        fio = (u.get("fio") or "—").strip() or "—"
        tid = u.get("telegram_id", "")
        label = f"{fio} ({tid})"[:60]
        buttons.append([InlineKeyboardButton(label, callback_data=f"push_to:{tid}")])
    buttons.append([InlineKeyboardButton("📋 Обрати кількох", callback_data="push_batch")])
    return InlineKeyboardMarkup(buttons)


def push_batch_keyboard(users: list[dict], selected_ids: list[int]):
    """Клавіатура батч-вибору: позначити кількох, потім «Готово»."""
    buttons = []
    for u in users:
        tid = u.get("telegram_id")
        fio = (u.get("fio") or "—").strip() or "—"
        label = f"{fio} ({tid})"[:55]
        if tid in selected_ids:
            label = "✓ " + label
        else:
            label = "○ " + label
        buttons.append([InlineKeyboardButton(label, callback_data=f"push_toggle:{tid}")])
    n = len(selected_ids)
    done_label = f"Готово — надіслати вибраним ({n})" if n else "Готово — надіслати вибраним"
    buttons.append([InlineKeyboardButton(done_label, callback_data="push_batch_done")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="push_batch_back")])
    return InlineKeyboardMarkup(buttons)
