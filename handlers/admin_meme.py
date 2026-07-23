# handlers/admin_meme.py — управління чергою мемів

import asyncio
import re
from collections import defaultdict

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from config import ADMIN_IDS
from database.db import add_meme, count_memes

router = Router()

# ─── НАЛАШТУВАННЯ ────────────────────────────────────────────────────────────
# Поріг залишку мемів при якому адмін отримує попередження
MEME_LOW_THRESHOLD = 2  # ← змінити якщо потрібен інший поріг

# Скільки секунд чекати, чи не прийдуть ще фото з того ж альбому,
# перш ніж вважати альбом повністю отриманим
ALBUM_DEBOUNCE_SECONDS = 1.0
# ─────────────────────────────────────────────────────────────────────────────

# Буфери для збору фото одного альбому (media_group_id -> дані)
_album_photos: dict[str, list[str]] = defaultdict(list)
_album_confirmed: dict[str, bool] = {}
_album_tasks: dict[str, asyncio.Task] = {}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _has_add_meme_caption(caption) -> bool:
    return bool(caption) and bool(re.match(r"^/add_meme", caption))


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
        "Чтобы добавить мем — отправь фото с подписью `/add_meme`\n"
        "Можно отправить сразу альбом из нескольких фото с такой подписью.",
        parse_mode="Markdown"
    )


async def _finalize_album(group_id: str, message: Message):
    """Чекає ALBUM_DEBOUNCE_SECONDS — чи не прийдуть ще фото цього ж альбому,
    і якщо десь у підписі був /add_meme — додає всі зібрані фото в чергу"""
    await asyncio.sleep(ALBUM_DEBOUNCE_SECONDS)

    photos    = _album_photos.pop(group_id, [])
    confirmed = _album_confirmed.pop(group_id, False)
    _album_tasks.pop(group_id, None)

    if not confirmed or not photos:
        return  # підпису /add_meme ніде в альбомі не було — ігноруємо

    for photo_id in photos:
        await add_meme(photo_id)

    count = await count_memes()
    await message.answer(
        f"✅ Добавлено мемов из альбома: *{len(photos)}*\n"
        f"📦 Всего в очереди: *{count}* мемов",
        parse_mode="Markdown"
    )


@router.message(F.photo, F.media_group_id.is_not(None))
async def cmd_add_meme_album(message: Message):
    """Приём нескольких мемов одним постом (альбом/медиагруппа).
    Подпись /add_meme можно поставить под ЛЮБЫМ фото в альбоме."""
    if not is_admin(message.from_user.id):
        return

    group_id = message.media_group_id
    _album_photos[group_id].append(message.photo[-1].file_id)

    if _has_add_meme_caption(message.caption):
        _album_confirmed[group_id] = True

    # Перезапускаємо таймер очікування, щоб дочекатись усіх фото альбому
    existing_task = _album_tasks.get(group_id)
    if existing_task:
        existing_task.cancel()
    _album_tasks[group_id] = asyncio.create_task(_finalize_album(group_id, message))


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
        "Можно отправить несколько фото подряд — каждое добавится в очередь.\n"
        "Также можно отправить сразу *альбом* (несколько фото одним постом) "
        "с подписью `/add_meme` под любым из фото — добавятся все фото альбома.",
        parse_mode="Markdown"
    )
