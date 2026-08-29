# handlers/meme.py — підписка на мем недели

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import SUBSCRIPTION_ADMIN_IDS
from database.db import (
    meme_subscribe, meme_unsubscribe,
    is_meme_subscribed
)

router = Router()


def meme_kb(subscribed: bool) -> InlineKeyboardMarkup:
    if subscribed:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔕 Отписаться от мема недели",
                callback_data="meme_unsub"
            )
        ]])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔔 Подписаться на мем недели",
                callback_data="meme_sub"
            )
        ]])


@router.message(F.text == "😂 Мем недели")
async def show_meme_subscription(message: Message):
    user_id    = message.from_user.id
    subscribed = await is_meme_subscribed(user_id)
    
    status = "✅ Ты подписан на мем недели!" if subscribed else "❌ Ты не подписан на мем недели."

    await message.answer(
        f"😂 *Мем недели*\n\n"
        f"{status}\n\n"
        "Каждый понедельник в 12:00 тебе будет приходить свежий мем 🎉\n\n",
        reply_markup=meme_kb(subscribed),
        parse_mode="Markdown"
    )


async def notify_admin_meme_subscription(bot: Bot, user):
    """Сповіщення ВСІХ адмінів зі списку SUBSCRIPTION_ADMIN_IDS про нову підписку на мем недели"""
    if not SUBSCRIPTION_ADMIN_IDS:
        return

    full_name     = user.full_name or user.first_name or "—"
    username_part = f"@{user.username}" if user.username else "—"

    text = (
        "😂 *Новая подписка на мем недели!*\n\n"
        f"👤 Имя: {full_name}\n"
        f"🔗 Username: {username_part}\n"
        f"🆔 ID: `{user.id}`"
    )
    for admin_id in SUBSCRIPTION_ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Не удалось отправить уведомление админу {admin_id} о подписке на мем: {e}")


@router.callback_query(F.data == "meme_sub")
async def meme_sub(callback: CallbackQuery, bot: Bot):
    user_id  = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    await meme_subscribe(user_id, username)
    await callback.message.edit_reply_markup(reply_markup=meme_kb(True))
    await callback.answer("✅ Подписан на мем недели!")
    await notify_admin_meme_subscription(bot, callback.from_user)


@router.callback_query(F.data == "meme_unsub")
async def meme_unsub(callback: CallbackQuery):
    await meme_unsubscribe(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=meme_kb(False))
    await callback.answer("🔕 Отписан от мема недели.")
