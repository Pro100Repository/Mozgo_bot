# handlers/admin_games.py — FSM-форма додавання нової гри

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from database.db import (
    add_game, delete_game, get_upcoming_games,
    parse_game_datetime, set_game_photo,
)

router = Router()

# Міста — беремо з games.py
CITIES = ["Москва «бар Liberty»", "Красногорск", "Истра", "Обнинск"]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── FSM ─────────────────────────────────────────────────────────────────────

class AddGameForm(StatesGroup):
    enter_title        = State()
    enter_date         = State()
    enter_time         = State()
    choose_city        = State()
    enter_location     = State()
    enter_price        = State()
    enter_reg_link     = State()
    enter_photo        = State()
    confirm            = State()


# ─── КЛАВІАТУРИ ──────────────────────────────────────────────────────────────

def cities_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🏙 {c}", callback_data=f"ag_city_{c}")]
        for c in CITIES
    ])


def confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить и отправить уведомления", callback_data="ag_confirm")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="ag_cancel")],
    ])


def skip_kb(cb: str):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Пропустить", callback_data=cb)
    ]])


# ─── СТАРТ ФОРМИ ─────────────────────────────────────────────────────────────

@router.message(Command("add_game"))
async def cmd_add_game(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    await state.clear()
    await message.answer(
        "🎮 *Добавление новой игры*\n\n"
        "Шаг 1. Напиши *название игры*:",
        parse_mode="Markdown"
    )
    await state.set_state(AddGameForm.enter_title)


@router.message(AddGameForm.enter_title)
async def ag_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer(
        "📆 Шаг 2. Напиши *дату* игры в формате ДД.ММ.ГГГГ\n"
        "Пример: `25.07.2026`",
        parse_mode="Markdown"
    )
    await state.set_state(AddGameForm.enter_date)


@router.message(AddGameForm.enter_date)
async def ag_date(message: Message, state: FSMContext):
    date_str = message.text.strip()
    # Базова перевірка формату
    parts = date_str.replace(".", "/").replace("-", "/").split("/")
    if len(parts) != 3:
        await message.answer("❌ Неверный формат. Введи дату как ДД.ММ.ГГГГ\nПример: `25.07.2026`", parse_mode="Markdown")
        return
    await state.update_data(date=date_str)
    await message.answer(
        "⏰ Шаг 3. Напиши *время* начала в формате ЧЧ:ММ\n"
        "Пример: `20:00`",
        parse_mode="Markdown"
    )
    await state.set_state(AddGameForm.enter_time)


@router.message(AddGameForm.enter_time)
async def ag_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    data = await state.get_data()

    event_datetime = parse_game_datetime(data["date"], time_str)
    if event_datetime is None:
        await message.answer(
            "❌ Неверный формат времени. Введи как ЧЧ:ММ\nПример: `20:00`",
            parse_mode="Markdown"
        )
        return

    await state.update_data(time=time_str, event_datetime=event_datetime)
    await message.answer(
        "🏙 Шаг 4. Выбери *город*:",
        reply_markup=cities_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(AddGameForm.choose_city)


@router.callback_query(AddGameForm.choose_city, F.data.startswith("ag_city_"))
async def ag_city(callback: CallbackQuery, state: FSMContext):
    city = callback.data.replace("ag_city_", "")
    await state.update_data(city=city)
    await callback.message.edit_text(
        f"🏙 Город: *{city}*\n\n"
        "📍 Шаг 5. Напиши *место проведения*\n"
        "или нажми «Пропустить»:",
        reply_markup=skip_kb("ag_skip_location"),
        parse_mode="Markdown"
    )
    await state.set_state(AddGameForm.enter_location)
    await callback.answer()


@router.message(AddGameForm.enter_location)
async def ag_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text.strip())
    await ask_price(message, state)


@router.callback_query(AddGameForm.enter_location, F.data == "ag_skip_location")
async def ag_skip_location(callback: CallbackQuery, state: FSMContext):
    await state.update_data(location="")
    await ask_price(callback.message, state)
    await callback.answer()


async def ask_price(message: Message, state: FSMContext):
    await message.answer(
        "💰 Шаг 6. Напиши *цену участия*\n"
        "Пример: `700 руб`\n"
        "или нажми «Пропустить»:",
        reply_markup=skip_kb("ag_skip_price"),
        parse_mode="Markdown"
    )
    await state.set_state(AddGameForm.enter_price)


@router.message(AddGameForm.enter_price)
async def ag_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text.strip())
    await ask_reg_link(message, state)


@router.callback_query(AddGameForm.enter_price, F.data == "ag_skip_price")
async def ag_skip_price(callback: CallbackQuery, state: FSMContext):
    await state.update_data(price="")
    await ask_reg_link(callback.message, state)
    await callback.answer()


async def ask_reg_link(message: Message, state: FSMContext):
    await message.answer(
        "🔗 Шаг 7. Напиши *ссылку на регистрацию*\n"
        "или нажми «Пропустить»:",
        reply_markup=skip_kb("ag_skip_reg"),
        parse_mode="Markdown"
    )
    await state.set_state(AddGameForm.enter_reg_link)


