# handlers/subscription.py — підписка на розсилку нових ігор по містах + типи нагадувань

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import SUBSCRIPTION_ADMIN_IDS
from database.db import (
    RESULT_CITIES, subscribe, unsubscribe,
    get_user_subscriptions, get_user_notify_prefs, toggle_notify_pref
)

router = Router()

# ─── ТИПИ НАГАДУВАНЬ (мультивибір) ───────────────────────────────────────────
# code -> підпис кнопки. Порядок тут визначає порядок кнопок у меню.
NOTIFY_PREFS = [
    ("0d",     "🔔 В день игры"),
    ("1d",     "🔔 За 1 день до игры"),
    ("2d",     "🔔 За 2 дня до игры"),
    ("7d",     "🔔 За неделю до игры"),
    ("reg14d", "📝 За 2 недели (с началом регистрации)"),
]

NOTIFY_PREFS_TEXT = (
    "⏰ Когда присылать напоминания об играх?\n\n"
    "Можно выбрать сразу несколько вариантов - нажимай на нужные 👇\n\n"
    "❗️ «За 2 недели (с началом регистрации)»: для первых игр месяца не получится прислать"
    "напоминание за 2 недели - расписание на следующий месяц появляется в конце предыдущего. "
    "В этом случае пришлём уведомление сразу после добавления игры и открытия регистрации (в 12:00)."
    
)


# ─── КЛАВІАТУРА З ЧЕКБОКСАМИ (міста) ─────────────────────────────────────────

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
        text="⏰ Настроить напоминания",
        callback_data="open_notify_prefs"
    )])
    buttons.append([InlineKeyboardButton(
        text="✔️ Готово",
        callback_data="sub_done"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def notify_prefs_kb(selected: set) -> InlineKeyboardMarkup:
    """Кнопки типів нагадувань з чекбоксами ✅/☐ (мультивибір)"""
    buttons = []
    for code, label in NOTIFY_PREFS:
        icon = "✅" if code in selected else "☐"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {label}",
            callback_data=f"np_toggle_{code}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="np_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def notify_admin_new_subscription(bot: Bot, user, city: str):
    """Надсилає ВСІМ адмінам зі списку SUBSCRIPTION_ADMIN_IDS сповіщення про нову підписку."""
    if not SUBSCRIPTION_ADMIN_IDS:
        return  # ID адмінів не задано в .env — пропускаем без ошибки

    full_name = user.full_name or user.first_name or "—"
    username_part = f"@{user.username}" if user.username else "—"

    text = (
        "🔔 *Новая подписка на рассылку!*\n\n"
        f"👤 Имя: {full_name}\n"
        f"🔗 Username: {username_part}\n"
        f"🆔 ID: `{user.id}`\n"
        f"🏙 Город: {city}"
    )
    for admin_id in SUBSCRIPTION_ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Не удалось отправить уведомление админу {admin_id} о подписке: {e}")


# ─── ТЕКСТ МЕНЮ ПІДПИСКИ (спільний для обох точок входу) ─────────────────────

async def _subscription_text(user_id: int) -> str:
    subscribed = await get_user_subscriptions(user_id)

    if subscribed:
        status = "Ты подписан на: " + ", ".join(f"*{c}*" for c in subscribed)
    else:
        status = "Ты пока не подписан ни на один город."

    return (
        "🔔 *Подписка на новые игры*\n\n"
        f"{status}\n\n"
        "Выбери города, о новых играх в которых хочешь получать уведомления.\n"
        "Нажми на город чтобы подписаться или отписаться 👇"
    )


# ─── ХЕНДЛЕРИ: ПІДПИСКА НА МІСТА ──────────────────────────────────────────────

@router.message(F.text == "🔔 Подписка на игры")
async def show_subscription(message: Message):
    await message.answer(
        await _subscription_text(message.from_user.id),
        reply_markup=await subscription_kb(message.from_user.id),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "open_subscription_menu")
async def open_subscription_from_faq(callback: CallbackQuery):
    """Відкриває меню підписки за callback_data з FAQ (open_subscription_from_faq)."""
    await callback.message.edit_text(
        await _subscription_text(callback.from_user.id),
        reply_markup=await subscription_kb(callback.from_user.id),
        parse_mode="Markdown"
    )
    await callback.answer()


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
            "Когда появится новая игра - ты получишь уведомление 🔔"
        )
    else:
        text = (
            "🔕 Ты не подписан ни на один город.\n"
            "Уведомления приходить не будут."
        )

    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()


# ─── ХЕНДЛЕРИ: ТИП НАГАДУВАНЬ (мультивибір) ──────────────────────────────────

@router.callback_query(F.data == "open_notify_prefs")
async def open_notify_prefs(callback: CallbackQuery):
    selected = await get_user_notify_prefs(callback.from_user.id)
    await callback.message.edit_text(
        NOTIFY_PREFS_TEXT,
        reply_markup=notify_prefs_kb(selected),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("np_toggle_"))
async def np_toggle(callback: CallbackQuery):
    code = callback.data.replace("np_toggle_", "")
    now_on = await toggle_notify_pref(callback.from_user.id, code)

    selected = await get_user_notify_prefs(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=notify_prefs_kb(selected))

    if code == "reg14d" and now_on:
        await callback.answer(
            "✅ Включено. Напомним за 2 недели до игры.\n"
            "Если игра добавлена на сайт позже - напомним после добавления (в 12:00).",
            show_alert=True
        )
    else:
        await callback.answer("✅ Включено" if now_on else "❌ Выключено")


@router.callback_query(F.data == "np_back")
async def np_back(callback: CallbackQuery):
    await callback.message.edit_text(
        await _subscription_text(callback.from_user.id),
        reply_markup=await subscription_kb(callback.from_user.id),
        parse_mode="Markdown"
    )
    await callback.answer()
