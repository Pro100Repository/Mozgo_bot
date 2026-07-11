# handlers/admin_results.py — FSM-форма введення результатів ігор

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from database.db import (
    RESULT_CITIES, RESULT_GAME_TYPES,
    add_game_result, get_game_result, update_game_result,
    delete_game_result, list_game_results
)

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── FSM ─────────────────────────────────────────────────────────────────────

class AddResultForm(StatesGroup):
    choose_city      = State()
    choose_game_type = State()
    enter_game_name  = State()
    enter_place1     = State()
    enter_place1_photo = State()
    enter_place2     = State()
    enter_place2_photo = State()
    enter_place3     = State()
    enter_place3_photo = State()


class EditResultForm(StatesGroup):
    choose_field  = State()
    enter_value   = State()
    enter_photo   = State()


# ─── КЛАВІАТУРИ ──────────────────────────────────────────────────────────────

def cities_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🏙 {c}", callback_data=f"ar_city_{c}")]
        for c in RESULT_CITIES
    ])


def game_types_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"ar_type_{key}")]
        for key, label in RESULT_GAME_TYPES.items()
    ])


def skip_photo_kb(next_cb: str):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Пропустить фото", callback_data=next_cb)
    ]])


# ─── ДОДАВАННЯ РЕЗУЛЬТАТУ ─────────────────────────────────────────────────────

