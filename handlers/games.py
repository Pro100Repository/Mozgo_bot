# handlers/games.py — предстоящие игры с фильтром по городу (кнопки), фото и результаты

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from database.db import get_games_by_city, get_results

router = Router()

# ──────────────────────────────────────────
# СПИСОК ГОРОДОВ — редактируй этот список под себя
# ──────────────────────────────────────────
CITIES = ["Москва", "Красногорск", "Истра", "Обнинск"]
# ──────────────────────────────────────────


def escape_html(text: str) -> str:
    """Экранирует спецсимволы HTML, чтобы не сломать разметку"""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cities_keyboard():
    """Кнопки с городами из списка CITIES"""
    buttons = [
        [InlineKeyboardButton(text=f"🏙 {city}", callback_data=f"city_{city}")]
        for city in CITIES
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_cities_keyboard():
    """Кнопка возврата к выбору города"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад к выбору города", callback_data="city_back")
    ]])


def build_game_text(title, date, location, registration_link):
    text = f"🎯 {escape_html(title)}\n"
    text += f"📆 Дата: {escape_html(date)}\n"
    if location:
        text += f"📍 Место: {escape_html(location)}\n"
    if registration_link:
        text += f'📝 <a href="{registration_link}">Регистрация</a>\n'
    return text


# ─── ПРЕДСТОЯЩИЕ ИГРЫ ───────────────────

@router.message(F.text == "📅 Предстоящие игры")
async def ask_city(message: Message):
    await message.answer(
        "🏙 Выберите город:",
        reply_markup=cities_keyboard()
    )


@router.callback_query(F.data.startswith("city_"))
async def city_chosen(callback: CallbackQuery):
    city = callback.data.replace("city_", "")

    # Обработка кнопки "Назад"
    if city == "back":
        await callback.message.edit_text(
            "🏙 Выберите город:",
            reply_markup=cities_keyboard()
        )
        await callback.answer()
        return

    games = await get_games_by_city(city)

    if not games:
        await callback.message.edit_text(
            f"📭 В городе «{city}» предстоящих игр нет.\n"
            "Следи за обновлениями!",
            reply_markup=back_to_cities_keyboard()
        )
        await callback.answer()
        return

    # Разделяем игры на те, у которых есть фото, и те, у которых нет
    games_with_photo = [g for g in games if g[4]]   # photo_id на 5-й позиции
    games_without_photo = [g for g in games if not g[4]]

    # Сначала убираем старое сообщение со списком городов
    await callback.message.delete()

    # Игры без фото — одним текстовым сообщением
    if games_without_photo:
        text = f"📅 Игры в городе «{city}»:\n\n"
        for title, date, location, registration_link, _ in games_without_photo:
            text += build_game_text(title, date, location, registration_link) + "\n"
        await callback.message.answer(text, parse_mode="HTML")

    # Игры с фото — отдельным сообщением-фото на каждую игру
    for title, date, location, registration_link, photo_id in games_with_photo:
        caption = build_game_text(title, date, location, registration_link)
        await callback.message.answer_photo(
            photo=photo_id,
            caption=caption,
            parse_mode="HTML"
        )

    # Кнопка "Назад" отдельным сообщением в конце
    await callback.message.answer(
        "Хочешь посмотреть игры в другом городе?",
        reply_markup=back_to_cities_keyboard()
    )
    await callback.answer()


# ─── РЕЗУЛЬТАТЫ ИГР ─────────────────────

@router.message(F.text == "🏆 Результаты игр")
async def show_results(message: Message):
    results = await get_results(limit=10)

    if not results:
        await message.answer(
            "📭 Результатов пока нет.\n"
            "После первой игры здесь появятся итоги!"
        )
        return

    text = "🏆 Результаты последних игр:\n\n"
    current_game = None

    for row in results:
        game_title, game_date, team_name, place, score = row
        if current_game != game_title:
            current_game = game_title
            text += f"🎮 {game_title} ({game_date})\n"
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(place, f"{place}.")
        text += f"  {medal} {team_name} — {score} баллов\n"

    await message.answer(text)
