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
        "📅 Предстоящие игры\n"
        "🎉 Акции\n"
        "📖 Правила\n"
        "🏅 Лидеров месяца\n"
        "❓ Ответы на частые вопросы\n"
        "📞 Контакты и соцсети\n"
        "🎯 Сможешь испытать свои силы в тестовых вопросах\n"
        "🔔 Подписаться на уведомления о будущих играх в твоем городе\n\n"
        "Выбери что тебя интересует 👇",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


@router.message(F.text == "🎉 Акции")
async def show_promotions(message: Message):
    await message.answer(
        "🎉 <b>Акции и бонусы</b>\n\n"
        "👥 <b>Реферальная программа</b>\n"
        "Приглашай друзей в игры — за каждого приглашённого\n"
        "получаешь [бонус]. Твоя ссылка: [ссылка]\n\n"
        "🎂 <b>День рождения</b>\n"
        "В свой день рождения получи [что именно] — просто напиши нам в этот день 🎁\n\n"
        'По всем вопросам пиши <a href="https://t.me/kotlettttka">Администратору</a>',
        parse_mode="HTML"
    )