@router.message(Command("add_result_new"))
async def cmd_add_result_new(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    await state.clear()
    await message.answer(
        "🏆 *Добавление результата игры*\n\nШаг 1. Выбери город:",
        reply_markup=cities_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(AddResultForm.choose_city)


@router.callback_query(AddResultForm.choose_city, F.data.startswith("ar_city_"))
async def ar_city_chosen(callback: CallbackQuery, state: FSMContext):
    city = callback.data.replace("ar_city_", "")
    await state.update_data(city=city)
    await callback.message.edit_text(
        f"🏙 Город: *{city}*\n\nШаг 2. Выбери тип игры:",
        reply_markup=game_types_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(AddResultForm.choose_game_type)
    await callback.answer()


@router.callback_query(AddResultForm.choose_game_type, F.data.startswith("ar_type_"))
async def ar_type_chosen(callback: CallbackQuery, state: FSMContext):
    game_type = callback.data.replace("ar_type_", "")
    game_label = RESULT_GAME_TYPES[game_type]
    await state.update_data(game_type=game_type, game_label=game_label)
    await callback.message.edit_text(
        f"🎮 Тип: *{game_label}*\n\nШаг 3. Напиши *название игры*:\n\n"
        "Пример: _Танці в большом городе_",
        parse_mode="Markdown"
    )
    await state.set_state(AddResultForm.enter_game_name)
    await callback.answer()


@router.message(AddResultForm.enter_game_name)
async def ar_game_name(message: Message, state: FSMContext):
    await state.update_data(game_name=message.text.strip())
    await message.answer(
        "🥇 Шаг 4. Напиши название команды, занявшей *1 место*:",
        parse_mode="Markdown"
    )
    await state.set_state(AddResultForm.enter_place1)


@router.message(AddResultForm.enter_place1)
async def ar_place1(message: Message, state: FSMContext):
    team = message.text.strip()
    await state.update_data(place1_team=team)
    await message.answer(
        f"🥇 1 место: *{team}*\n\n"
        "Отправь фото для этой команды или нажми «Пропустить»:",
        reply_markup=skip_photo_kb("ar_skip_photo1"),
        parse_mode="Markdown"
    )
    await state.set_state(AddResultForm.enter_place1_photo)


@router.message(AddResultForm.enter_place1_photo, F.photo)
async def ar_place1_photo(message: Message, state: FSMContext):
    await state.update_data(place1_photo=message.photo[-1].file_id)
    await ask_place2(message, state)


@router.callback_query(AddResultForm.enter_place1_photo, F.data == "ar_skip_photo1")
async def ar_skip_photo1(callback: CallbackQuery, state: FSMContext):
    await state.update_data(place1_photo="")
    await ask_place2(callback.message, state)
    await callback.answer()


async def ask_place2(message: Message, state: FSMContext):
    await message.answer(
        "🥈 Шаг 5. Напиши название команды, занявшей *2 место*\n"
        "или /skip чтобы пропустить:",
        parse_mode="Markdown"
    )
    await state.set_state(AddResultForm.enter_place2)


@router.message(AddResultForm.enter_place2, F.text == "/skip")
@router.message(AddResultForm.enter_place2, F.text.lower() == "пропустить")
async def ar_skip_place2(message: Message, state: FSMContext):
    await state.update_data(place2_team="", place2_photo="")
    await ask_place3(message, state)


@router.message(AddResultForm.enter_place2)
async def ar_place2(message: Message, state: FSMContext):
    team = message.text.strip()
    await state.update_data(place2_team=team)
    await message.answer(
        f"🥈 2 место: *{team}*\n\n"
        "Отправь фото или нажми «Пропустить»:",
        reply_markup=skip_photo_kb("ar_skip_photo2"),
        parse_mode="Markdown"
    )
    await state.set_state(AddResultForm.enter_place2_photo)


@router.message(AddResultForm.enter_place2_photo, F.photo)
async def ar_place2_photo(message: Message, state: FSMContext):
    await state.update_data(place2_photo=message.photo[-1].file_id)
    await ask_place3(message, state)


@router.callback_query(AddResultForm.enter_place2_photo, F.data == "ar_skip_photo2")
async def ar_skip_photo2(callback: CallbackQuery, state: FSMContext):
    await state.update_data(place2_photo="")
    await ask_place3(callback.message, state)
    await callback.answer()


async def ask_place3(message: Message, state: FSMContext):
    await message.answer(
        "🥉 Шаг 6. Напиши название команды, занявшей *3 место*\n"
        "или /skip чтобы пропустить:",
        parse_mode="Markdown"
    )
    await state.set_state(AddResultForm.enter_place3)


@router.message(AddResultForm.enter_place3, F.text == "/skip")
@router.message(AddResultForm.enter_place3, F.text.lower() == "пропустить")
async def ar_skip_place3(message: Message, state: FSMContext):
    await state.update_data(place3_team="", place3_photo="")
    await save_result(message, state)


@router.message(AddResultForm.enter_place3)
async def ar_place3(message: Message, state: FSMContext):
    team = message.text.strip()
    await state.update_data(place3_team=team)
    await message.answer(
        f"🥉 3 место: *{team}*\n\n"
        "Отправь фото или нажми «Пропустить»:",
        reply_markup=skip_photo_kb("ar_skip_photo3"),
        parse_mode="Markdown"
    )
    await state.set_state(AddResultForm.enter_place3_photo)


@router.message(AddResultForm.enter_place3_photo, F.photo)
async def ar_place3_photo(message: Message, state: FSMContext):
    await state.update_data(place3_photo=message.photo[-1].file_id)
    await save_result(message, state)


@router.callback_query(AddResultForm.enter_place3_photo, F.data == "ar_skip_photo3")
async def ar_skip_photo3(callback: CallbackQuery, state: FSMContext):
    await state.update_data(place3_photo="")
    await save_result(callback.message, state)
    await callback.answer()


async def save_result(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    result_id = await add_game_result(
        city        = data["city"],
        game_type   = data["game_type"],
        game_name   = data["game_name"],
        place1_team = data.get("place1_team", ""),
        place1_photo= data.get("place1_photo", ""),
        place2_team = data.get("place2_team", ""),
        place2_photo= data.get("place2_photo", ""),
        place3_team = data.get("place3_team", ""),
        place3_photo= data.get("place3_photo", ""),
    )

    p1 = data.get("place1_team") or "—"
    p2 = data.get("place2_team") or "—"
    p3 = data.get("place3_team") or "—"

    await message.answer(
        f"✅ Результат сохранён! ID: `{result_id}`\n\n"
        f"🏙 Город: {data['city']}\n"
        f"🎮 Игра: {data['game_label']} — {data['game_name']}\n"
        f"🥇 1 место: {p1}\n"
        f"🥈 2 место: {p2}\n"
        f"🥉 3 место: {p3}\n\n"
        f"Для редактирования: /edit_result {result_id}",
        parse_mode="Markdown"
    )


# ─── РЕДАГУВАННЯ РЕЗУЛЬТАТУ ───────────────────────────────────────────────────

@router.message(Command("edit_result"))
async def cmd_edit_result(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    args = message.text.replace("/edit_result", "").strip()
    if not args or not args.isdigit():
        await message.answer(
            "Формат: `/edit_result ID`\n"
            "ID узнать через /list_results",
            parse_mode="Markdown"
        )
        return

    result_id = int(args)
    row = await get_game_result(result_id)
    if not row:
        await message.answer(f"❌ Результат с ID {result_id} не найден.")
        return

    await state.update_data(edit_id=result_id)

    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏙 Город",         callback_data="er_field_city")],
        [InlineKeyboardButton(text="🎮 Тип игры",      callback_data="er_field_game_type")],
        [InlineKeyboardButton(text="📝 Название игры", callback_data="er_field_game_name")],
        [InlineKeyboardButton(text="🥇 1 место (команда)", callback_data="er_field_place1_team")],
        [InlineKeyboardButton(text="🥇 1 место (фото)",    callback_data="er_field_place1_photo")],
        [InlineKeyboardButton(text="🥈 2 место (команда)", callback_data="er_field_place2_team")],
        [InlineKeyboardButton(text="🥈 2 место (фото)",    callback_data="er_field_place2_photo")],
        [InlineKeyboardButton(text="🥉 3 место (команда)", callback_data="er_field_place3_team")],
        [InlineKeyboardButton(text="🥉 3 место (фото)",    callback_data="er_field_place3_photo")],
    ])

    _, city, gtype, gname, p1t, p1p, p2t, p2p, p3t, p3p, created = row
    await message.answer(
        f"✏️ *Редактирование результата ID {result_id}*\n\n"
        f"🏙 {city} | {RESULT_GAME_TYPES.get(gtype, gtype)} | {gname}\n"
        f"🥇 {p1t or '—'} {'📷' if p1p else ''}\n"
        f"🥈 {p2t or '—'} {'📷' if p2p else ''}\n"
        f"🥉 {p3t or '—'} {'📷' if p3p else ''}\n\n"
        "Что хочешь изменить?",
        reply_markup=buttons,
        parse_mode="Markdown"
    )
    await state.set_state(EditResultForm.choose_field)


@router.callback_query(EditResultForm.choose_field, F.data.startswith("er_field_"))
async def er_field_chosen(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("er_field_", "")
    await state.update_data(edit_field=field)

    if field.endswith("_photo"):
        await callback.message.answer(
            "📷 Отправь новое фото или /skip чтобы очистить фото:"
        )
        await state.set_state(EditResultForm.enter_photo)
    elif field == "city":
        await callback.message.answer(
            "🏙 Выбери новый город:",
            reply_markup=cities_kb()
        )
        await state.set_state(EditResultForm.enter_value)
    elif field == "game_type":
        await callback.message.answer(
            "🎮 Выбери новый тип игры:",
            reply_markup=game_types_kb()
        )
        await state.set_state(EditResultForm.enter_value)
    else:
        await callback.message.answer("✏️ Введи новое значение:")
        await state.set_state(EditResultForm.enter_value)

    await callback.answer()


@router.message(EditResultForm.enter_value)
async def er_enter_value(message: Message, state: FSMContext):
    data = await state.get_data()
    await update_game_result(data["edit_id"], **{data["edit_field"]: message.text.strip()})
    await state.clear()
    await message.answer("✅ Обновлено!")


@router.callback_query(EditResultForm.enter_value)
async def er_enter_value_cb(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    field = data["edit_field"]
    # Для city і game_type — отримуємо значення з callback_data
    if field == "city":
        value = callback.data.replace("ar_city_", "")
    elif field == "game_type":
        value = callback.data.replace("ar_type_", "")
    else:
        await callback.answer()
        return
    await update_game_result(data["edit_id"], **{field: value})
    await state.clear()
    await callback.message.answer(f"✅ Обновлено: {value}")
    await callback.answer()


@router.message(EditResultForm.enter_photo, F.photo)
async def er_enter_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await update_game_result(data["edit_id"], **{data["edit_field"]: message.photo[-1].file_id})
    await state.clear()
    await message.answer("✅ Фото обновлено!")


@router.message(EditResultForm.enter_photo, F.text == "/skip")
async def er_clear_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await update_game_result(data["edit_id"], **{data["edit_field"]: ""})
    await state.clear()
    await message.answer("✅ Фото удалено.")


# ─── СПИСОК І ВИДАЛЕННЯ ───────────────────────────────────────────────────────

@router.message(Command("list_results"))
async def cmd_list_results(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    rows = await list_game_results(limit=20)
    if not rows:
        await message.answer("📭 Результатов пока нет.")
        return

    text = "📋 *Последние результаты:*\n\n"
    for r in rows:
        rid, city, gtype, gname, p1, p2, p3, created = r
        text += (f"ID `{rid}` | {city} | {RESULT_GAME_TYPES.get(gtype, gtype)}\n"
                 f"   {gname}\n"
                 f"   🥇{p1 or '—'} 🥈{p2 or '—'} 🥉{p3 or '—'}\n\n")

    text += "Редактировать: `/edit_result ID`\nУдалить: `/del_result ID`"
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("del_result"))
async def cmd_del_result(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    args = message.text.replace("/del_result", "").strip()
    if not args or not args.isdigit():
        await message.answer("Формат: `/del_result ID`", parse_mode="Markdown")
        return

    deleted = await delete_game_result(int(args))
    if deleted:
        await message.answer(f"✅ Результат ID {args} удалён.")
    else:
        await message.answer(f"❌ Не найден.")
