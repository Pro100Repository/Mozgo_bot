# scheduler.py — автоматична розсилка сповіщень про ігри та мем недели
#
# НАЛАШТУВАННЯ ЧАСУ РОЗСИЛКИ:
# ──────────────────────────────────────────────────────────────────
BROADCAST_HOUR   = 9   # ← година розсилки нагадувань "за N днів до гри" (за часом сервера -3 до мск)
BROADCAST_MINUTE = 0    # ← хвилина розсилки нагадувань "за N днів до гри"

# За скільки днів до гри надсилати нагадування — користувач сам обирає
# один чи кілька варіантів у меню "🔔 Подписка на игры" -> "⏰ Настроить напоминания"
DAYS_BEFORE_PREFS = {
    "1d": 1,
    "2d": 2,
    "7d": 7,
}

# "Реєстрація" умовно відкривається за REGISTRATION_DAYS_BEFORE_EVENT днів до гри.
# Якщо гру додали пізніше цієї дати - нагадування шлеться в день додавання,
# а не заднім числом. Відправляється о REG_REMINDER_HOUR:REG_REMINDER_MINUTE,
# незалежно від того, о котрій годині гру фактично додали в бота.
REGISTRATION_DAYS_BEFORE_EVENT = 14
REG_REMINDER_HOUR   = 12
REG_REMINDER_MINUTE = 0

MEME_WEEKDAY = 0        # ← день тижня для мема недели: 0 = Понедельник, 1 = Вторник, ... 6 = Воскресенье
MEME_HOUR    = 9        # ← година відправки мему тижня
MEME_MINUTE  = 0        # ← хвилина відправки мему тижня
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
    get_games_for_broadcast, remove_subscriber,
    get_subscribers_by_pref, get_games_for_registration_reminder,
    mark_registration_notified,
    get_next_meme, delete_meme, count_memes,
    get_meme_subscribers, remove_meme_subscriber,
    get_scheduler_state, set_scheduler_state
)

logger = logging.getLogger(__name__)


