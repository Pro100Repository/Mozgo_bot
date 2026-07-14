# handlers/subscription.py — підписка на розсилку нових ігор по містах

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import SUBSCRIPTION_ADMIN_ID
from database.db import (
    RESULT_CITIES, subscribe, unsubscribe,
    get_user_subscriptions
)

router = Router()

# ─── КЛАВІАТУРА З ЧЕКБОКСАМИ ─────────────────────────────────────────────────

async def subscription_kb(user_id: int) -> InlineKeyboardMarkup:
    """Кнопки міст з чекбоксами ✅/☐ залежно від підписки"""
    subscribed = await get_user_subscriptions(user_id)
    buttons = []
    for city in RESULT_CITIES:
        icon = "✅" if city in subscribed else "☐"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {city}",
            callback_data=f"sub_toggle_{city}"
        )])
    buttons.append([InlineKeyboardButton(
        text="✔️ Готово",
        callback_data="sub_done"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def notify_admin_new_subscription(bot: Bot, user, city: str):
    """Надсилає конкретному адміну (SUBSCRIPTION_ADMIN_ID) сповіщення про нову підписку."""
    if not SUBSCRIPTION_ADMIN_ID:
        return  # ID адміна не задано в .env — пропускаем без ошибки

    full_name = user.full_name or user.first_name or "—"
    username_part = f"@{user.username}" if user.username else "—"

    text = (
        "🔔 *Новая подписка на рассылку!*\n\n"
        f"👤 Имя: {full_name}\n"
        f"🔗 Username: {username_part}\n"
        f"🆔 ID: `{user.id}`\n"
        f"🏙 Город: {city}"
    )
    try:
        await bot.send_message(SUBSCRIPTION_ADMIN_ID, text, parse_mode="Markdown")
    except Exception as e:
        print(f"⚠️ Не удалось отправить уведомление админу о подписке: {e}")


# ─── ХЕНДЛЕРИ ────────────────────────────────────────────────────────────────

@router.message(F.text == "🔔 Подписка на игры")
async def show_subscription(message: Message):
    subscribed = await get_user_subscriptions(message.from_user.id)

    if subscribed:
        status = "Ты подписан на: " + ", ".join(f"*{c}*" for c in subscribed)
    else:
        status = "Ты пока не подписан ни на один город."

    await message.answer(
        "🔔 *Подписка на новые игры*\n\n"
        f"{status}\n\n"
        "Выбери города, о новых играх в которых хочешь получать уведомления.\n"
        "Нажми на город чтобы подписаться или отписаться 👇",
        reply_markup=await subscription_kb(message.from_user.id),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("sub_toggle_"))
async def toggle_subscription(callback: CallbackQuery, bot: Bot):
    city = callback.data.replace("sub_toggle_", "")
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name

    subscribed = await get_user_subscriptions(user_id)

    if city in subscribed:
        await unsubscribe(user_id, city)
        await callback.answer(f"❌ Отписан от {city}")
    else:
        await subscribe(user_id, city, username)
        await callback.answer(f"✅ Подписан на {city}")
        await notify_admin_new_subscription(bot, callback.from_user, city)

    # Оновлюємо клавіатуру
    await callback.message.edit_reply_markup(
        reply_markup=await subscription_kb(user_id)
    )


@router.callback_query(F.data == "sub_done")
async def subscription_done(callback: CallbackQuery):
    subscribed = await get_user_subscriptions(callback.from_user.id)

    if subscribed:
        cities_text = ", ".join(f"*{c}*" for c in subscribed)
        text = (
            f"✅ Готово! Ты подписан на города: {cities_text}\n\n"
            "Когда появится новая игра — ты получишь уведомление 🔔"
        )
    else:
        text = (
            "🔕 Ты не подписан ни на один город.\n"
            "Уведомления приходить не будут."
        )

    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()
