# handlers/start.py — главное меню бота

from aiogram import Router, F
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart

router = Router()

# ─── ФОТОАЛЬБОМЫ ПО ГОРОДАМ ──────────────────────────────────────────────────
# Замени ссылки на реальные фотоальбомы в соцсетях для каждого города.
PHOTO_ALBUMS = {
    "Москва":       "https://vk.ru/albums-126335374",
    "Красногорск":  "https://vk.ru/albums-163158280",
    "Истра":        "https://vk.ru/albums-167360648",
    "Обнинск":      "https://vk.ru/albums-167360403",
}


def photo_albums_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🏙 {city}", url=link)]
        for city, link in PHOTO_ALBUMS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Предстоящие игры"),     KeyboardButton(text="📖 Правила")],
            [KeyboardButton(text="🎉 Акции"),                KeyboardButton(text="❓ FAQ")],
            [KeyboardButton(text="📸 Фотоальбомы"),          KeyboardButton(text="📞 Контакты")],
            [KeyboardButton(text="🎯 Попробуй свои силы"),   KeyboardButton(text="🏅 Лидеры месяца")],
            [KeyboardButton(text="😂 Мем недели"),           KeyboardButton(text="🔔 Подписка на игры")],
        ],
        resize_keyboard=True
    )
    return keyboard


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я бот квиз-сообщества *Ruda Games*. Здесь ты найдёшь:\n"
        "📅 Игры • 📖 Правила • 🎉 Акции \n"
        "❓ FAQ • 📸 Фотоальбомы  \n"
        "📞 Контакты • 🎯 Квиз \n"
        "🏅 Рейтинг • 🔔 Подписка на игры и мемы\n\n"        
        "Выбери что тебя интересует 👇",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


@router.message(F.text == "🎉 Акции")
async def show_promotions(message: Message):
    await message.answer(
        "🎉 <b>Акции и бонусы</b>\n\n"
        "🎂 <b>Именинникам - подарок!</b>\n\n"
        "Если ваш день рождения выпадает на понедельник–воскресенье той недели,"
        "в которую проходит игра, вы играете бесплатно.\n\n"
        "Для участия в акции предъявите паспорт администратору на игре.",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.message(F.text == "📸 Фотоальбомы")
async def show_photo_albums(message: Message):
    await message.answer(
        "📸 <b>Фотоальбомы с игр</b>\n\n"
        "Выбери город, чтобы перейти к альбому в нашей группе в ВК 👇",
        reply_markup=photo_albums_kb(),
        parse_mode="HTML"
    )

