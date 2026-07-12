# handlers/admin.py — админ-команды для управления ботом

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from config import ADMIN_IDS
from database.db import add_game, add_result, delete_game, get_upcoming_games, parse_game_datetime, set_game_photo

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─────────────────────────────────────────
# ДОБАВИТЬ ИГРУ
# Формат: /add_game Название | Дата | Время | Город | Место | Ссылка на регистрацию
# Дата в формате ДД.MM.ГГГГ, время в формате ЧЧ:MM (24-часовой формат)
# Город — ОБЯЗАТЕЛЬНОЕ поле (по нему пользователи ищут игры).
# Время нужно для автоматического удаления игры через 2 часа после начала.
# Пример: /add_game Квиз №5 | 20.06.2026 | 19:00 | Киев | Бар Burnout | https://forms.gle/xxxxx
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
            "`/add_game Название | Дата | Время | Город | Место | Ссылка на регистрацию`\n\n"
            "Дата — в формате ДД.MM.ГГГГ\n"
            "Время — в формате ЧЧ:MM (24-часовой формат)\n"
            "Город — обязательное поле!\n\n"
            "*Пример:*\n"
            "`/add_game Квиз №5 | 20.06.2026 | 19:00 | Киев | Бар Burnout | https://forms.gle/xxxxx`\n\n"
            "Игра автоматически исчезнет из списка через 2 часа после начала.",
            parse_mode="Markdown"
        )
        return

    parts = [p.strip() for p in args.split("|")]

    if len(parts) < 4:
        await message.answer(
            "❌ Неверный формат. Нужно минимум: *Название | Дата | Время | Город*\n\n"
            "Город обязателен — по нему пользователи ищут игры.\n"
            "Время обязательно — по нему бот понимает, когда удалить игру.\n\n"
            "Пример: `/add_game Квиз №5 | 20.06.2026 | 19:00 | Киев | Бар Burnout`",
            parse_mode="Markdown"
        )
        return

    title = parts[0]
    date  = parts[1]
    time_str = parts[2]
    city  = parts[3]

    if not city:
        await message.answer("❌ Город не может быть пустым. Укажи название города на 4-й позиции.")
        return

    event_datetime = parse_game_datetime(date, time_str)
    if event_datetime is None:
        await message.answer(
            "❌ Не удалось распознать дату или время.\n\n"
            "Дата должна быть в формате ДД.MM.ГГГГ (например 20.06.2026)\n"
            "Время должно быть в формате ЧЧ:MM (например 19:00)"
        )
        return

    location           = parts[4] if len(parts) > 4 else ""
    registration_link  = parts[5] if len(parts) > 5 else ""

    # В поле "date" сохраняем дату+время вместе для красивого отображения
    display_date = f"{date} {time_str}"

    await add_game(
        title, display_date, location,
        registration_link=registration_link,
        city=city,
        event_datetime=event_datetime
    )

    reg_status = registration_link if registration_link else "—"
    await message.answer(
        f"✅ Игра добавлена!\n\n"
        f"🎯 Название: {title}\n"
        f"📆 Дата и время: {display_date}\n"
        f"🏙 Город: {city}\n"
        f"📍 Место: {location or '—'}\n"
        f"📝 Регистрация: {reg_status}\n\n"
        f"ℹ️ Игра автоматически исчезнет из списка через 2 часа после начала."
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
        game_id, title, date, location, registration_link, max_players, city = game[:7]
        text += f"ID: `{game_id}` — *{title}* ({date}, {city})\n"

    text += "\nЧтобы удалить: `/del_game ID`"
    await message.answer(text, parse_mode="Markdown")


# ─────────────────────────────────────────
# ДОБАВИТЬ ФОТО К ИГРЕ
# Способ: отправь фото в бот с подписью "/add_photo ID"
# ID игры узнать через /list_games
# ─────────────────────────────────────────
@router.message(F.photo, F.caption.regexp(r"^/add_photo"))
async def cmd_add_photo_with_image(message: Message):
    """Срабатывает когда фото отправлено с подписью /add_photo ID"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    args = message.caption.replace("/add_photo", "").strip()

    if not args or not args.isdigit():
        await message.answer(
            "❌ Не указан ID игры в подписи.\n\n"
            "Подпись к фото должна быть: `/add_photo ID`\n"
            "Пример: `/add_photo 3`",
            parse_mode="Markdown"
        )
        return

    game_id = int(args)

    # Берём file_id самого крупного варианта фото (последний в списке)
    photo_id = message.photo[-1].file_id

    success = await set_game_photo(game_id, photo_id)

    if success:
        await message.answer(f"✅ Фото прикреплено к игре с ID {game_id}.")
    else:
        await message.answer(f"❌ Игра с ID {game_id} не найдена.")


@router.message(Command("add_photo"))
async def cmd_add_photo_no_image(message: Message):
    """Срабатывает если написали команду без фото (текстом) — подсказываем как правильно"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    await message.answer(
        "📷 *Как прикрепить фото к игре:*\n\n"
        "1. Узнай ID игры через `/list_games`\n"
        "2. Отправь ФОТО в этот чат, а в подписи к фото напиши:\n"
        "`/add_photo ID`\n\n"
        "*Пример:* отправь картинку с подписью `/add_photo 3`\n\n"
        "⚠️ Команду нужно написать в подписи к фото, а не отдельным сообщением.",
        parse_mode="Markdown"
    )


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
        "`/add_game` Название | Дата | Время | Город | Место | Ссылка на регистрацию\n\n"
        "*ПРИМЕР* (Все значения надо прописывать через *вертикальную черту*, дата и время *только в таком формате*: \n"
        "`/add_game` Классическая | 01.01.2027 | 22:00 | Мозгожопинск | В клубе | Ссылка \n\n"
        "`/list_games` — список игр с ID\n"
        "`/del_game ID` — удалить игру где *ID это номер игры который в списке*\n"
        "`/add_photo ID` - 📷 прикрепить фото к игре (Фото и команда *отправляется одним сообщением*. *Фото+подпись(/add_photo ID)*\n\n"
        "🏆 *Результаты игр:*\n"
        "`/add_result_new` — добавить результат (пошаговая форма, *только для 1-3 мест*\n"
        "`/list_results` — список результатов\n"
        "`/edit_result ID` — редактировать результат, где ID это номер результата из списка\n"
        "`/del_result ID` — удалить результат\n\n"
        "🎯 *Квиз — вопросы:*\n"
        "`/add_question` — добавить вопрос (пошаговая форма)\n"
        "`/list_questions` — список вопросов по категориям\n"
        "`/del_question ID` — удалить вопрос\n"
        "`/quiz_stats` — информация с количеством вопросов в каждой категории (1 категория 8 вопросов, 2 категория 3 вопроса и т.д.)",
        parse_mode="Markdown"
    )
