# handlers/admin_meme.py — управління чергою мемів

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from config import ADMIN_IDS
from database.db import add_meme, count_memes

router = Router()

# ─── НАЛАШТУВАННЯ ────────────────────────────────────────────────────────────
# Поріг залишку мемів при якому адмін отримує попередження
MEME_LOW_THRESHOLD = 2  # ← змінити якщо потрібен інший поріг
# ─────────────────────────────────────────────────────────────────────────────


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("meme_stats"))
async def cmd_meme_stats(message: Message):
    """Показує кількість мемів в черзі"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    count = await count_memes()
    await message.answer(
        f"😂 *Статус очереди мемов:*\n\n"
        f"📦 Мемов в очереди: *{count}*\n\n"
        f"{'⚠️ Мало мемов! Загрузи ещё.' if count <= MEME_LOW_THRESHOLD else '✅ Запас мемов в норме.'}\n\n"
        "Чтобы добавить меме — отправь фото с подписью `/add_meme`",
        parse_mode="Markdown"
    )


@router.message(F.photo, F.caption.regexp(r"^/add_meme"))
async def cmd_add_meme_photo(message: Message):
    """Админ добавляет фото с подписью /add_meme — добавляется в очередьюю"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    photo_id = message.photo[-1].file_id
    await add_meme(photo_id)
    count = await count_memes()

    await message.answer(
        f"✅ Мем добавлен в очередь!\n"
        f"📦 Всего в очереди: *{count}* мемов",
        parse_mode="Markdown"
    )


@router.message(Command("add_meme"))
async def cmd_add_meme_text(message: Message):
    """Если написали /add_meme без фото — подсказываем как правильно"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    await message.answer(
        "📷 Чтобы добавить мем — отправь *фото* с подписью `/add_meme`\n\n"
        "Можно отправить несколько фото подряд — каждое добавится в очередь.",
        parse_mode="Markdown"
    )
