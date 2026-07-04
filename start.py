# handlers/start.py — главное меню бота

from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

router = Router()


def main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Предстоящие игры"),  KeyboardButton(text="🏅 Рейтинг команд")],
            [KeyboardButton(text="❓ FAQ"),                KeyboardButton(text="📞 Контакты")],
            [KeyboardButton(text="🎯 Попробуй свои силы")],
        ],
        resize_keyboard=True
    )
    return keyboard


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я бот квиз-сообщества *Мзгб*. Здесь ты найдёшь:\n"
        "📅 Предстоящие игры\n"
        "🏅 Рейтинг команд\n"
        "❓ Ответы на частые вопросы\n"
        "📞 Контакты и соцсети\n\n"
        "Выбери что тебя интересует 👇",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )
