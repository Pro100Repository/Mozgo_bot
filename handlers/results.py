# handlers/results.py — рейтинг команд для користувача

import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import RESULT_CITIES, RATING_GROUPS, get_rating

router = Router()

# ─── РАНГИ (тимчасово вимкнено) ──────────────────────────────────────────────
# RANKS = [
#     (10, "👑 Легенда"),
#     (5,  "🔥 Мастер"),
#     (2,  "⭐ Опытный"),
#     (1,  "🌱 Новичок"),
# ]

# def get_rank(wins1: int) -> str:
#     for threshold, rank in RANKS:
#         if wins1 >= threshold:
#             return rank
#     return "🌱 Новичок"


# ─── КЛАВІАТУРИ ──────────────────────────────────────────────────────────────

def cities_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🏙 {c}", callback_data=f"rt_city_{c}")]
        for c in RESULT_CITIES
    ])


def groups_kb(city: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=info["label"],
            callback_data=f"rt_group_{city}|{key}"
        )]
        for key, info in RATING_GROUPS.items()
    ] + [[InlineKeyboardButton(text="◀️ Назад", callback_data="rt_back")]])


# ─── ХЕНДЛЕРИ ────────────────────────────────────────────────────────────────

@router.message(F.text == "🏅 Лидеры месяца")
async def show_rating_menu(message: Message):
    await message.answer(
        "🏅 *Лидеры месяца*\n\nВыбери город:",
        reply_markup=cities_kb(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "rt_back")
async def rt_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏅 *Лидеры месяца*\n\nВыбери город:",
        reply_markup=cities_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rt_city_"))
async def rt_city_chosen(callback: CallbackQuery):
    city = callback.data.replace("rt_city_", "")
    await callback.message.edit_text(
        f"🏙 *{city}*\n\nВыбери тип игр:",
        reply_markup=groups_kb(city),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rt_group_"))
async def rt_group_chosen(callback: CallbackQuery):
    city, group_key = callback.data.replace("rt_group_", "").split("|", 1)

    group_label = RATING_GROUPS[group_key]["label"]
    sorted_teams, total_games = await get_rating(city, group_key)

    if not sorted_teams:
        await callback.message.edit_text(
            f"📭 В категории *{group_label}* для города *{city}* пока нет результатов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"rt_city_{city}")
            ]]),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    # ─── Лідер з рандомним фото ──────────────────────────────────────────────
    leader_name, leader_data = sorted_teams[0]
    leader_photos = leader_data["photos"]
    leader_w1     = leader_data["w1"]
    leader_w2     = leader_data["w2"]
    leader_w3     = leader_data["w3"]
    # leader_rank   = get_rank(leader_w1)  # ранги тимчасово вимкнено

    leader_text = (
        f"👑 *Лидер — {city} / {group_label}*\n\n"
        f"*{leader_name}*\n"
        f"🥇 {leader_w1} побед   🥈 {leader_w2}   🥉 {leader_w3}"
    )

    if leader_photos:
        random_photo = random.choice(leader_photos)
        await callback.message.answer_photo(
            photo=random_photo,
            caption=leader_text,
            parse_mode="Markdown"
        )
    else:
        await callback.message.answer(leader_text, parse_mode="Markdown")

    # ─── Статистика + список команд ──────────────────────────────────────────
    #total_w1   = sum(d["w1"] for _, d in sorted_teams)
    #total_top3 = sum(d["w1"] + d["w2"] + d["w3"] for _, d in sorted_teams)

    text = (
        f"📊 *{city} — {group_label}*\n\n"
        f"🎮 Проведено игр: {total_games}\n"
    #    f"🥇 Первых мест разыграно: {total_w1}\n"
    #    f"🏅 Попаданий в топ-3: {total_top3}\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )

    for i, (team_name, tdata) in enumerate(sorted_teams, 1):
        w1, w2, w3 = tdata["w1"], tdata["w2"], tdata["w3"]
        # rank = get_rank(w1)  # ранги тимчасово вимкнено
        pos_icon = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += (
            f"{pos_icon} *{team_name}*\n"
            f"   🥇 {w1}  🥈 {w2}  🥉 {w3}\n\n"
        )

    text += (
        "━━━━━━━━━━━━━━━━━━\n"
        "Общий рейтинг команд и их ранги можно посмотреть на оффициальном сайте: \n"
        "[Ruda Games](https://rudagames.com)"
    )

    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад к типам игр", callback_data=f"rt_city_{city}")
    ]])

    await callback.message.answer(text, reply_markup=back_kb, parse_mode="Markdown")
    await callback.answer()
