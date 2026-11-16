# handlers/admin_games.py — FSM-форма додавання нової гри

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from database.db import (
    add_game, delete_game, get_upcoming_games,
    parse_game_datetime, set_game_photo,
    get_venues, get_venue_name, add_venue,
)

router = Router()

# Міста — беремо з games.py
CITIES = ["Москва «бар Liberty»", "Красногорск", "Истра", "Обнинск"]

# Быстрые варианты времени (кнопки). Можно менять под себя.
TIME_PRESETS = ["18:00", "19:00", "20:00"]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── FSM ─────────────────────────────────────────────────────────────────────

class AddGameForm(StatesGroup):
    enter_title        = State()
    enter_date         = State()
    enter_time         = State()
    choose_city        = State()
    choose_venue       = State()   # выбор места кнопками из БД
    enter_location     = State()   # ввод нового места вручную
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


def time_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🕒 {t}", callback_data=f"ag_time_{t}") for t in TIME_PRESETS]
    ])


def venues_kb(venues):
    """venues — список (id, name) из БД. В callback_data кладём id, а не название
    (лимит Telegram — 64 байта, кириллица в названии его легко превысит)."""
    buttons = [
        [InlineKeyboardButton(text=f"📍 {name}", callback_data=f"ag_venue_{vid}")]
        for vid, name in venues
    ]
    buttons.append([InlineKeyboardButton(text="➕ Новое место", callback_data="ag_venue_new")])
    buttons.append([InlineKeyboardButton(text="⏭ Пропустить", callback_data="ag_skip_location")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить", callback_data="ag_confirm")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="ag_cancel")],
    ])


def skip_kb(cb: str):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Пропустить", callback_data=cb)
    ]])


# ─── ПОМОЩНИКИ АВТООЧИСТКИ ───────────────────────────────────────────────────
# Идея: в чате всегда остаётся только ТЕКУЩИЙ вопрос бота.
# При каждом шаге удаляем: предыдущий вопрос бота, предупреждение об ошибке
# (если было) и ответ админа. В конце остаётся одно итоговое сообщение.

async def _safe_delete(message: Message):
    """Удаляет сообщение, молча игнорируя ошибки (старше 48ч, нет прав и т.д.)"""
    try:
        await message.delete()
    except Exception:
        pass


async def _delete_by_id(bot, chat_id: int, msg_id):
    if not msg_id:
        return
    try:
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


async def step(message: Message, state: FSMContext, text: str,
               reply_markup=None, parse_mode: str | None = "Markdown"):
    """Удаляет предыдущий вопрос бота (и предупреждение), шлёт новый вопрос
    и запоминает его id, чтобы удалить на следующем шаге."""
    data = await state.get_data()
    await _delete_by_id(message.bot, message.chat.id, data.get("prompt_id"))
    await _delete_by_id(message.bot, message.chat.id, data.get("warn_id"))

    sent = await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    await state.update_data(prompt_id=sent.message_id, warn_id=None)
    return sent


async def warn(message: Message, state: FSMContext, text: str):
    """Короткое предупреждение об ошибке ввода. Вопрос остаётся на месте,
    предупреждение исчезнет на следующем шаге (или при следующей ошибке)."""
    data = await state.get_data()
    await _delete_by_id(message.bot, message.chat.id, data.get("warn_id"))
    sent = await message.answer(text, parse_mode="Markdown")
    await state.update_data(warn_id=sent.message_id)


# ─── СТАРТ ФОРМИ ─────────────────────────────────────────────────────────────

