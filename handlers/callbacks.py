"""Обработка inline-кнопок: выбор ФИО, настройки уведомлений, push (Всім/користувач), тест нагадування."""
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from config import TIMEZONE, ADMIN_IDS
from database import (
    get_user_by_telegram_id,
    set_user_fio,
    get_all_fio_from_shifts,
    get_notification_settings,
    set_notification_settings,
    get_shifts_for_date,
    get_all_users,
)
from keyboards import main_menu, fio_keyboard, time_keyboard, notify_toggle_keyboard, push_recipients_keyboard, push_batch_keyboard

TIMEZONE_HINT = f"Часовий пояс бота: {TIMEZONE}."


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.data:
        return
    await q.answer()
    data = q.data
    user = update.effective_user
    if not user:
        return
    db_user = await get_user_by_telegram_id(user.id)
    if not db_user:
        await q.edit_message_text("Спочатку активуйте бота за ключем (/start).")
        return

    if data.startswith("fio:"):
        fio = data.replace("fio:", "", 1)
        await set_user_fio(db_user["id"], fio)
        await q.edit_message_text(f"ПІБ збережено: {fio}. Скористайтесь меню нижче.")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Оберіть дію:",
            reply_markup=main_menu(user.id),
        )
        return

    if data.startswith("notify_hr:"):
        try:
            hour = int(data.split(":")[1])
        except (IndexError, ValueError):
            hour = 8
        await set_notification_settings(db_user["id"], hour, 0, 1)
        await q.edit_message_text(
            f"Сповіщення увімкнено. Щодня о {hour}:00 ({TIMEZONE_HINT}) вам приходитиме нагадування про зміну (якщо зміна є).",
            reply_markup=notify_toggle_keyboard(True),
        )
        return

    if data == "notify_custom":
        context.user_data["awaiting_notify_time"] = True
        context.user_data["awaiting_notify_time_user_id"] = db_user["id"]
        await q.edit_message_text(
            f"Введіть час у форматі ГГ:ХХ або Г:ХХ (наприклад 13:30).\n\n{TIMEZONE_HINT}"
        )
        return

    if data == "notify_toggle":
        cur = await get_notification_settings(db_user["id"])
        if cur and cur.get("enabled") == 1:
            h, m = int(cur.get("hour", 0) or 0), int(cur.get("minute", 0) or 0)
            await set_notification_settings(db_user["id"], h, m, 0)
            await q.edit_message_text("Сповіщення вимкнено.", reply_markup=notify_toggle_keyboard(False))
        else:
            await q.edit_message_text(
                f"Оберіть час щоденного нагадування ({TIMEZONE_HINT}):",
                reply_markup=time_keyboard(),
            )
        return

    # Тест нагадування — показуємо те, що прийде о обраному часу (після 18:00 — зміна на завтра)
    if data == "notify_test_now":
        tz = pytz.timezone(TIMEZONE)
        now_local = datetime.now(tz)
        cur = await get_notification_settings(db_user["id"])
        notify_hour = int(cur.get("hour", 0) or 0) if cur else 12
        # Якщо користувач обрав час >= 18:00 — нагадування буде про завтра
        if notify_hour >= 18:
            target_date = now_local + timedelta(days=1)
            day_label = "завтра"
        else:
            target_date = now_local
            day_label = "сьогодні"
        target_ddmm = target_date.strftime("%d-%m-%Y")
        fio = (db_user.get("fio") or "").strip()
        if not fio:
            await q.answer("Спочатку оберіть ПІБ.", show_alert=True)
            return
        shifts_target = await get_shifts_for_date(target_ddmm)
        my_shift = next((s for s in shifts_target if (s.get("fio") or "").strip() == fio), None)
        if my_shift:
            text = (
                f"Нагадування (тест): {day_label} ({target_ddmm}) у вас зміна.\n"
                f"зміна {my_shift['shift_type']}, місце: {my_shift['location']}."
            )
        else:
            text = f"Нагадування (тест): {day_label} ({target_ddmm}) у вас вихідний (зміни немає в розкладі)."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        return

    # Адмін: вибір одержувача push (Всім, один або батч)
    if data.startswith("push_to:") and user.id in ADMIN_IDS:
        rest = data.replace("push_to:", "", 1)
        if rest == "all":
            context.user_data["push_recipients"] = "all"
        else:
            try:
                context.user_data["push_recipients"] = [int(rest)]
            except ValueError:
                await q.answer("Помилка.", show_alert=True)
                return
        context.user_data["awaiting_push_text"] = True
        await q.edit_message_text("Введіть текст повідомлення для відправки.")
        return

    if data == "push_batch" and user.id in ADMIN_IDS:
        users = await get_all_users()
        if not users:
            await q.answer("Немає користувачів.", show_alert=True)
            return
        context.user_data["push_batch_users"] = users
        context.user_data["push_batch_selected"] = []
        await q.edit_message_text("Оберіть одержувачів (натисніть для позначки), потім «Готово»:", reply_markup=push_batch_keyboard(users, []))
        return

    if data.startswith("push_toggle:") and user.id in ADMIN_IDS:
        try:
            tid = int(data.replace("push_toggle:", "", 1))
        except ValueError:
            return
        users = context.user_data.get("push_batch_users") or []
        selected = list(context.user_data.get("push_batch_selected") or [])
        if tid in selected:
            selected = [x for x in selected if x != tid]
        else:
            selected = selected + [tid]
        context.user_data["push_batch_selected"] = selected
        await q.edit_message_text("Оберіть одержувачів (натисніть для позначки), потім «Готово»:", reply_markup=push_batch_keyboard(users, selected))
        return

    if data == "push_batch_done" and user.id in ADMIN_IDS:
        selected = context.user_data.pop("push_batch_selected", None) or []
        context.user_data.pop("push_batch_users", None)
        if not selected:
            await q.answer("Оберіть хоча б одного одержувача.", show_alert=True)
            return
        context.user_data["push_recipients"] = selected
        context.user_data["awaiting_push_text"] = True
        await q.edit_message_text("Введіть текст повідомлення для відправки.")
        return

    if data == "push_batch_back" and user.id in ADMIN_IDS:
        context.user_data.pop("push_batch_selected", None)
        context.user_data.pop("push_batch_users", None)
        users = await get_all_users()
        await q.edit_message_text("Кому надіслати?", reply_markup=push_recipients_keyboard(users))
        return

    # Адмін: режим видалення користувача
    if data == "admin_delete_user" and user.id in ADMIN_IDS:
        context.user_data["awaiting_delete_user_id"] = True
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Введіть telegram_id користувача для видалення (число зі списку вище). Його дані будуть скинуті, він зможе зайти лише заново (контакт, ключ, ПІБ).",
        )
        return


callback_handler = CallbackQueryHandler(handle_callback)
