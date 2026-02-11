"""Старт и активация по ключу."""
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, filters
from database import get_user_by_telegram_id, get_key_by_text, mark_key_used, create_user, get_all_fio_from_shifts
from keyboards import main_menu, fio_keyboard, request_contact_keyboard


async def self_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    db_user = await get_user_by_telegram_id(user.id)
    if db_user:
        if db_user["fio"]:
            await update.message.reply_text(
                f"Знову привіт! Ваш профіль: {db_user['fio']}.\nСкористайтесь меню нижче.",
                reply_markup=main_menu(user.id),
            )
        else:
            fio_list = await get_all_fio_from_shifts()
            if not fio_list:
                await update.message.reply_text(
                    "Дані змін ще не завантажено. Зачекайте оновлення або зверніться до адміністратора."
                )
                return
            kb = fio_keyboard(fio_list)
            await update.message.reply_text(
                "Оберіть ваше ПІБ зі списку:",
                reply_markup=kb,
            )
        return
    context.user_data["awaiting_contact"] = True
    await update.message.reply_text(
        "Ласкаво просимо. Для активації спочатку обовʼязково поділіться контактом (натисніть кнопку нижче):",
        reply_markup=request_contact_keyboard(),
    )


async def key_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ключ приймаємо лише після контакту (awaiting_key). Без контакту — нагадуємо поділитися.
    awaiting_key = context.user_data.get("awaiting_key")
    awaiting_contact = context.user_data.get("awaiting_contact")
    if not awaiting_key and not awaiting_contact:
        return
    if awaiting_contact and not awaiting_key:
        await update.message.reply_text(
            "Спочатку поділіться контактом (натисніть кнопку «Поділитися контактом»). Після цього введіть ключ активації."
        )
        return
    key_text = (update.message.text or "").strip()
    if not key_text:
        await update.message.reply_text("Введіть ключ.")
        return
    key_row = await get_key_by_text(key_text)
    if not key_row:
        await update.message.reply_text("Невірний ключ.")
        return
    if key_row["used"] == 1:
        await update.message.reply_text("Цей ключ вже використано.")
        return
    context.user_data.pop("awaiting_contact", None)
    phone = context.user_data.pop("contact_phone", None) or ""
    user_id = await create_user(update.effective_user.id, key_row["id"], phone=phone)
    await mark_key_used(key_row["id"])
    del context.user_data["awaiting_key"]
    fio_list = await get_all_fio_from_shifts()
    if not fio_list:
        await update.message.reply_text(
            "Ключ активовано. Дані змін поки не завантажено — оберіть ПІБ пізніше через /start."
        )
        return
    kb = fio_keyboard(fio_list)
    await update.message.reply_text("Ключ активовано. Оберіть ваше ПІБ:", reply_markup=kb)


async def contact_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_contact"):
        return
    if not update.message or not update.message.contact:
        return
    contact = update.message.contact
    context.user_data["contact_phone"] = contact.phone_number or ""
    context.user_data["awaiting_contact"] = False
    context.user_data["awaiting_key"] = True
    await update.message.reply_text(
        "Дякуємо. Тепер введіть ключ активації (одним рядком):",
        reply_markup=ReplyKeyboardRemove(),
    )


start_handler = CommandHandler("start", self_start)
contact_handler = MessageHandler(filters.CONTACT, contact_received)
key_input_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, key_input)