async def send_game_notification(bot: Bot, user_id: int,
                                  title: str, date: str, location: str,
                                  price: str, registration_link: str,
                                  city: str, photo_id: str, days_before: int = 1):
    """Надсилає одне сповіщення про гру конкретному користувачу"""
    when_text = {1: "завтра", 2: "через 2 дня", 7: "через неделю"}.get(days_before, f"через {days_before} дн.")
    text = (
        f"🔔 *Напоминание об игре {when_text}!*\n\n"
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
    Надсилає нагадування про ігри для КОЖНОГО обраного користувачами варіанту
    ('за 1 день', 'за 2 дні', 'за тиждень') — окремо перевіряє ігри на кожну
    з відповідних дат і бере підписників саме з цим типом нагадування.
    Викликається щодня о BROADCAST_HOUR:BROADCAST_MINUTE.
    """
    total_sent = 0

    for pref_code, days in DAYS_BEFORE_PREFS.items():
        target_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        games = await get_games_for_broadcast(target_date)

        if not games:
            continue

        logger.info(f"[Scheduler] {pref_code}: игр на {target_date} — {len(games)}")

        for game in games:
            title, date, location, price, registration_link, city, photo_id = game

            subscribers = await get_subscribers_by_pref(city, pref_code)
            if not subscribers:
                continue

            logger.info(f"[Scheduler] {city} / {title} ({pref_code}): отправляем {len(subscribers)} подписчикам")

            for user_id in subscribers:
                sent = await send_game_notification(
                    bot, user_id,
                    title, date, location, price, registration_link, city, photo_id,
                    days_before=days
                )
                if sent:
                    total_sent += 1
                await asyncio.sleep(0.05)

    logger.info(f"[Scheduler] Розсилка ігор завершена. Надіслано: {total_sent}")


async def run_registration_reminder(bot: Bot):
    """
    Надсилає нагадування підписникам з типом 'reg14d' — окремо для кожної гри,
    для якої настав день "відкриття реєстрації" (див. get_games_for_registration_reminder).
    Кожному користувачу по кожній грі — не більше одного разу (дедуплікація
    через registration_notified). Викликається щодня о REG_REMINDER_HOUR:REG_REMINDER_MINUTE.
    """
    games = await get_games_for_registration_reminder(REGISTRATION_DAYS_BEFORE_EVENT)
    if not games:
        return

    sent = 0
    for game in games:
        game_id, title, date, location, price, registration_link, city, photo_id = game

        subscribers = await get_subscribers_by_pref(city, "reg14d")
        if not subscribers:
            continue

        text = (
            f"📝 *Открыта регистрация на игру!*\n\n"
            f"🎯 {title}\n"
            f"📆 {date}\n"
            f"🏙 Город: {city}\n"
        )
        if registration_link:
            text += f"📝 [Регистрация]({registration_link})\n"

        for user_id in subscribers:
            is_new = await mark_registration_notified(user_id, game_id)
            if not is_new:
                continue  # уже отправляли по этой игре этому пользователю

            try:
                if photo_id:
                    await bot.send_photo(user_id, photo=photo_id, caption=text, parse_mode="Markdown")
                else:
                    await bot.send_message(user_id, text, parse_mode="Markdown")
                sent += 1
            except TelegramForbiddenError:
                await remove_subscriber(user_id)
            except (TelegramBadRequest, Exception) as e:
                logger.warning(f"[RegReminder] Не удалось отправить {user_id}: {e}")

            await asyncio.sleep(0.05)

    logger.info(f"[RegReminder] Нагадування про відкриття реєстрації надіслано: {sent}")


async def run_meme_broadcast(bot: Bot):
    """
    Надсилає один мем всім підписникам і видаляє його з черги.
    Викликається щотижня (у день MEME_WEEKDAY).
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
                    "Мем недели не будет отправлен.\n"
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
    WEEKDAY_NAMES = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
    days_list = ", ".join(f"{v} дн." for v in DAYS_BEFORE_PREFS.values())
    logger.info(
        f"[Scheduler] Запущено.\n"
        f"  Ігри: щодня о {BROADCAST_HOUR:02d}:{BROADCAST_MINUTE:02d}, "
        f"варіанти нагадувань: {days_list} до гри\n"
        f"  Реєстрація (за {REGISTRATION_DAYS_BEFORE_EVENT} дн. до гри): "
        f"щодня о {REG_REMINDER_HOUR:02d}:{REG_REMINDER_MINUTE:02d}\n"
        f"  Мем недели: щотижня в {WEEKDAY_NAMES[MEME_WEEKDAY]} о {MEME_HOUR:02d}:{MEME_MINUTE:02d}"
    )

    last_game_run = await _load_last_run_date("last_game_broadcast")
    last_reg_run  = await _load_last_run_date("last_reg_reminder")
    last_meme_run = await _load_last_run_date("last_meme_broadcast")

    while True:
        now = datetime.now()

        now_time = now.hour * 60 + now.minute  # поточний час в хвилинах

        # ─── Розсилка ігор (за N днів до гри) ─────────────────────
        game_time = BROADCAST_HOUR * 60 + BROADCAST_MINUTE
        if (now_time >= game_time
                and now.date() != last_game_run):
            last_game_run = now.date()
            await set_scheduler_state("last_game_broadcast", last_game_run.isoformat())
            try:
                await run_daily_broadcast(bot)
            except Exception as e:
                logger.error(f"[Scheduler] Помилка розсилки ігор: {e}")

        # ─── Нагадування про відкриття реєстрації (окремий час — 12:00) ──
        reg_time = REG_REMINDER_HOUR * 60 + REG_REMINDER_MINUTE
        if (now_time >= reg_time
                and now.date() != last_reg_run):
            last_reg_run = now.date()
            await set_scheduler_state("last_reg_reminder", last_reg_run.isoformat())
            try:
                await run_registration_reminder(bot)
            except Exception as e:
                logger.error(f"[Scheduler] Помилка нагадування про реєстрацію: {e}")

        # ─── Мем недели ──────────────────────────────────────────
        meme_time = MEME_HOUR * 60 + MEME_MINUTE
        if (now.weekday() == MEME_WEEKDAY
                and now_time >= meme_time
                and now.date() != last_meme_run):
            last_meme_run = now.date()
            await set_scheduler_state("last_meme_broadcast", last_meme_run.isoformat())
            try:
                await run_meme_broadcast(bot)
            except Exception as e:
                logger.error(f"[Scheduler] Помилка розсилки мему: {e}")

        # Перевіряємо раз на 30 секунд щоб не пропустити потрібну хвилину
        await asyncio.sleep(30)
