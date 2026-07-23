# handlers/start.py — главное меню бота

from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

router = Router()


def main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Предстоящие игры"),    KeyboardButton(text="🏅 Лидеры месяца")],
            [KeyboardButton(text="❓ FAQ"),                  KeyboardButton(text="📞 Контакты")],
            [KeyboardButton(text="📖 Правила"),              KeyboardButton(text="🎯 Попробуй свои силы")],
            [KeyboardButton(text="🔔 Подписка на игры"),     KeyboardButton(text="😂 Мем дня")],
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
        "🏅 Лидеры месяца\n"
        "❓ Ответы на частые вопросы\n"
        "📞 Контакты и соцсети\n\n"
        "Выбери что тебя интересует 👇",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )
