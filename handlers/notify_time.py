"""Обробка введення власного часу сповіщення (ГГ:ХХ)."""
import re
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from database import set_notification_settings
from keyboards import notify_toggle_keyboard
from config import TIMEZONE

TIMEZONE_HINT = f"Часовий пояс бота: {TIMEZONE}."


def parse_time(text: str) -> tuple[int, int] | None:
    """Парсинг ГГ:ХХ або Г:ХХ. Повертає (год, хв) або None."""
    text = (text or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not m:
        return None
    h, m_val = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= m_val <= 59:
        return (h, m_val)
    return None


async def handle_custom_notify_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_notify_time"):
        return
    if not update.message or not update.message.text:
        return
    user_id = context.user_data.get("awaiting_notify_time_user_id")
    if not user_id:
        context.user_data.pop("awaiting_notify_time", None)
        context.user_data.pop("awaiting_notify_time_user_id", None)
        return
    parsed = parse_time(update.message.text)
    if parsed is None:
        await update.message.reply_text(
            "Невірний формат. Введіть час у вигляді ГГ:ХХ або Г:ХХ (наприклад 13:30 або 9:00)."
        )
        return
    hour, minute = parsed
    await set_notification_settings(user_id, hour, minute, 1)
    context.user_data.pop("awaiting_notify_time", None)
    context.user_data.pop("awaiting_notify_time_user_id", None)
    await update.message.reply_text(
        f"Сповіщення увімкнено. Щодня о {hour}:{minute:02d}. {TIMEZONE_HINT}",
        reply_markup=notify_toggle_keyboard(True),
    )


custom_notify_time_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    handle_custom_notify_time,
)
