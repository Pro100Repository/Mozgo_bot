# game_sync.py — импорт расписания игр с сайта rudagames.com (JSON API)
#
# Бот запрашивает расписание каждого города, находит НОВЫЕ игры и присылает
# их админам карточками с кнопками «✅ Добавить» / «❌ Пропустить».
# Ничего не добавляется в бота без подтверждения админа.
#
# НАСТРОЙКИ ─────────────────────────────────────────────────────────────────
API_BASE  = "https://api.rudagames.com"
SITE_BASE = "https://rudagames.com"

# Название города В БОТЕ -> ID города на сайте (число из запроса events/dates/<ID>).
# None = ID пока не задан, город пропускается.
CITY_IDS = {
    "Красногорск":           198,
    "Москва «бар Liberty»":  None,   # ← впиши ID Москвы
    "Истра":                 None,   # ← впиши ID Истры
    "Обнинск":               None,   # ← впиши ID Обнинска
}

# Если для города указан фильтр — берутся только игры, в названии заведения
# которых есть одно из слов (без учёта регистра). Нужен для Москвы, где на сайте
# много заведений, а в боте только Liberty.
PLACE_FILTERS = {
    "Москва «бар Liberty»": ["liberty"],
}

SKIP_CORPORATE  = True   # не предлагать корпоративные игры
REQUEST_TIMEOUT = 20     # секунд на один запрос к сайту
# ────────────────────────────────────────────────────────────────────────────

import asyncio
import logging
import re
from datetime import datetime

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import SYNC_ADMIN_IDS
from database.db import (
    external_id_known, find_similar_game, add_candidate,
    get_pending_candidates, prune_candidates,
)

logger = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()


# ─── РАЗБОР ДАННЫХ САЙТА ─────────────────────────────────────────────────────

def _clean(text) -> str:
    """Убирает символы, которые ломают Markdown в рассылках бота
    (например, апостроф-«`» в названии HARAT`S PUB)."""
    text = (text or "")
    text = text.replace("`", "'").replace("*", "").replace("_", " ")
    text = text.replace("[", "(").replace("]", ")")
    return re.sub(r"\s+", " ", text).strip()


def make_title(game_name: str) -> str:
    """'Мозгобойня - Классическая 26 - Классическая #224 (Тема)' ->
    'Мозгобойня — Классическая #224 (Тема)';
    'Туц Туц Quiz - Классическая - Туц Туц QUIZ #121' -> 'Туц Туц QUIZ #121'."""
    name = _clean(game_name)
    parts = [p.strip() for p in name.split(" - ") if p.strip()]
    if len(parts) < 2:
        return name
    head, last = parts[0], parts[-1]
    if last.lower().startswith(head.lower()):
        return last
    return f"{head} — {last}"


def format_price(raw, currency="RUB") -> str:
    """Сайт отдаёт цену в копейках: 70000 -> '700 руб'"""
    try:
        value = float(raw) / 100
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    amount = str(int(value)) if value == int(value) else f"{value:.2f}"
    return f"{amount} руб" if (currency or "RUB") == "RUB" else f"{amount} {currency}"


def parse_event(raw: dict, city: str):
    """Одна игра из JSON сайта -> словарь с полями нашего бота (или None)."""
    uuid = raw.get("uuid")
    played_at = raw.get("played_at")
    if not uuid or not played_at:
        return None
    try:
        dt = datetime.fromisoformat(played_at).replace(tzinfo=None)
    except ValueError:
        return None

    place = _clean(raw.get("place"))
    address = _clean(raw.get("address"))
    if place and address and "(" not in place:
        place = f"{place} ({address})"
    elif not place:
        place = address

    city_slug = raw.get("city_link_name") or ""
    link = (
        f"{SITE_BASE}/{city_slug}/schedule?modal=isShowGameRegistrationModal"
        f"&uuid={uuid}&reg_type=registration&isCorporateGame=false"
    ) if city_slug else ""

    notes = []
    if raw.get("is_full"):
        notes.append("⚠️ На сайте мест уже нет")
    if raw.get("is_registration_opened") is False:
        when = ""
        try:
            when = datetime.fromisoformat(raw["registration_at"]).strftime(" (откроется %d.%m в %H:%M)")
        except (KeyError, TypeError, ValueError):
            pass
        notes.append(f"⏳ Регистрация ещё не открыта{when}")

    return {
        "external_id":       uuid,
        "city":              city,
        "title":             make_title(raw.get("game_name") or raw.get("displayed_game_name") or ""),
        "date":              dt.strftime("%d.%m.%Y %H:%M"),
        "event_datetime":    dt.strftime("%Y-%m-%d %H:%M"),
        "location":          place,
        "price":             format_price(raw.get("price"), raw.get("currency")),
        "registration_link": link,
        "note":              "\n".join(notes),
    }


