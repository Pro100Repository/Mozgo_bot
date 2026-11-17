# handlers/admin_sync.py — подтверждение игр, найденных на сайте

import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from config import SYNC_ADMIN_IDS
from database.db import (
    add_game, add_venue,
    get_candidate, get_pending_candidates, set_candidate_status,
)
from game_sync import run_sync, candidate_text, strip_numbers, ensure_photo_id

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in SYNC_ADMIN_IDS   # только те, кому приходят карточки


async def _set_card_text(message: Message, text: str):
    """Карточка может быть и фото (подпись), и обычным текстом.
    Без reply_markup кнопки под карточкой исчезают."""
    if message.photo:
        await message.edit_caption(caption=text)
    else:
        await message.edit_text(text)


async def _publish(bot: Bot, chat_id: int, c: dict):
    """Добавляет игру в бота тем же способом, что и ручная форма /add_game"""
    photo_id = await ensure_photo_id(bot, chat_id, c)
    await add_game(
        title             = strip_numbers(c["title"]),   # без номера выпуска
        date              = c["date"],
        location          = c["location"],
        registration_link = c["registration_link"],
        price             = c["price"],
        city              = c["city"],
        event_datetime    = c["event_datetime"],
        photo_id          = photo_id,
        external_id       = c["external_id"],
    )
    if c["location"]:
        await add_venue(c["city"], c["location"])   # место попадёт в кнопки /add_game


async def _publish_claimed(bot: Bot, chat_id: int, c: dict) -> bool:
    """Сначала «занимаем» карточку (чтобы два админа не добавили игру дважды),
    затем добавляем. При ошибке возвращаем карточку в ожидание."""
    if not await set_candidate_status(c["id"], "added"):
        return False
    try:
        await _publish(bot, chat_id, c)
    except Exception as e:
        logger.error(f"[Sync] Ошибка добавления игры {c['id']}: {e}")
        await set_candidate_status(c["id"], "pending", from_status="added")
        raise
    return True


@router.message(Command("sync_games"))
async def cmd_sync_games(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    status = await message.answer("🔄 Проверяю сайт…")
    report = await run_sync(bot, manual=True)
    await status.edit_text(report)


@router.callback_query(F.data.startswith("sy_add_"))
async def sy_add(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    c = await get_candidate(int(callback.data.replace("sy_add_", "")))
    if not c:
        await callback.answer("Игра не найдена", show_alert=True)
        return
    try:
        ok = await _publish_claimed(callback.bot, callback.message.chat.id, c)
    except Exception:
        await callback.answer("❌ Не удалось добавить, попробуй ещё раз", show_alert=True)
        return
    if not ok:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Уже обработано", show_alert=True)
        return
    await _set_card_text(callback.message, candidate_text(c) + "\n\n✅ Добавлено в бота")
    await callback.answer("✅ Добавлено")


@router.callback_query(F.data.startswith("sy_skip_"))
async def sy_skip(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    c = await get_candidate(int(callback.data.replace("sy_skip_", "")))
    if not c:
        await callback.answer("Игра не найдена", show_alert=True)
        return
    if not await set_candidate_status(c["id"], "skipped"):
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Уже обработано", show_alert=True)
        return
    await _set_card_text(callback.message, candidate_text(c) + "\n\n❌ Пропущено")
    await callback.answer("Пропущено")


@router.callback_query(F.data == "sy_addall")
async def sy_add_all(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    added = failed = 0
    for c in await get_pending_candidates():
        try:
            if await _publish_claimed(callback.bot, callback.message.chat.id, c):
                added += 1
        except Exception:
            failed += 1
    text = f"✅ Добавлено игр: {added}"
    if failed:
        text += f"\n⚠️ Не удалось добавить: {failed} (они остались в ожидании)"
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "sy_skipall")
async def sy_skip_all(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    skipped = 0
    for c in await get_pending_candidates():
        if await set_candidate_status(c["id"], "skipped"):
            skipped += 1
    await callback.message.edit_text(f"❌ Пропущено игр: {skipped}")
    await callback.answer()
