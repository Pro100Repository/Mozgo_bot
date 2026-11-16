# handlers/admin_games.py — FSM-форма додавання нової гри

import re
import calendar
from datetime import date, datetime

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
    get_game_full, update_game,
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


# ─── КАЛЕНДАРЬ И БЫСТРЫЙ ВВОД ДАТЫ ───────────────────────────────────────────

MONTHS_RU = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
CALENDAR_MONTHS_AHEAD = 12   # насколько месяцев вперёд можно листать календарь


def _cbtn(text: str, cb: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb)


def calendar_rows(year: int, month: int, prefix: str) -> list:
    """Сетка месяца. Колбэки: {prefix}_day_ГГГГ-ММ-ДД, {prefix}_cal_ГГГГ-ММ, {prefix}_noop.
    Прошедшие дни неактивны, сегодняшний выделен [скобками]."""
    today = date.today()
    noop = f"{prefix}_noop"

    rows = [[_cbtn(f"📅 {MONTHS_RU[month - 1]} {year}", noop)]]
    rows.append([_cbtn(d, noop) for d in WEEKDAYS_RU])

    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(_cbtn(" ", noop))
                continue
            d = date(year, month, day)
            if d < today:
                row.append(_cbtn("·", noop))
            else:
                label = f"[{day}]" if d == today else str(day)
                row.append(_cbtn(label, f"{prefix}_day_{d.isoformat()}"))
        rows.append(row)

    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    months_from_now = (year - today.year) * 12 + (month - today.month)

    nav = [
        _cbtn("◀️", f"{prefix}_cal_{prev_y}-{prev_m:02d}") if months_from_now > 0 else _cbtn(" ", noop),
        _cbtn("▶️", f"{prefix}_cal_{next_y}-{next_m:02d}") if months_from_now < CALENDAR_MONTHS_AHEAD else _cbtn(" ", noop),
    ]
    rows.append(nav)
    return rows


def parse_cal_month(data: str):
    """'2026-07' -> (2026, 7) или None"""
    try:
        y, m = data.split("-")
        y, m = int(y), int(m)
        if 1 <= m <= 12 and 2000 <= y <= 2100:
            return y, m
    except ValueError:
        pass
    return None


def normalize_date(text: str):
    """Понимает: 25.07.2026, 25.07.26, 25.07, 2507, 250726, 25072026, 25/07, 25-07-2026.
    Если год не указан — берётся текущий (или следующий, если дата уже прошла).
    Возвращает 'ДД.ММ.ГГГГ' или None."""
    t = (text or "").strip().replace("/", ".").replace("-", ".").replace(" ", ".")
    d = m = y = None

    if re.fullmatch(r"\d{4}|\d{6}|\d{8}", t):
        d, m, y = t[:2], t[2:4], (t[4:] or None)
    else:
        mt = re.fullmatch(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2}|\d{4}))?", t)
        if not mt:
            return None
        d, m, y = mt.group(1), mt.group(2), mt.group(3)

    today = date.today()
    try:
        if y is None:
            result = date(today.year, int(m), int(d))
            if result < today:
                result = date(today.year + 1, int(m), int(d))
        else:
            year = int(y) + 2000 if len(y) == 2 else int(y)
            result = date(year, int(m), int(d))
    except ValueError:
        return None
    return result.strftime("%d.%m.%Y")


@router.callback_query(F.data.in_({"ag_noop", "eg_noop"}))
async def calendar_noop(callback: CallbackQuery):
    await callback.answer()


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
        "📆 Шаг 2. Выбери *дату* игры в календаре\n"
        "или напиши текстом: `25.07`, `2507` или `25.07.2026`",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=calendar_rows(date.today().year, date.today().month, "ag")
        )
    )
    await state.set_state(AddGameForm.enter_date)


async def _apply_date(message: Message, state: FSMContext, date_str: str):
    """date_str — уже нормализованная 'ДД.ММ.ГГГГ'. Переходит к выбору времени."""
    await state.update_data(date=date_str)
    await step(
        message, state,
        f"📆 Дата: *{date_str}*\n\n"
        "⏰ Шаг 3. Выбери *время* начала кнопкой\n"
        "или напиши своё в формате ЧЧ:ММ (например, `20:30`):",
        reply_markup=time_kb()
    )
    await state.set_state(AddGameForm.enter_time)