async def fetch_city_events(city_id: int) -> list:
    import aiohttp   # входит в зависимости aiogram, отдельно ставить не нужно

    url = f"{API_BASE}/events/dates/{city_id}"
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    headers = {"User-Agent": "RudaGamesTelegramBot/1.0", "Accept": "application/json"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url, params={"sort": "played_at"}) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    if not isinstance(data, list):
        raise ValueError("неожиданный формат ответа сайта")
    return data


# ─── КАРТОЧКИ ДЛЯ АДМИНА ─────────────────────────────────────────────────────

def candidate_text(c: dict) -> str:
    lines = ["🆕 Новая игра на сайте", "",
             f"🎯 {c['title']}",
             f"📆 {c['date']}",
             f"🏙 {c['city']}"]
    if c.get("location"):
        lines.append(f"📍 {c['location']}")
    if c.get("price"):
        lines.append(f"💰 {c['price']}")
    if c.get("note"):
        lines += ["", c["note"]]
    return "\n".join(lines)


def candidate_kb(c: dict) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="✅ Добавить",  callback_data=f"sy_add_{c['id']}"),
        InlineKeyboardButton(text="❌ Пропустить", callback_data=f"sy_skip_{c['id']}"),
    ]]
    if c.get("registration_link"):
        rows.append([InlineKeyboardButton(text="🔗 Открыть на сайте", url=c["registration_link"])])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_candidates(bot: Bot, candidates: list):
    """Отправляет всем админам карточки (и кнопки «все сразу», если игр больше одной)"""
    if not candidates:
        return
    for admin_id in SYNC_ADMIN_IDS:
        try:
            if len(candidates) > 1:
                await bot.send_message(
                    admin_id,
                    f"🔄 Найдено новых игр на сайте: {len(candidates)}\n"
                    "Реши по каждой игре ниже или сразу по всем:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text=f"✅ Добавить все ({len(candidates)})", callback_data="sy_addall"),
                        InlineKeyboardButton(text="❌ Пропустить все", callback_data="sy_skipall"),
                    ]])
                )
            for c in candidates:
                await bot.send_message(admin_id, candidate_text(c), reply_markup=candidate_kb(c))
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.warning(f"[Sync] Не удалось отправить карточки админу {admin_id}: {e}")


async def _notify_admins(bot: Bot, text: str):
    for admin_id in SYNC_ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


# ─── ОСНОВНАЯ СИНХРОНИЗАЦИЯ ──────────────────────────────────────────────────

async def run_sync(bot: Bot, manual: bool = False) -> str:
    """Опрашивает сайт, сохраняет новые игры как «кандидатов» и шлёт их админам.
    manual=True (команда /sync_games) — дополнительно повторно присылает ещё
    не обработанные карточки. Возвращает текстовый отчёт."""
    if _sync_lock.locked():
        return "⏳ Синхронизация уже выполняется, подожди пару секунд."

    async with _sync_lock:
        await prune_candidates()

        report, errors, new_ids = [], [], set()
        configured = 0
        now = datetime.now()

        for city, city_id in CITY_IDS.items():
            if not city_id:
                report.append(f"• {city}: ID города не задан — пропущен")
                continue
            configured += 1

            try:
                events = await fetch_city_events(city_id)
            except Exception as e:
                logger.warning(f"[Sync] {city}: ошибка запроса: {e}")
                errors.append(f"{city}: {e}")
                report.append(f"• {city}: ❌ ошибка запроса")
                continue

            filters = [f.lower() for f in PLACE_FILTERS.get(city, [])]
            seen = new = 0

            for raw in events:
                if SKIP_CORPORATE and raw.get("is_corporate_game"):
                    continue
                if (raw.get("distribution_format") or "offline") != "offline":
                    continue
                if filters and not any(f in (raw.get("place") or "").lower() for f in filters):
                    continue

                ev = parse_event(raw, city)
                if not ev:
                    continue
                if datetime.strptime(ev["event_datetime"], "%Y-%m-%d %H:%M") <= now:
                    continue
                seen += 1

                if await external_id_known(ev["external_id"]):
                    continue
                if await find_similar_game(city, ev["event_datetime"], ev["location"]):
                    continue   # такая игра уже есть (например, добавлена вручную)

                cid = await add_candidate(ev)
                if cid:
                    new_ids.add(cid)
                    new += 1

            report.append(f"• {city}: на сайте {seen}, новых {new}")
            await asyncio.sleep(1)   # не дёргаем сайт слишком часто

        pending = await get_pending_candidates()
        to_send = pending if manual else [c for c in pending if c["id"] in new_ids]
        await send_candidates(bot, to_send)

        if errors and (manual is False):
            await _notify_admins(
                bot,
                "⚠️ Синхронизация с сайтом: не удалось получить расписание.\n" + "\n".join(errors) +
                "\n\nВозможно, сайт недоступен или изменился формат данных."
            )

        header = "🔄 Синхронизация завершена"
        if not configured:
            header += "\n⚠️ Ни для одного города не задан ID (см. CITY_IDS в game_sync.py)"
        return (
            f"{header}\n\n" + "\n".join(report) +
            f"\n\nОжидают решения: {len(pending)}"
        )
