# scheduler.py — автоматична розсилка сповіщень про ігри
#
# НАЛАШТУВАННЯ ЧАСУ РОЗСИЛКИ:
# ──────────────────────────────────────────────────────────────────
BROADCAST_HOUR   = 00   # ← година розсилки (за московським часом сервера)
BROADCAST_MINUTE = 45    # ← хвилина розсилки
DAYS_BEFORE_GAME = 1    # ← за скільки днів до гри надсилати сповіщення
# ──────────────────────────────────────────────────────────────────

import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from database.db import get_games_for_broadcast, get_city_subscribers, remove_subscriber

logger = logging.getLogger(__name__)


async def send_game_notification(bot: Bot, user_id: int,
                                  title: str, date: str, location: str,
                                  price: str, registration_link: str,
                                  city: str, photo_id: str):
    """Надсилає одне сповіщення про гру конкретному користувачу"""
    text = (
        f"🔔 *Напоминание об игре завтра!*\n\n"
        f"🎯 {title}\n"
        f"📆 {date}\n"
        f"🏙 Город: {city}\n"
    )
    if location:
        text += f"📍 Место: {location}\n"
    if price:
        text += f"💰 Цена: {price}\n"
    if registration_link:
        text += f"📝 [Регистрация]({registration_link})\n"

    try:
        if photo_id:
            await bot.send_photo(
                user_id, photo=photo_id,
                caption=text, parse_mode="Markdown"
            )
        else:
            await bot.send_message(user_id, text, parse_mode="Markdown")
        return True
    except TelegramForbiddenError:
        # Користувач заблокував бота — видаляємо підписки
        await remove_subscriber(user_id)
        return False
    except (TelegramBadRequest, Exception) as e:
        logger.warning(f"Не удалось отправить уведомление {user_id}: {e}")
        return False


async def run_daily_broadcast(bot: Bot):
    """
    Надсилає сповіщення про ігри які відбудуться через DAYS_BEFORE_GAME днів.
    Викликається щодня о BROADCAST_HOUR:BROADCAST_MINUTE
    """
    target_date = (datetime.now() + timedelta(days=DAYS_BEFORE_GAME)).strftime("%Y-%m-%d")
    logger.info(f"[Scheduler] Запуск розсилки для ігор {target_date}")

    games = await get_games_for_broadcast(target_date)

    if not games:
        logger.info(f"[Scheduler] Ігор на {target_date} немає — розсилка не потрібна")
        return

    total_sent = 0

    for game in games:
        title, date, location, price, registration_link, city, photo_id = game

        subscribers = await get_city_subscribers(city)
        if not subscribers:
            logger.info(f"[Scheduler] Місто {city}: підписників немає")
            continue

        logger.info(f"[Scheduler] {city} / {title}: відправляємо {len(subscribers)} підписникам")

        for user_id in subscribers:
            sent = await send_game_notification(
                bot, user_id,
                title, date, location, price, registration_link, city, photo_id
            )
            if sent:
                total_sent += 1

            # Затримка між повідомленнями — 20 повідомлень/сек
            await asyncio.sleep(0.05)

    logger.info(f"[Scheduler] Розсилка завершена. Надіслано: {total_sent}")


async def scheduler_loop(bot: Bot):
    """
    Фоновий цикл — чекає потрібного часу і запускає розсилку.
    Перевіряє час щохвилини.
    """
    logger.info(
        f"[Scheduler] Запущено. Розсилка щодня о "
        f"{BROADCAST_HOUR:02d}:{BROADCAST_MINUTE:02d}, "
        f"за {DAYS_BEFORE_GAME} день до гри"
    )

    last_run_date = None  # щоб не запускати двічі в один день

    while True:
        now = datetime.now()

        if (now.hour == BROADCAST_HOUR
                and now.minute == BROADCAST_MINUTE
                and now.date() != last_run_date):
            last_run_date = now.date()
            try:
                await run_daily_broadcast(bot)
            except Exception as e:
                logger.error(f"[Scheduler] Помилка розсилки: {e}")

        # Перевіряємо раз на хвилину
        await asyncio.sleep(60)
