# handlers/meme.py — підписка на мем дня

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import (
    meme_subscribe, meme_unsubscribe,
    is_meme_subscribed
)

router = Router()


def meme_kb(subscribed: bool) -> InlineKeyboardMarkup:
    if subscribed:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔕 Отписаться от мема дня",
                callback_data="meme_unsub"
            )
        ]])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔔 Подписаться на мем дня",
                callback_data="meme_sub"
            )
        ]])


@router.message(F.text == "😂 Мем дня")
async def show_meme_subscription(message: Message):
    user_id    = message.from_user.id
    subscribed = await is_meme_subscribed(user_id)
    
    status = "✅ Ты подписан на мем дня!" if subscribed else "❌ Ты не подписан на мем дня."

    await message.answer(
        f"😂 *Мем дня*\n\n"
        f"{status}\n\n"
        "Каждый день в 12:00 тебе будет приходить свежий мем 🎉\n\n",
        reply_markup=meme_kb(subscribed),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "meme_sub")
async def meme_sub(callback: CallbackQuery):
    user_id  = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    await meme_subscribe(user_id, username)
    await callback.message.edit_reply_markup(reply_markup=meme_kb(True))
    await callback.answer("✅ Подписан на мем дня!")


@router.callback_query(F.data == "meme_unsub")
async def meme_unsub(callback: CallbackQuery):
    await meme_unsubscribe(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=meme_kb(False))
    await callback.answer("🔕 Отписан от мема дня.")