@router.message(AddGameForm.enter_reg_link)
async def ag_reg_link(message: Message, state: FSMContext):
    await state.update_data(registration_link=message.text.strip())
    await ask_photo(message, state)


@router.callback_query(AddGameForm.enter_reg_link, F.data == "ag_skip_reg")
async def ag_skip_reg(callback: CallbackQuery, state: FSMContext):
    await state.update_data(registration_link="")
    await ask_photo(callback.message, state)
    await callback.answer()


async def ask_photo(message: Message, state: FSMContext):
    await message.answer(
        "🖼 Шаг 8. Отправь *фото* для этой игры\n"
        "или нажми «Пропустить»:",
        reply_markup=skip_kb("ag_skip_photo"),
        parse_mode="Markdown"
    )
    await state.set_state(AddGameForm.enter_photo)


@router.message(AddGameForm.enter_photo, F.photo)
async def ag_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await show_confirm(message, state)


@router.callback_query(AddGameForm.enter_photo, F.data == "ag_skip_photo")
async def ag_skip_photo(callback: CallbackQuery, state: FSMContext):
    await state.update_data(photo_id="")
    await show_confirm(callback.message, state)
    await callback.answer()


async def show_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    display_date = f"{data['date']} {data['time']}"

    text = (
        f"📋 Проверь данные игры:\n\n"
        f"🎯 Название: {data['title']}\n"
        f"📆 Дата и время: {display_date}\n"
        f"🏙 Город: {data['city']}\n"
        f"📍 Место: {data.get('location') or '—'}\n"
        f"💰 Цена: {data.get('price') or '—'}\n"
        f"🔗 Регистрация: {data.get('registration_link') or '—'}\n"
        f"🖼 Фото: {'✅ есть' if data.get('photo_id') else '—'}\n\n"
        "Всё верно?"
    )
    await message.answer(text, reply_markup=confirm_kb())
    await state.set_state(AddGameForm.confirm)


@router.callback_query(AddGameForm.confirm, F.data == "ag_confirm")
async def ag_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    display_date = f"{data['date']} {data['time']}"

    # Зберігаємо гру
    await add_game(
        title             = data["title"],
        date              = display_date,
        location          = data.get("location", ""),
        registration_link = data.get("registration_link", ""),
        price             = data.get("price", ""),
        city              = data["city"],
        event_datetime    = data["event_datetime"],
        photo_id          = data.get("photo_id", ""),
    )

    await callback.message.edit_text(
        f"✅ Игра *{data['title']}* добавлена!\n\n"
        f"🏙 Город: {data['city']}\n"
        f"📆 {display_date}\n\n"
        f"🔔 Подписчики получат уведомление автоматически за день до игры в 12:00",
        parse_mode="Markdown"
    )

    # Розсилка відбудеться автоматично о 12:00 за день до гри (через scheduler.py)

    await callback.answer()


@router.callback_query(AddGameForm.confirm, F.data == "ag_cancel")
async def ag_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Добавление игры отменено.")
    await callback.answer()


# ─── ВИДАЛЕННЯ ГРИ ────────────────────────────────────────────────────────────

@router.message(Command("del_game"))
async def cmd_del_game(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    args = message.text.replace("/del_game", "").strip()
    if not args or not args.isdigit():
        await message.answer(
            "📝 *Формат:* `/del_game ID`\n"
            "ID узнать через `/list_games`",
            parse_mode="Markdown"
        )
        return

    deleted = await delete_game(int(args))
    if deleted:
        await message.answer(f"✅ Игра с ID {args} удалена.")
    else:
        await message.answer(f"❌ Игра с ID {args} не найдена.")


# ─── СПИСОК ІГОР ──────────────────────────────────────────────────────────────

@router.message(Command("list_games"))
async def cmd_list_games(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    games = await get_upcoming_games(with_id=True)
    if not games:
        await message.answer("📭 Предстоящих игр нет.")
        return

    text = "📋 Список игр (для админа):\n\n"
    for game in games:
        game_id, title, date, location, registration_link, max_players, city = game[:7]
        text += f"ID: {game_id} — {title} ({date}, {city})\n"

    text += "\nЧтобы удалить: /del_game ID"
    await message.answer(text)


# ─── ФОТО ДО ГРИ ──────────────────────────────────────────────────────────────

@router.message(F.photo, F.caption.regexp(r"^/add_photo"))
async def cmd_add_photo_with_image(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    args = message.caption.replace("/add_photo", "").strip()
    if not args or not args.isdigit():
        await message.answer(
            "❌ Подпись к фото должна быть: `/add_photo ID`",
            parse_mode="Markdown"
        )
        return

    success = await set_game_photo(int(args), message.photo[-1].file_id)
    if success:
        await message.answer(f"✅ Фото прикреплено к игре с ID {args}.")
    else:
        await message.answer(f"❌ Игра с ID {args} не найдена.")


@router.message(Command("add_photo"))
async def cmd_add_photo_no_image(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    await message.answer(
        "📷 Отправь ФОТО с подписью `/add_photo ID`\n\n"
        "ID узнать через `/list_games`",
        parse_mode="Markdown"
    )
