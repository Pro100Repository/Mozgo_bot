# handlers/admin_broadcast.py — FSM-форма розсилки повідомлення підписникам обраних міст

import asyncio
import html

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import ADMIN_IDS
from database.db import RESULT_CITIES, get_city_subscribers, remove_subscriber

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── FSM ─────────────────────────────────────────────────────────────────────

class BroadcastForm(StatesGroup):
    choose_cities = State()
    enter_text    = State()
    confirm       = State()


ALL_KEY = "__all__"


# ─── КЛАВІАТУРИ ──────────────────────────────────────────────────────────────

def cities_kb(selected: set) -> InlineKeyboardMarkup:
    """Мультивибір міст з чекбоксами + кнопка «Всі» + «Готово»."""
    all_selected = len(selected) == len(RESULT_CITIES)

    buttons = []
    for city in RESULT_CITIES:
        icon = "✅" if city in selected else "☐"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {city}",
            callback_data=f"bc_city_{city}"
        )])

    all_icon = "✅" if all_selected else "☐"
    buttons.append([InlineKeyboardButton(
        text=f"{all_icon} Все города",
        callback_data=f"bc_city_{ALL_KEY}"
    )])
    buttons.append([InlineKeyboardButton(text="➡️ Далее", callback_data="bc_cities_done")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="bc_cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Отправить", callback_data="bc_confirm")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="bc_cancel")],
    ])


# ─── СТАРТ ФОРМИ ─────────────────────────────────────────────────────────────

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    await state.clear()
    await state.update_data(cities=[])
    await message.answer(
        "📨 *Рассылка сообщения подписчикам*\n\n"
        "Шаг 1. Выбери город(а), кому отправить сообщение "
        "(можно несколько или «Все города»):",
        reply_markup=cities_kb(set()),
        parse_mode="Markdown"
    )
    await state.set_state(BroadcastForm.choose_cities)


@router.callback_query(BroadcastForm.choose_cities, F.data.startswith("bc_city_"))
async def bc_toggle_city(callback: CallbackQuery, state: FSMContext):
    key = callback.data.replace("bc_city_", "")
    data = await state.get_data()
    selected = set(data.get("cities", []))

    if key == ALL_KEY:
        # Перемикач "усі": якщо вже всі обрані — знімаємо всі, інакше обираємо всі
        if len(selected) == len(RESULT_CITIES):
            selected = set()
        else:
            selected = set(RESULT_CITIES)
    else:
        if key in selected:
            selected.discard(key)
        else:
            selected.add(key)

    await state.update_data(cities=list(selected))
    await callback.message.edit_reply_markup(reply_markup=cities_kb(selected))
    await callback.answer()


@router.callback_query(BroadcastForm.choose_cities, F.data == "bc_cities_done")
async def bc_cities_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("cities", [])

    if not selected:
        await callback.answer("⚠️ Выбери хотя бы один город.", show_alert=True)
        return

    cities_text = "Все города" if len(selected) == len(RESULT_CITIES) else ", ".join(selected)
    await callback.message.edit_text(
        f"🏙 Города: *{cities_text}*\n\n"
        "Шаг 2. Напиши текст сообщения, которое получат подписчики "
        "(поддерживается *Markdown*-разметка):",
        parse_mode="Markdown"
    )
    await state.set_state(BroadcastForm.enter_text)
    await callback.answer()


@router.message(BroadcastForm.enter_text)
async def bc_enter_text(message: Message, state: FSMContext):
    await state.update_data(text=message.html_text)
    data = await state.get_data()
    selected = data.get("cities", [])
    cities_text = "Все города" if len(selected) == len(RESULT_CITIES) else ", ".join(selected)

    await message.answer(
        f"📋 *Проверь сообщение перед отправкой*\n\n"
        f"🏙 Города: {cities_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{message.html_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        "Отправить это сообщение подписчикам выбранных городов?",
        reply_markup=confirm_kb(),
        parse_mode="HTML"
    )
    await state.set_state(BroadcastForm.confirm)


@router.callback_query(BroadcastForm.confirm, F.data == "bc_confirm")
async def bc_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    selected_cities = data.get("cities", [])
    text = data.get("text", "")

    # Збираємо унікальних підписників по всіх обраних містах
    user_ids = set()
    for city in selected_cities:
        subs = await get_city_subscribers(city)
        user_ids.update(subs)

    if not user_ids:
        await callback.message.edit_text("ℹ️ Подписчиков в выбранных городах пока нет.")
        await callback.answer()
        return

    await callback.message.edit_text(f"📨 Отправляю сообщение {len(user_ids)} подписчикам...")

    sent = 0
    failed = 0
    for user_id in user_ids:
        try:
            await callback.bot.send_message(user_id, text, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            await remove_subscriber(user_id)
            failed += 1
        except TelegramBadRequest:
            failed += 1
        except Exception:
            failed += 1

    result_text = f"✅ Рассылка завершена!\n\n📨 Доставлено: {sent}"
    if failed:
        result_text += f"\n⚠️ Не доставлено: {failed} (бот заблокирован или ошибка)"

    await callback.message.answer(result_text)
    await callback.answer()


@router.callback_query(F.data == "bc_cancel")
async def bc_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена.")
    await callback.answer()
