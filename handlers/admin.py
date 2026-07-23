# handlers/admin.py — админ-команды для управления ботом

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from config import ADMIN_IDS
from database.db import add_result, get_subscription_stats, get_total_subscribers_count

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─────────────────────────────────────────
# ДОБАВИТЬ ИГРУ
# Формат: /add_game 
# Дата в формате ДД.MM.ГГГГ, время в формате ЧЧ:MM (24-часовой формат)
# Город — ОБЯЗАТЕЛЬНОЕ поле (по нему пользователи ищут игры).
# Время нужно для автоматического удаления игры через 2 часа после начала.
# Пример: /add_game Квиз №5 | 20.06.2026 | 19:00 | Киев | Бар Burnout | 700 руб | https://forms.gle/xxxxx
# ─────────────────────────────────────────
# ─────────────────────────────────────────
# ДОБАВИТЬ РЕЗУЛЬТАТ
# Формат: /add_result_new 
# ─────────────────────────────────────────
@router.message(Command("add_result"))
async def cmd_add_result(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    args = message.text.replace("/add_result", "").strip()

    if not args:
        await message.answer(
            "📝 *Формат команды:*\n\n"
            "`/add_result Название игры | Дата | Команда | Место | Баллы`\n\n"
            "*Пример:*\n"
            "`/add_result Квиз №4 | 15.06.2025 | Умники | 1 | 42.5`",
            parse_mode="Markdown"
        )
        return

    parts = [p.strip() for p in args.split("|")]

    if len(parts) < 5:
        await message.answer(
            "❌ Неверный формат. Нужно 5 полей через `|`\n\n"
            "Пример: `/add_result Квиз №4 | 15.06.2025 | Умники | 1 | 42.5`",
            parse_mode="Markdown"
        )
        return

    game_title = parts[0]
    game_date = parts[1]
    team_name = parts[2]

    try:
        place = int(parts[3])
        score = float(parts[4])
    except ValueError:
        await message.answer("❌ Место должно быть целым числом, баллы — числом (можно с точкой).")
        return

    await add_result(game_title, game_date, team_name, place, score)

    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(place, f"{place}-е место")
    await message.answer(
        f"✅ Результат добавлен!\n\n"
        f"🎮 Игра: {game_title} ({game_date})\n"
        f"👥 Команда: {team_name}\n"
        f"{medal} Место: {place}\n"
        f"⭐ Баллы: {score}"
    )


# ─────────────────────────────────────────
# СТАТИСТИКА ПОДПИСОК
# Формат: /subscribers
# Показывает количество подписчиков по каждому городу и общее число.
# ─────────────────────────────────────────
@router.message(Command("subscribers"))
async def cmd_subscribers(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    stats = await get_subscription_stats()
    total_users = await get_total_subscribers_count()

    if not stats:
        await message.answer("📭 Пока никто не подписан ни на один город.")
        return

    text = (
        "🔔 *Статистика подписок*\n\n"
        f"👥 Уникальных подписчиков: *{total_users}*\n\n"
        "📍 *По городам:*\n"
    )
    for city, count in stats:
        text += f"  🏙 {city} — {count}\n"

    total_slots = sum(count for _, count in stats)
    text += f"\nℹ️ Всего подписок (город+юзер): {total_slots}"

    await message.answer(text, parse_mode="Markdown")


# ─────────────────────────────────────────
# СПИСОК АДМИН-КОМАНД
# ─────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin_help(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    await message.answer(
        "🔧 *Админ-команды:*\n\n"
        "📅 *Игры:*\n"
        "`/add_game` - Добавить игру (Пошаговая форма)\n\n"
        "`/list_games` — список игр с ID\n"
        "`/del_game ID` — удалить игру где *ID это номер игры который в списке*\n"
        "`/add_photo ID` - 📷 прикрепить фото к игре (Фото и команда *отправляется одним сообщением*. *Фото+подпись(/add_photo ID)*\n\n"
        "🏆 *Результаты игр:*\n"
        "`/add_result_new` — добавить результат (пошаговая форма, *только для 1-3 мест*)\n"
        "`/list_results` — список результатов\n"
        "`/edit_result ID` — редактировать результат, где ID это номер результата из списка\n"
        "`/del_result ID` — удалить результат\n\n"
        "🎯 *Квиз — вопросы:*\n"
        "`/add_question` — добавить вопрос (пошаговая форма)\n"
        "`/list_questions` — список вопросов по категориям\n"
        "`/del_question ID` — удалить вопрос\n"
        "`/quiz_stats` — информация с количеством вопросов в каждой категории (1 категория 8 вопросов, 2 категория 3 вопроса и т.д.)\n\n"
        "🔔 *Подписки:*\n"
        "`/subscribers` — статистика подписок по городам и всего уникальных подписчиков\n\n"
        "😂 *Мем дня:*\n"
        "Отправь фото с подписью `/add_meme` — добавится в очередь\n"
        "`/meme_stats` — сколько мемов в очереди",
        parse_mode="Markdown"
    )
