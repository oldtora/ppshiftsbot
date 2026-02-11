"""Точка входа: запуск бота."""
import asyncio
from telegram.ext import Application
from config import BOT_TOKEN
from database import init_db
from handlers import setup_handlers
from scheduler import setup_jobs

def main():
    if not BOT_TOKEN:
        print("Вкажіть BOT_TOKEN в .env")
        return
    asyncio.run(init_db())
    app = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(app)
    setup_jobs(app)
    print("Бот запущено.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
