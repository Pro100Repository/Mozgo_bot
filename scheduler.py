# scheduler.py — автоматична розсилка сповіщень про ігри та мем дня
#
# НАЛАШТУВАННЯ ЧАСУ РОЗСИЛКИ:
# ──────────────────────────────────────────────────────────────────
BROADCAST_HOUR   = 9   # ← година розсилки ігор (за часом сервера -3 до мск)
BROADCAST_MINUTE = 0    # ← хвилина розсилки ігор
DAYS_BEFORE_GAME = 1    # ← за скільки днів до гри надсилати сповіщення

MEME_HOUR   = 18        # ← година відправки мему дня
MEME_MINUTE = 29         # ← хвилина відправки мему дня
                        #   (можна зробити інший час ніж розсилка ігор,
                        #    наприклад MEME_HOUR=10 щоб мем о 10:00, ігри о 12:00)

MEME_LOW_THRESHOLD = 2  # ← при якій кількості мемів надсилати попередження адміну
# ──────────────────────────────────────────────────────────────────

import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import ADMIN_IDS
from database.db import (
    get_games_for_broadcast, get_city_subscribers, remove_subscriber,
    get_next_meme, delete_meme, count_memes,
    get_meme_subscribers, remove_meme_subscriber,
    get_scheduler_state, set_scheduler_state
)

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


async def run_meme_broadcast(bot: Bot):
    """
    Надсилає один мем всім підписникам і видаляє його з черги.
    Якщо мемів мало — надсилає попередження адміну.
    """
    meme = await get_next_meme()
    if not meme:
        logger.info("[Meme] Черга мемів порожня — розсилка пропущена")
        # Повідомляємо всіх адмінів
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    "⚠️ *Очередь мемов пустая!*\n\n"
                    "Мем на сегодня не будет отправлен.\n"
                    "Добавь новые мемы через команду `/add_meme`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return

    meme_id, photo_id = meme
    subscribers = await get_meme_subscribers()

    logger.info(f"[Meme] Відправляємо мем {meme_id} для {len(subscribers)} підписників")

    sent = 0
    for user_id in subscribers:
        try:
            await bot.send_photo(user_id, photo=photo_id)
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            await remove_meme_subscriber(user_id)
        except (TelegramBadRequest, Exception) as e:
            logger.warning(f"[Meme] Помилка відправки {user_id}: {e}")

    # Видаляємо відправлений мем з черги
    await delete_meme(meme_id)
    logger.info(f"[Meme] Мем {meme_id} відправлено {sent} підписникам та видалено з черги")

    # Перевіряємо залишок і попереджаємо адміна
    remaining = await count_memes()
    if remaining <= MEME_LOW_THRESHOLD:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⚠️ *Мало мемов в очереди!*\n\n"
                    f"Осталось: *{remaining}* мем(а)\n"
                    f"Пополни очередь через команду `/add_meme`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass


async def _load_last_run_date(key: str):
    """Читає дату останньої розсилки з БД (переживає рестарт бота)"""
    value = await get_scheduler_state(key)
    if value:
        return datetime.strptime(value, "%Y-%m-%d").date()
    return None


async def scheduler_loop(bot: Bot):
    """
    Фоновий цикл — чекає потрібного часу і запускає розсилки.
    Перевіряє час щохвилини.
    """
    logger.info(
        f"[Scheduler] Запущено.\n"
        f"  Ігри: щодня о {BROADCAST_HOUR:02d}:{BROADCAST_MINUTE:02d}, "
        f"за {DAYS_BEFORE_GAME} день до гри\n"
        f"  Мем дня: щодня о {MEME_HOUR:02d}:{MEME_MINUTE:02d}"
    )

    last_game_run = await _load_last_run_date("last_game_broadcast")
    last_meme_run = await _load_last_run_date("last_meme_broadcast")

    while True:
        now = datetime.now()

        now_time = now.hour * 60 + now.minute  # поточний час в хвилинах

        # ─── Розсилка ігор ───────────────────────────────────────
        game_time = BROADCAST_HOUR * 60 + BROADCAST_MINUTE
        if (now_time >= game_time
                and now.date() != last_game_run):
            last_game_run = now.date()
            await set_scheduler_state("last_game_broadcast", last_game_run.isoformat())
            try:
                await run_daily_broadcast(bot)
            except Exception as e:
                logger.error(f"[Scheduler] Помилка розсилки ігор: {e}")

        # ─── Мем дня ─────────────────────────────────────────────
        meme_time = MEME_HOUR * 60 + MEME_MINUTE
        if (now_time >= meme_time
                and now.date() != last_meme_run):
            last_meme_run = now.date()
            await set_scheduler_state("last_meme_broadcast", last_meme_run.isoformat())
            try:
                await run_meme_broadcast(bot)
            except Exception as e:
                logger.error(f"[Scheduler] Помилка розсилки мему: {e}")

        # Перевіряємо раз на 30 секунд щоб не пропустити потрібну хвилину
        await asyncio.sleep(30)