@router.message(Command("add_game"))
async def cmd_add_game(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    await state.clear()
    await _safe_delete(message)   # убираем саму команду /add_game
    await step(
        message, state,
        "🎮 *Добавление новой игры*\n"
        "_В любой момент можно написать /stop, чтобы отменить добавление._\n\n"
        "Шаг 1. Напиши *название игры*:"
    )
    await state.set_state(AddGameForm.enter_title)


# ─── ОСТАНОВКА ФОРМИ (на любом шаге) ─────────────────────────────────────────

@router.message(Command("stop"), StateFilter(AddGameForm))
async def ag_stop(message: Message, state: FSMContext):
    data = await state.get_data()
    await _delete_by_id(message.bot, message.chat.id, data.get("prompt_id"))
    await _delete_by_id(message.bot, message.chat.id, data.get("warn_id"))
    await state.clear()
    await _safe_delete(message)
    await message.answer("🛑 Добавление игры отменено. Ничего не сохранено в базу.")


@router.message(AddGameForm.enter_title)
async def ag_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    await _safe_delete(message)
    if not title:
        await warn(message, state, "❌ Напиши название игры текстом.")
        return

    await state.update_data(title=title)
    await step(
        message, state,
        "📆 Шаг 2. Напиши *дату* игры в формате ДД.ММ.ГГГГ\n"
        "Пример: `25.07.2026`"
    )
    await state.set_state(AddGameForm.enter_date)


@router.message(AddGameForm.enter_date)
async def ag_date(message: Message, state: FSMContext):
    date_str = (message.text or "").strip()
    await _safe_delete(message)

    # Базова перевірка формату
    parts = date_str.replace(".", "/").replace("-", "/").split("/")
    if len(parts) != 3:
        await warn(message, state, "❌ Неверный формат. Введи дату как ДД.ММ.ГГГГ\nПример: `25.07.2026`")
        return

    await state.update_data(date=date_str)
    await step(
        message, state,
        "⏰ Шаг 3. Выбери *время* начала кнопкой\n"
        "или напиши своё в формате ЧЧ:ММ (например, `20:30`):",
        reply_markup=time_kb()
    )
    await state.set_state(AddGameForm.enter_time)


async def _apply_time(message: Message, state: FSMContext, time_str: str) -> bool:
    """Проверяет время, сохраняет и переходит к выбору города. True — если ок."""
    data = await state.get_data()
    event_datetime = parse_game_datetime(data["date"], time_str)
    if event_datetime is None:
        await warn(message, state, "❌ Неверный формат времени. Введи как ЧЧ:ММ\nПример: `20:00`")
        return False

    await state.update_data(time=time_str, event_datetime=event_datetime)
    await step(
        message, state,
        "🏙 Шаг 4. Выбери *город*:",
        reply_markup=cities_kb()
    )
    await state.set_state(AddGameForm.choose_city)
    return True


@router.callback_query(AddGameForm.enter_time, F.data.startswith("ag_time_"))
async def ag_time_button(callback: CallbackQuery, state: FSMContext):
    time_str = callback.data.replace("ag_time_", "")
    await _apply_time(callback.message, state, time_str)
    await callback.answer()


@router.message(AddGameForm.enter_time)
async def ag_time(message: Message, state: FSMContext):
    time_str = (message.text or "").strip()
    await _safe_delete(message)
    if not time_str:
        await warn(message, state, "❌ Выбери время кнопкой или напиши текстом, например `20:30`")
        return
    await _apply_time(message, state, time_str)


@router.callback_query(AddGameForm.choose_city, F.data.startswith("ag_city_"))
async def ag_city(callback: CallbackQuery, state: FSMContext):
    city = callback.data.replace("ag_city_", "")
    await state.update_data(city=city)

    venues = await get_venues(city)
    hint = (
        "Выбери место из списка или добавь новое:"
        if venues else
        "Для этого города пока нет сохранённых мест. Добавь первое:"
    )
    await step(
        callback.message, state,
        f"🏙 Город: *{city}*\n\n"
        f"📍 Шаг 5. *Место проведения*\n{hint}",
        reply_markup=venues_kb(venues)
    )
    await state.set_state(AddGameForm.choose_venue)
    await callback.answer()


@router.callback_query(AddGameForm.choose_venue, F.data == "ag_venue_new")
async def ag_venue_new(callback: CallbackQuery, state: FSMContext):
    await step(
        callback.message, state,
        "📍 Напиши *название нового места* "
        "(оно сохранится и будет в списке в следующий раз):"
    )
    await state.set_state(AddGameForm.enter_location)
    await callback.answer()


@router.callback_query(AddGameForm.choose_venue, F.data == "ag_skip_location")
async def ag_skip_location(callback: CallbackQuery, state: FSMContext):
    await state.update_data(location="")
    await ask_price(callback.message, state)
    await callback.answer()


@router.callback_query(AddGameForm.choose_venue, F.data.startswith("ag_venue_"))
async def ag_venue_chosen(callback: CallbackQuery, state: FSMContext):
    venue_id = callback.data.replace("ag_venue_", "")
    name = await get_venue_name(int(venue_id)) if venue_id.isdigit() else None
    if not name:
        await callback.answer("Место не найдено, выбери другое.", show_alert=True)
        return

    await state.update_data(location=name)
    await ask_price(callback.message, state)
    await callback.answer()


# Новое место можно ввести и после кнопки «Новое место», и просто написав текст
@router.message(AddGameForm.enter_location)
@router.message(AddGameForm.choose_venue)
async def ag_location(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    await _safe_delete(message)
    if not name:
        await warn(message, state, "❌ Напиши название места текстом.")
        return

    data = await state.get_data()
    await add_venue(data["city"], name)   # сохраняем в БД для будущих игр
    await state.update_data(location=name)
    await ask_price(message, state)


async def ask_price(message: Message, state: FSMContext):
    await step(
        message, state,
        "💰 Шаг 6. Напиши *цену участия*\n"
        "Пример: `700 руб`\n"
        "или нажми «Пропустить»:",
        reply_markup=skip_kb("ag_skip_price")
    )
    await state.set_state(AddGameForm.enter_price)


@router.message(AddGameForm.enter_price)
async def ag_price(message: Message, state: FSMContext):
    price = (message.text or "").strip()
    await _safe_delete(message)
    if not price:
        await warn(message, state, "❌ Напиши цену текстом или нажми «Пропустить».")
        return
    await state.update_data(price=price)
    await ask_reg_link(message, state)


@router.callback_query(AddGameForm.enter_price, F.data == "ag_skip_price")
async def ag_skip_price(callback: CallbackQuery, state: FSMContext):
    await state.update_data(price="")
    await ask_reg_link(callback.message, state)
    await callback.answer()


async def ask_reg_link(message: Message, state: FSMContext):
    await step(
        message, state,
        "🔗 Шаг 7. Напиши *ссылку на регистрацию*\n"
        "или нажми «Пропустить»:",
        reply_markup=skip_kb("ag_skip_reg")
    )
    await state.set_state(AddGameForm.enter_reg_link)


@router.message(AddGameForm.enter_reg_link)
async def ag_reg_link(message: Message, state: FSMContext):
    link = (message.text or "").strip()
    await _safe_delete(message)
    if not link:
        await warn(message, state, "❌ Напиши ссылку текстом или нажми «Пропустить».")
        return
    await state.update_data(registration_link=link)
    await ask_photo(message, state)


@router.callback_query(AddGameForm.enter_reg_link, F.data == "ag_skip_reg")
async def ag_skip_reg(callback: CallbackQuery, state: FSMContext):
    await state.update_data(registration_link="")
    await ask_photo(callback.message, state)
    await callback.answer()


async def ask_photo(message: Message, state: FSMContext):
    await step(
        message, state,
        "🖼 Шаг 8. Отправь *фото* для этой игры\n"
        "или нажми «Пропустить»:",
        reply_markup=skip_kb("ag_skip_photo")
    )
    await state.set_state(AddGameForm.enter_photo)


@router.message(AddGameForm.enter_photo, F.photo)
async def ag_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await _safe_delete(message)   # file_id уже сохранён, само сообщение можно убрать
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
    await step(message, state, text, reply_markup=confirm_kb(), parse_mode=None)
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

    # Это единственное сообщение, которое остаётся в чате после всей формы
    await callback.message.edit_text(
        f"✅ Игра *{data['title']}* добавлена!\n\n"
        f"🏙 Город: {data['city']}\n"
        f"📍 Место: {data.get('location') or '—'}\n"
        f"📆 {display_date}\n\n"
        f"🔔 Подписчики получат уведомление автоматически в зависимости от их настройки подписки в 12:00",
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
        game_id, title, date, location, price, registration_link, max_players, city = game[:8]
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
