"""Планировщик: загрузка данных с API и ежедневные оповещения (через JobQueue бота)."""
from datetime import datetime, time, timedelta
import pytz
from config import FETCH_TIMES, TIMEZONE
from database import (
    replace_shifts,
    get_users_with_notifications_enabled,
    get_shifts_for_date,
    was_notification_sent,
    mark_notification_sent,
)
from api_client import fetch_shifts_from_api

tz = pytz.timezone(TIMEZONE)
NOTIFY_CUTOFF_HOUR = 18  # після 18:00 за локальним часом показуємо зміну на завтра


async def job_fetch_shifts(context):
    """Загрузить смены с API и записать в БД."""
    rows = await fetch_shifts_from_api()
    if rows:
        await replace_shifts(rows)
        print(f"[{datetime.now()}] Shifts updated: {len(rows)} rows")
    else:
        print(f"[{datetime.now()}] Shifts fetch returned nothing")


async def job_send_notifications(context):
    """Перевірити: кому зараз час нагадування — надіслати. Після 18:00 за локальним часом — зміна на завтра."""
    bot = context.bot
    now_local = datetime.now(tz)
    hour, minute = now_local.hour, now_local.minute
    if now_local.hour >= NOTIFY_CUTOFF_HOUR:
        target_date = now_local + timedelta(days=1)
        day_label = "завтра"
    else:
        target_date = now_local
        day_label = "сьогодні"
    target_ddmm = target_date.strftime("%d-%m-%Y")
    users = await get_users_with_notifications_enabled()
    for u in users:
        u_hour = int(u.get("hour", 0) or 0)
        u_minute = int(u.get("minute", 0) or 0)
        if u_hour != hour or u_minute != minute:
            continue
        if await was_notification_sent(u["id"], target_ddmm):
            continue
        shifts_target = await get_shifts_for_date(target_ddmm)
        my_shift = next((s for s in shifts_target if s["fio"] == u["fio"]), None)
        if not my_shift:
            continue
        try:
            text = (
                f"Нагадування: {day_label} ({target_ddmm}) у вас зміна.\n"
                f"зміна {my_shift['shift_type']}, місце: {my_shift['location']}."
            )
            await bot.send_message(chat_id=u["telegram_id"], text=text)
            await mark_notification_sent(u["id"], target_ddmm)
            print(f"[Notify] Надіслано {u['telegram_id']} на {target_ddmm}")
        except Exception as e:
            print(f"Notify error for {u['telegram_id']}: {e}")


def setup_jobs(application):
    """Добавить задачи в JobQueue бота."""
    jq = application.job_queue
    if not jq:
        return
    # Загрузка с API 4 раза в день
    for t in FETCH_TIMES:
        h, m = map(int, t.split(":"))
        jq.run_daily(job_fetch_shifts, time=time(hour=h, minute=m, tzinfo=tz))
    # Кожні 30 сек — перевірка сповіщень (щоб не пропустити хвилину)
    jq.run_repeating(job_send_notifications, interval=30, first=10)
    # Одна загрузка при старте (через 2 сек)
    jq.run_once(job_fetch_shifts, when=2)
