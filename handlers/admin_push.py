"""Адмін: панель (хто в боті, видалення), окрема вкладка Ключі, push-повідомлення."""
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from database import get_user_by_telegram_id, get_all_users, delete_user_by_telegram_id, get_available_keys
from config import ADMIN_IDS
from keyboards import push_recipients_keyboard, panel_admin_keyboard


async def handle_admin_push(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    # Якщо користувач у флоу активації (ключ/контакт) — передаємо в обробник ключа
    if context.user_data.get("awaiting_key") or context.user_data.get("awaiting_contact"):
        from .start import key_input
        await key_input(update, context)
        return
    # Якщо очікується введення кастомного часу сповіщення (ГГ:ХХ) — передаємо в обробник часу
    if context.user_data.get("awaiting_notify_time"):
        from .notify_time import handle_custom_notify_time
        await handle_custom_notify_time(update, context)
        return
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    db_user = await get_user_by_telegram_id(user_id)
    if not db_user:
        return

    # Вже очікуємо текст повідомлення (після вибору Всім/конкретного)
    if context.user_data.get("awaiting_push_text"):
        text = (update.message.text or "").strip()
        if not text:
            await update.message.reply_text("Введіть непустий текст.")
            return
        recipients = context.user_data.pop("push_recipients", None)
        context.user_data.pop("awaiting_push_text", None)
        if recipients == "all":
            users = await get_all_users()
            chat_ids = [u["telegram_id"] for u in users]
        elif isinstance(recipients, list):
            chat_ids = recipients
        else:
            await update.message.reply_text("Оберіть одержувачів знову (Push → Всім або користувач).")
            return
        sent = 0
        failed = 0
        for cid in chat_ids:
            try:
                await context.bot.send_message(chat_id=cid, text=text)
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(f"Надіслано {sent} одержувачам." + (f" Помилок: {failed}." if failed else ""))
        return

    # Введення telegram_id для видалення користувача
    if context.user_data.get("awaiting_delete_user_id"):
        raw = (update.message.text or "").strip()
        context.user_data.pop("awaiting_delete_user_id", None)
        if not raw.isdigit():
            await update.message.reply_text("Введіть число (telegram_id зі списку вище).")
            return
        tid = int(raw)
        if tid == user_id:
            await update.message.reply_text("Не можна видалити самого себе.")
            return
        deleted = await delete_user_by_telegram_id(tid)
        if deleted:
            await update.message.reply_text(
                f"Користувача {tid} видалено. Він зможе зайти знову лише пройшовши всі кроки (контакт, ключ, ПІБ)."
            )
        else:
            await update.message.reply_text(f"Користувача з id {tid} не знайдено в базі.")
        return

    # Кнопка «🔑 Ключі» — окрема вкладка, дані з БД при кожному запиті
    if update.message.text.strip() == "🔑 Ключі":
        keys = await get_available_keys()
        if not keys:
            await update.message.reply_text("🔑 Доступних ключів немає (всі використані).")
            return
        lines = [f"🔑 Доступні ключі ({len(keys)} шт.):\n"] + [f"• {k}" for k in keys]
        text = "\n".join(lines)
        if len(text) > 4000:
            text = "\n".join(lines[:1] + [f"• {k}" for k in keys[:80]]) + f"\n\n... та ще {len(keys) - 80}."
        await update.message.reply_text(text)
        return

    # Кнопка «📋 Панель» — список хто активував бота + кнопка видалення
    if update.message.text.strip() == "📋 Панель":
        users = await get_all_users()
        if not users:
            await update.message.reply_text(
                "Поки ніхто не активував бота.",
                reply_markup=panel_admin_keyboard(),
            )
            return
        lines = ["📋 Хто в боті:\n"]
        for u in users:
            fio = (u.get("fio") or "—").strip()
            tid = u.get("telegram_id", "")
            phone = (u.get("phone") or "").strip()
            line = f"• {tid} — {fio}"
            if phone:
                line += f" ({phone})"
            lines.append(line)
        await update.message.reply_text("\n".join(lines), reply_markup=panel_admin_keyboard())
        return

    # Кнопка «📤 Push-сповіщення» — вибір кому надіслати
    if update.message.text.strip() != "📤 Push-сповіщення":
        return
    users = await get_all_users()
    if not users:
        await update.message.reply_text("Немає користувачів для відправки.")
        return
    await update.message.reply_text(
        "Кому надіслати?",
        reply_markup=push_recipients_keyboard(users),
    )


admin_push_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    handle_admin_push,
)
