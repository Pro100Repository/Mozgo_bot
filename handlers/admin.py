# handlers/admin.py — админ-команды для управления ботом

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from config import ADMIN_IDS
from database.db import add_game, add_result, delete_game, get_upcoming_games

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─────────────────────────────────────────
# ДОБАВИТЬ ИГРУ
# Формат: /add_game Название | Дата | Город | Место | Ссылка на регистрацию
# Город — ОБЯЗАТЕЛЬНОЕ поле (по нему пользователи ищут игры).
# Пример: /add_game Квиз №5 | 20.06.2025 | Киев | Бар Burnout | https://forms.gle/xxxxx
# ─────────────────────────────────────────
@router.message(Command("add_game"))
async def cmd_add_game(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    args = message.text.replace("/add_game", "").strip()

    if not args:
        await message.answer(
            "📝 *Формат команды:*\n\n"
            "`/add_game Название | Дата | Город | Место | Ссылка на регистрацию`\n\n"
            "Город — обязательное поле!\n\n"
            "*Пример:*\n"
            "`/add_game Квиз №5 | 20.06.2025 | Киев | Бар Burnout | https://forms.gle/xxxxx`",
            parse_mode="Markdown"
        )
        return

    parts = [p.strip() for p in args.split("|")]

    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат. Нужно минимум: *Название | Дата | Город*\n\n"
            "Город обязателен — по нему пользователи ищут игры.\n\n"
            "Пример: `/add_game Квиз №5 | 20.06.2025 | Киев | Бар Burnout | https://forms.gle/xxxxx`",
            parse_mode="Markdown"
        )
        return

    title = parts[0]
    date  = parts[1]
    city  = parts[2]

    if not city:
        await message.answer("❌ Город не может быть пустым. Укажи название города на 3-й позиции.")
        return

    location           = parts[3] if len(parts) > 3 else ""
    registration_link  = parts[4] if len(parts) > 4 else ""

    await add_game(title, date, location, registration_link=registration_link, city=city)

    reg_status = registration_link if registration_link else "—"
    await message.answer(
        f"✅ Игра добавлена!\n\n"
        f"🎯 Название: {title}\n"
        f"📆 Дата: {date}\n"
        f"🏙 Город: {city}\n"
        f"📍 Место: {location or '—'}\n"
        f"📝 Регистрация: {reg_status}"
    )


# ─────────────────────────────────────────
# УДАЛИТЬ ИГРУ
# Формат: /del_game ID
# ─────────────────────────────────────────
@router.message(Command("del_game"))
async def cmd_del_game(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    args = message.text.replace("/del_game", "").strip()

    if not args or not args.isdigit():
        await message.answer(
            "📝 *Формат:* `/del_game ID`\n\n"
            "Чтобы узнать ID игр — используйте `/list_games`",
            parse_mode="Markdown"
        )
        return

    game_id = int(args)
    deleted = await delete_game(game_id)

    if deleted:
        await message.answer(f"✅ Игра с ID {game_id} удалена.")
    else:
        await message.answer(f"❌ Игра с ID {game_id} не найдена.")


# ─────────────────────────────────────────
# СПИСОК ИГР С ID (для админа)
# ─────────────────────────────────────────
@router.message(Command("list_games"))
async def cmd_list_games(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    games = await get_upcoming_games(with_id=True)

    if not games:
        await message.answer("📭 Предстоящих игр нет.")
        return

    text = "📋 *Список игр (для админа):*\n\n"
    for game in games:
        game_id, title, date, location, registration_link, max_players, city = game
        text += f"ID: `{game_id}` — *{title}* ({date}, {city})\n"

    text += "\nЧтобы удалить: `/del_game ID`"
    await message.answer(text, parse_mode="Markdown")


# ─────────────────────────────────────────
# ДОБАВИТЬ РЕЗУЛЬТАТ
# Формат: /add_result Название игры | Дата | Команда | Место | Баллы
# Пример: /add_result Квиз №4 | 15.06.2025 | Умники | 1 | 42.5
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
        "`/add_game Название | Дата | Город | Место | Ссылка на регистрацию`\n"
        "`/list_games` — список игр с ID\n"
        "`/del_game ID` — удалить игру\n\n"
        "🏆 *Результаты:*\n"
        "`/add_result Игра | Дата | Команда | Место | Баллы`",
        parse_mode="Markdown"
    )
