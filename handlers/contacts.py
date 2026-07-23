# handlers/contacts.py — контакты и ссылки на соцсети
#
# ВАЖНО: замени значения ниже на свои реальные данные.
# Если какой-то соцсети у тебя нет — удали соответствующую строку
# в списке buttons ниже (или оставь пустой URL — тогда кнопка не нажмётся,
# как было раньше).

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

# ──────────────────────────────────────────
# РЕДАКТИРУЙ ЭТИ ДАННЫЕ ПОД СЕБЯ:
# ──────────────────────────────────────────
TG_ADMIN    = "kotlettttka"          # ← твой Telegram username, без @
TG_MSC  = "rudagamespriglosmsc"                # ← username канала, без @ (или полный URL https://t.me/...)
TG_KRSN  = "rudagameskrgk"                      # ← username канала, без @ (или полный URL https://t.me/...)
TG_OBN  = "rudagamesobninsk"
INSTAGRAM   = "ruda_games"              # ← username Instagram, без @ (или полный URL https://instagram.com/...)
RUDA   = "https://rudagames.com/"
# ──────────────────────────────────────────


def build_url(value: str, base: str) -> str:
    """Если value уже похоже на полный URL — используем как есть.
    Если это просто username — собираем ссылку через base."""
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"{base}{value.lstrip('@')}"


@router.message(F.text == "📞 Контакты")
async def show_contacts(message: Message):
    buttons_list = []

    if TG_ADMIN:
        buttons_list.append([InlineKeyboardButton(
            text="✉️ Написать администратору",
            url=build_url(TG_ADMIN, "https://t.me/")
        )])

    if TG_MSC:
        buttons_list.append([InlineKeyboardButton(
            text="📢 Ruda Games Москва",
            url=build_url(TG_MSC, "https://t.me/")
        )])

    if TG_KRSN:
        buttons_list.append([InlineKeyboardButton(
            text="📢 Ruda Games Красногорск",
            url=build_url(TG_KRSN, "https://t.me/")
        )])

    if TG_OBN:
        buttons_list.append([InlineKeyboardButton(
            text="📢 Ruda Games Обнинск",
            url=build_url(TG_OBN, "https://t.me/")
        )])

    if INSTAGRAM:
        buttons_list.append([InlineKeyboardButton(
            text="📸 Instagram",
            url=build_url(INSTAGRAM, "https://instagram.com/")
        )])

    if RUDA:
        buttons_list.append([InlineKeyboardButton(
            text="🎮 Ruda Games",
            url=build_url(RUDA)
        )])

    buttons = InlineKeyboardMarkup(inline_keyboard=buttons_list) if buttons_list else None

    await message.answer(
        f"📞 Контакты и соцсети\n\n"
        f"✉️ Telegram: @{TG_ADMIN}\n\n"
        "Подписывайся на наши страницы, чтобы не пропустить анонсы и новости 👇",
        reply_markup=buttons
    )