@router.callback_query(AddGameForm.enter_date, F.data.startswith("ag_cal_"))
async def ag_calendar_nav(callback: CallbackQuery, state: FSMContext):
    ym = parse_cal_month(callback.data.replace("ag_cal_", ""))
    if not ym:
        await callback.answer()
        return
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(inline_keyboard=calendar_rows(ym[0], ym[1], "ag"))
    )
    await callback.answer()


@router.callback_query(AddGameForm.enter_date, F.data.startswith("ag_day_"))
async def ag_calendar_day(callback: CallbackQuery, state: FSMContext):
    try:
        d = date.fromisoformat(callback.data.replace("ag_day_", ""))
    except ValueError:
        await callback.answer()
        return
    await _apply_date(callback.message, state, d.strftime("%d.%m.%Y"))
    await callback.answer()


@router.message(AddGameForm.enter_date)
async def ag_date(message: Message, state: FSMContext):
    date_str = normalize_date(message.text or "")
    await _safe_delete(message)

    if not date_str:
        await warn(message, state, "❌ Не понял дату. Выбери в календаре или напиши так: `25.07`, `2507` или `25.07.2026`")
        return
    await _apply_date(message, state, date_str)


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


# ═════════════════════════════════════════════════════════════════════════════
# РЕДАКТИРОВАНИЕ ИГРЫ
#   /edit_game ID                — показать поля кнопками
#   /edit_game ID Регистрация    — сразу открыть нужное поле
#   (разделитель " - " тоже работает: /edit_game 12 - Регистрация)
# ═════════════════════════════════════════════════════════════════════════════

class EditGameForm(StatesGroup):
    choose_field = State()
    edit_value   = State()


EDIT_FIELDS = [
    ("title",             "🎯 Название"),
    ("date",              "📆 Дата"),
    ("time",              "⏰ Время"),
    ("city",              "🏙 Город"),
    ("location",          "📍 Место"),
    ("price",             "💰 Цена"),
    ("registration_link", "🔗 Регистрация"),
    ("photo",             "🖼 Фото"),
]
FIELD_LABELS = dict(EDIT_FIELDS)

# Что можно написать в команде после ID (достаточно начала слова: «рег», «фот»)
FIELD_ALIASES = {
    "title":             ["название", "title"],
    "date":              ["дата", "date"],
    "time":              ["время", "time"],
    "city":              ["город", "city"],
    "location":          ["место", "локация", "location"],
    "price":             ["цена", "стоимость", "price"],
    "registration_link": ["регистрация", "ссылка", "registration", "link"],
    "photo":             ["фото", "картинка", "photo"],
}

CLEARABLE_FIELDS = {"location", "price", "registration_link", "photo"}

EDIT_PROMPTS = {
    "title":             "Напиши новое название игры:",
    "date":              "Выбери дату в календаре или напиши текстом (25.07, 2507 или 25.07.2026):",
    "time":              "Выбери время кнопкой или напиши своё в формате ЧЧ:ММ:",
    "city":              "Выбери новый город:",
    "location":          "Выбери место из списка, добавь новое или очисти поле:",
    "price":             "Напиши новую цену (например, 700 руб):",
    "registration_link": "Отправь новую ссылку на регистрацию (должна начинаться с http):",
    "photo":             "Отправь новое фото для игры:",
}


def _parse_edit_args(args: str):
    """'12 - Регистрация' -> (12, 'registration_link'); '12' -> (12, None);
    мусор -> (None, None). Если поле не распознано — (id, 'unknown')."""
    m = re.match(r"^(\d+)\s*(?:[-–—:]\s*)?(.*)$", args.strip())
    if not m:
        return None, None
    game_id = int(m.group(1))
    word = m.group(2).strip().lower()
    if not word:
        return game_id, None
    for key, aliases in FIELD_ALIASES.items():
        if any(a == word or a.startswith(word) for a in aliases):
            return game_id, key
    return game_id, "unknown"


def _split_date(date_str: str):
    """'25.07.2026 20:00' -> ('25.07.2026', '20:00'); без времени -> ('25.07.2026', None)"""
    parts = (date_str or "").split()
    d = parts[0] if parts else ""
    t = parts[1] if len(parts) > 1 else None
    return d, t


