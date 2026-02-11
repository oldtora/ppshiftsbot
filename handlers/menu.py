"""Главное меню: мои смены, оповещения, сброс ФИО."""
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from database import (
    get_user_by_telegram_id,
    get_shifts_by_fio,
    reset_user_fio,
    get_all_fio_from_shifts,
    get_notification_settings,
)
from keyboards import main_menu, fio_keyboard, time_keyboard, notify_toggle_keyboard


async def cmd_my_shifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.message.text.strip() != "📅 Мої зміни":
        return
    user = update.effective_user
    if not user:
        return
    db_user = await get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text("Спочатку активуйте бота (/start).")
        return
    if not db_user["fio"]:
        fio_list = await get_all_fio_from_shifts()
        if not fio_list:
            await update.message.reply_text("Спочатку оберіть ПІБ. Дані змін поки не завантажено.")
            return
        await update.message.reply_text("Оберіть ваше ПІБ:", reply_markup=fio_keyboard(fio_list))
        return
    shifts = await get_shifts_by_fio(db_user["fio"])
    if not shifts:
        await update.message.reply_text("За вашим ПІБ змін поки немає в базі.")
        return
    lines = ["📅 Ваші зміни:\n"]
    for s in shifts:
        lines.append(f"• {s['date_ddmm']} — зміна {s['shift_type']}, місце: {s['location']}")
    await update.message.reply_text("\n".join(lines))


async def cmd_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.text.strip() != "🔔 Сповіщення":
        return
    user = update.effective_user
    if not user:
        return
    db_user = await get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text("Спочатку активуйте бота (/start).")
        return
    if not db_user["fio"]:
        await update.message.reply_text("Спочатку оберіть ПІБ в меню.")
        return
    from config import TIMEZONE
    tz_hint = f"Часовий пояс бота: {TIMEZONE}."
    cur = await get_notification_settings(db_user["id"])
    if cur and cur.get("enabled") == 1:
        h, m = int(cur.get("hour", 0) or 0), int(cur.get("minute", 0) or 0)
        text = f"Зараз сповіщення увімкнено: щодня о {h}:{m:02d}. {tz_hint}"
        await update.message.reply_text(text, reply_markup=notify_toggle_keyboard(True))
    else:
        await update.message.reply_text(
            f"Увімкніть сповіщення та оберіть час нагадування. {tz_hint}\n\nАбо натисніть «Свій час» і введіть ГГ:ХХ:",
            reply_markup=time_keyboard(),
        )


async def cmd_reset_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.text.strip() != "🔄 Скинути ПІБ":
        return
    user = update.effective_user
    if not user:
        return
    db_user = await get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text("Спочатку активуйте бота (/start).")
        return
    if not db_user["fio"]:
        await update.message.reply_text("ПІБ не було обрано.")
        return
    await reset_user_fio(db_user["id"])
    fio_list = await get_all_fio_from_shifts()
    if not fio_list:
        await update.message.reply_text("ПІБ скинуто. Коли зʼявляться дані змін — оберіть ПІБ через /start.")
        return
    await update.message.reply_text("ПІБ скинуто. Оберіть знову:", reply_markup=fio_keyboard(fio_list))


menu_handlers = [
    MessageHandler(filters.Regex("^📅 Мої зміни$"), cmd_my_shifts),
    MessageHandler(filters.Regex("^🔔 Сповіщення$"), cmd_notifications),
    MessageHandler(filters.Regex("^🔄 Скинути ПІБ$"), cmd_reset_fio),
]
