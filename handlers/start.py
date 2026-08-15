# handlers/start.py — главное меню бота

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

router = Router()


def main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Предстоящие игры"),     KeyboardButton(text="📖 Правила")],
            [KeyboardButton(text="🎉 Акции"),                KeyboardButton(text="❓ FAQ")],
            [KeyboardButton(text="🎯 Попробуй свои силы"),   KeyboardButton(text="📞 Контакты")],
            [KeyboardButton(text="🏅 Лидеры месяца"),        KeyboardButton(text="😂 Мем дня")],
            [KeyboardButton(text="🔔 Подписка на игры")],
        ],
        resize_keyboard=True
    )
    return keyboard


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я бот квиз-сообщества *Ruda Games*. Здесь ты найдёшь:\n"
        "📅 Игры • 🎉 Акции • 📖 Правила\n"
        "🏅 Рейтинг • ❓ FAQ • 📞 Контакты\n"
        "🎯 Квиз • 🔔 Подписка на игры\n\n"        
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