def _current_value(game: dict, field: str) -> str:
    d, t = _split_date(game["date"])
    return {
        "title":             game["title"],
        "date":              d,
        "time":              t,
        "city":              game["city"],
        "location":          game["location"],
        "price":             game["price"],
        "registration_link": game["registration_link"],
        "photo":             "✅ есть" if game["photo_id"] else None,
    }[field] or "—"


def game_card(g: dict) -> str:
    return (
        f"🆔 ID: {g['id']}\n"
        f"🎯 Название: {g['title']}\n"
        f"📆 Дата и время: {g['date']}\n"
        f"🏙 Город: {g['city'] or '—'}\n"
        f"📍 Место: {g['location'] or '—'}\n"
        f"💰 Цена: {g['price'] or '—'}\n"
        f"🔗 Регистрация: {g['registration_link'] or '—'}\n"
        f"🖼 Фото: {'✅ есть' if g['photo_id'] else '—'}"
    )


def _btn(text, cb):
    return InlineKeyboardButton(text=text, callback_data=cb)


def edit_fields_kb():
    rows, row = [], []
    for key, label in EDIT_FIELDS:
        row.append(_btn(label, f"eg_field_{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_btn("❌ Отмена", "eg_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def edit_value_kb(field: str, game: dict):
    rows = []
    if field == "date":
        # открываем календарь на месяце текущей даты игры (если он не в прошлом)
        today = date.today()
        y, m = today.year, today.month
        try:
            gd = datetime.strptime(_split_date(game["date"])[0], "%d.%m.%Y").date()
            if (gd.year, gd.month) > (y, m):
                y, m = gd.year, gd.month
        except ValueError:
            pass
        rows += calendar_rows(y, m, "eg")
    elif field == "time":
        rows.append([_btn(f"🕒 {t}", f"eg_time_{t}") for t in TIME_PRESETS])
    elif field == "city":
        rows += [[_btn(f"🏙 {c}", f"eg_city_{c}")] for c in CITIES]
    elif field == "location":
        venues = await get_venues(game["city"])
        rows += [[_btn(f"📍 {name}", f"eg_venue_{vid}")] for vid, name in venues]
        rows.append([_btn("➕ Новое место", "eg_venue_new")])
    if field in CLEARABLE_FIELDS:
        rows.append([_btn("🗑 Очистить поле", "eg_clear")])
    rows.append([_btn("◀️ К списку полей", "eg_back"), _btn("❌ Отмена", "eg_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_save_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✏️ Изменить ещё поле", "eg_back")],
        [_btn("✔️ Готово", "eg_done")],
    ])


async def _show_fields(message: Message, state: FSMContext):
    data = await state.get_data()
    game = await get_game_full(data["game_id"])
    if not game:
        await state.clear()
        await message.answer("❌ Игра не найдена (возможно, уже удалена).")
        return
    await step(
        message, state,
        f"✏️ Редактирование игры\n\n{game_card(game)}\n\nЧто изменить?",
        reply_markup=edit_fields_kb(), parse_mode=None
    )
    await state.set_state(EditGameForm.choose_field)


async def _open_field(message: Message, state: FSMContext, field: str):
    data = await state.get_data()
    game = await get_game_full(data["game_id"])
    if not game:
        await state.clear()
        await message.answer("❌ Игра не найдена (возможно, уже удалена).")
        return
    await state.update_data(field=field)
    await step(
        message, state,
        f"✏️ Игра ID {game['id']} — {game['title']}\n"
        f"{FIELD_LABELS[field]}\n"
        f"Сейчас: {_current_value(game, field)}\n\n"
        f"{EDIT_PROMPTS[field]}",
        reply_markup=await edit_value_kb(field, game), parse_mode=None
    )
    await state.set_state(EditGameForm.edit_value)


async def _save(message: Message, state: FSMContext, **fields):
    data = await state.get_data()
    game_id = data["game_id"]
    ok = await update_game(game_id, **fields)
    if not ok:
        await state.clear()
        await message.answer("❌ Игра не найдена (возможно, уже удалена).")
        return
    game = await get_game_full(game_id)
    await step(
        message, state,
        f"✅ Сохранено!\n\n{game_card(game)}",
        reply_markup=after_save_kb(), parse_mode=None
    )
    await state.set_state(EditGameForm.choose_field)


# ─── СТАРТ ────────────────────────────────────────────────────────────────────

@router.message(Command("edit_game"))
async def cmd_edit_game(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    parts = (message.text or "").split(maxsplit=1)
    game_id, field = _parse_edit_args(parts[1] if len(parts) > 1 else "")

    if game_id is None:
        await message.answer(
            "📝 Формат:\n"
            "/edit_game ID — выбрать поле кнопками\n"
            "/edit_game ID Регистрация — сразу изменить нужное поле\n\n"
            "Поля: название, дата, время, город, место, цена, регистрация, фото.\n"
            "ID узнать через /list_games"
        )
        return

    if field == "unknown":
        await message.answer(
            "❌ Не понял, какое поле менять.\n"
            "Доступно: название, дата, время, город, место, цена, регистрация, фото."
        )
        return

    if not await get_game_full(game_id):
        await message.answer(f"❌ Игра с ID {game_id} не найдена.")
        return

    await state.clear()
    await _safe_delete(message)
    await state.update_data(game_id=game_id)

    if field:
        await _open_field(message, state, field)
    else:
        await _show_fields(message, state)


@router.message(Command("stop"), StateFilter(EditGameForm))
async def eg_stop(message: Message, state: FSMContext):
    data = await state.get_data()
    await _delete_by_id(message.bot, message.chat.id, data.get("prompt_id"))
    await _delete_by_id(message.bot, message.chat.id, data.get("warn_id"))
    await state.clear()
    await _safe_delete(message)
    await message.answer("🛑 Редактирование отменено.")


# ─── НАВИГАЦИЯ ────────────────────────────────────────────────────────────────

@router.callback_query(StateFilter(EditGameForm), F.data == "eg_cancel")
async def eg_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Редактирование отменено.")
    await callback.answer()


@router.callback_query(StateFilter(EditGameForm), F.data == "eg_done")
async def eg_done(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Готово")


@router.callback_query(StateFilter(EditGameForm), F.data == "eg_back")
async def eg_back(callback: CallbackQuery, state: FSMContext):
    await _show_fields(callback.message, state)
    await callback.answer()


@router.callback_query(EditGameForm.choose_field, F.data.startswith("eg_field_"))
async def eg_field_chosen(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("eg_field_", "")
    if field not in FIELD_LABELS:
        await callback.answer("Неизвестное поле", show_alert=True)
        return
    await _open_field(callback.message, state, field)
    await callback.answer()


# ─── ЗНАЧЕНИЯ КНОПКАМИ ────────────────────────────────────────────────────────

async def _apply_date_edit(message: Message, state: FSMContext, date_str: str):
    """date_str — нормализованная 'ДД.ММ.ГГГГ'."""
    data = await state.get_data()
    game = await get_game_full(data["game_id"])
    if not game:
        await state.clear()
        await message.answer("❌ Игра не найдена (возможно, уже удалена).")
        return
    _, t = _split_date(game["date"])
    if not t:
        await warn(message, state, "❌ У игры не указано время — сначала измени поле «Время».")
        return
    iso = parse_game_datetime(date_str, t)
    if iso is None:
        await warn(message, state, "❌ Неверная дата.")
        return
    await _save(message, state, date=f"{date_str} {t}", event_datetime=iso)


@router.callback_query(EditGameForm.edit_value, F.data.startswith("eg_cal_"))
async def eg_calendar_nav(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ym = parse_cal_month(callback.data.replace("eg_cal_", ""))
    if data.get("field") != "date" or not ym:
        await callback.answer()
        return
    rows = calendar_rows(ym[0], ym[1], "eg") + [
        [_btn("◀️ К списку полей", "eg_back"), _btn("❌ Отмена", "eg_cancel")]
    ]
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(EditGameForm.edit_value, F.data.startswith("eg_day_"))
async def eg_calendar_day(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("field") != "date":
        await callback.answer()
        return
    try:
        d = date.fromisoformat(callback.data.replace("eg_day_", ""))
    except ValueError:
        await callback.answer()
        return
    await _apply_date_edit(callback.message, state, d.strftime("%d.%m.%Y"))
    await callback.answer()


async def _apply_time_edit(message: Message, state: FSMContext, time_str: str):
    data = await state.get_data()
    game = await get_game_full(data["game_id"])
    if not game:
        await state.clear()
        await message.answer("❌ Игра не найдена (возможно, уже удалена).")
        return
    d, _ = _split_date(game["date"])
    iso = parse_game_datetime(d, time_str)
    if iso is None:
        await warn(message, state, "❌ Неверный формат времени. Введи как ЧЧ:ММ\nПример: `20:00`")
        return
    await _save(message, state, date=f"{d} {iso[11:16]}", event_datetime=iso)


@router.callback_query(EditGameForm.edit_value, F.data.startswith("eg_time_"))
async def eg_time_button(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("field") != "time":
        await callback.answer()
        return
    await _apply_time_edit(callback.message, state, callback.data.replace("eg_time_", ""))
    await callback.answer()


@router.callback_query(EditGameForm.edit_value, F.data.startswith("eg_city_"))
async def eg_city_button(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    city = callback.data.replace("eg_city_", "")
    if data.get("field") != "city" or city not in CITIES:
        await callback.answer("Выбери город из списка", show_alert=True)
        return
    await _save(callback.message, state, city=city)
    await callback.answer()


@router.callback_query(EditGameForm.edit_value, F.data == "eg_venue_new")
async def eg_venue_new(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("field") != "location":
        await callback.answer()
        return
    game = await get_game_full(data["game_id"])
    await step(
        callback.message, state,
        "📍 Напиши название нового места "
        f"(оно сохранится в список для города {game['city'] or '—'}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("◀️ К списку полей", "eg_back"), _btn("❌ Отмена", "eg_cancel")]
        ]),
        parse_mode=None
    )
    await callback.answer()


@router.callback_query(EditGameForm.edit_value, F.data.startswith("eg_venue_"))
async def eg_venue_chosen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    venue_id = callback.data.replace("eg_venue_", "")
    name = await get_venue_name(int(venue_id)) if venue_id.isdigit() else None
    if data.get("field") != "location" or not name:
        await callback.answer("Место не найдено, выбери другое.", show_alert=True)
        return
    await _save(callback.message, state, location=name)
    await callback.answer()


@router.callback_query(EditGameForm.edit_value, F.data == "eg_clear")
async def eg_clear(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    field = data.get("field")
    if field not in CLEARABLE_FIELDS:
        await callback.answer("Это поле нельзя очистить", show_alert=True)
        return
    column = "photo_id" if field == "photo" else field
    await _save(callback.message, state, **{column: ""})
    await callback.answer("🗑 Очищено")


# ─── ЗНАЧЕНИЯ ТЕКСТОМ / ФОТО ──────────────────────────────────────────────────

@router.message(EditGameForm.edit_value, F.photo)
async def eg_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("field") != "photo":
        await _safe_delete(message)
        await warn(message, state, "❌ Здесь нужен текст, а не фото.")
        return
    photo_id = message.photo[-1].file_id
    await _safe_delete(message)
    await _save(message, state, photo_id=photo_id)


@router.message(EditGameForm.edit_value)
async def eg_text_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("field")
    value = (message.text or "").strip()
    await _safe_delete(message)

    if not value:
        await warn(message, state, "❌ Отправь значение текстом.")
        return

    if field == "title":
        await _save(message, state, title=value)

    elif field == "date":
        date_str = normalize_date(value)
        if not date_str:
            await warn(message, state, "❌ Не понял дату. Выбери в календаре или напиши так: `25.07`, `2507` или `25.07.2026`")
            return
        await _apply_date_edit(message, state, date_str)

    elif field == "time":
        await _apply_time_edit(message, state, value)

    elif field == "location":
        game = await get_game_full(data["game_id"])
        if game["city"]:
            await add_venue(game["city"], value)   # новое место попадёт в список кнопок
        await _save(message, state, location=value)

    elif field == "price":
        await _save(message, state, price=value)

    elif field == "registration_link":
        # Ссылка вставляется в HTML/Markdown-разметку, поэтому без пробелов и кавычек
        if not re.match(r"^https?://[^\s\"'<>()\[\]]+$", value):
            await warn(message, state, "❌ Нужна корректная ссылка, начинающаяся с http:// или https:// (без пробелов).")
            return
        await _save(message, state, registration_link=value)

    elif field == "city":
        await warn(message, state, "❌ Город выбирается кнопкой.")

    elif field == "photo":
        await warn(message, state, "❌ Отправь именно фото (не текст) или нажми «Очистить поле».")


# Форма устарела (например, бот перезапускался и состояние потеряно)
@router.callback_query(F.data.startswith("eg_"))
async def eg_stale(callback: CallbackQuery):
    await callback.answer("Форма устарела. Запусти /edit_game ID заново.", show_alert=True)
