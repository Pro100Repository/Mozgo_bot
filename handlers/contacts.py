# handlers/contacts.py — контакты и ссылки на соцсети
#
# ВАЖНО: замени значения ниже на свои реальные данные.
# Если какой-то соцсети у тебя нет — удали соответствующую строку
# в соответствующем списке (TELEGRAM_CHANNELS / VK_PAGES).

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

router = Router()

# ──────────────────────────────────────────
# РЕДАКТИРУЙ ЭТИ ДАННЫЕ ПОД СЕБЯ:
# ──────────────────────────────────────────
TG_ADMIN = "kotlettttka"  # ← твой Telegram username, без @

# Список Telegram-каналов, которые попадут в подменю "Telegram"
TELEGRAM_CHANNELS = [
    ("Ruda Games Москва",       "rudagamespriglosmsc"),  # можно и полный URL
    ("Ruda Games Красногорск",  "rudagameskrgk"),
    ("Ruda Games Обнинск",      "rudagamesobninsk"),
    
]

# Список VK-страниц, которые попадут в подменю "VK"
# ⚠️ ЗАПОЛНИ РЕАЛЬНЫМИ ССЫЛКАМИ — сейчас это заглушки!
VK_PAGES = [
    ("Ruda Games Москва",       "https://vk.ru/mzgb_msk"),
    ("Ruda Games Красногорск",  "https://vk.ru/mzgb_krgk"),
    ("Ruda Games Обнинск",      "https://vk.ru/mzgb_obn"),
    ("Ruda Games Истра",        "https://vk.ru/mzgb_ist"),
]

RUDA = "https://rudagames.com/"
# ──────────────────────────────────────────


def build_url(value: str, base: str) -> str:
    """Если value уже похоже на полный URL — используем как есть.
    Если это просто username — собираем ссылку через base."""
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"{base}{value.lstrip('@')}"


def main_contacts_keyboard() -> InlineKeyboardMarkup:
    buttons_list = []

    if TG_ADMIN:
        buttons_list.append([InlineKeyboardButton(
            text="✉️ Написать администратору",
            url=build_url(TG_ADMIN, "https://t.me/")
        )])

    if RUDA:
        buttons_list.append([InlineKeyboardButton(
            text="🎮 Оффициальный сайт Ruda Games",
            url=RUDA
        )])

    if TELEGRAM_CHANNELS:
        buttons_list.append([InlineKeyboardButton(
            text="📢 Telegram",
            callback_data="contacts_tg"
        )])

    if VK_PAGES:
        buttons_list.append([InlineKeyboardButton(
            text="🔵 VK",
            callback_data="contacts_vk"
        )])

   
    return InlineKeyboardMarkup(inline_keyboard=buttons_list)


def sub_keyboard(items: list[tuple[str, str]], back_callback: str) -> InlineKeyboardMarkup:
    buttons_list = []
    for text, value in items:
        buttons_list.append([InlineKeyboardButton(
            text=text,
            url=build_url(value, "https://t.me/") if "t.me" not in value and "http" not in value else value
        )])
    buttons_list.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=buttons_list)


CONTACTS_TEXT = (
    "📞 Контакты и соцсети\n\n"
    "Подписывайся на наши страницы, чтобы не пропустить анонсы и новости 👇"
)


@router.message(F.text == "📞 Контакты")
async def show_contacts(message: Message):
    await message.answer(
        CONTACTS_TEXT,
        reply_markup=main_contacts_keyboard()
    )


@router.callback_query(F.data == "contacts_tg")
async def show_telegram_submenu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📢 Наши Telegram-каналы:",
        reply_markup=sub_keyboard(TELEGRAM_CHANNELS, back_callback="contacts_back")
    )
    await callback.answer()


@router.callback_query(F.data == "contacts_vk")
async def show_vk_submenu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔵 Наши страницы VK:",
        reply_markup=sub_keyboard(VK_PAGES, back_callback="contacts_back")
    )
    await callback.answer()


@router.callback_query(F.data == "contacts_back")
async def back_to_contacts(callback: CallbackQuery):
    await callback.message.edit_text(
        CONTACTS_TEXT,
        reply_markup=main_contacts_keyboard()
    )
    await callback.answer()
