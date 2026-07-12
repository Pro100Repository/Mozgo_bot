# handlers/rating.py — рейтинг команд и таблица рекордов

from aiogram import Router, F
from aiogram.types import Message
from database.db import get_records

router = Router()

# Хендлер "🏅 Рейтинг команд" перенесён в handlers/results.py (новая логика
# с выбором города и типа игр). Здесь его больше нет, чтобы не было дублей.


@router.message(F.text == "🎖 Таблица рекордов")
async def show_records(message: Message):
    top_scores, most_wins, most_games = await get_records()

    if not top_scores:
        await message.answer(
            "📭 Рекордов пока нет.\n"
            "Они появятся после первых игр!"
        )
        return

    text = "🎖 *Таблица рекордов:*\n\n"

    text += "🔥 *Лучшие результаты в истории:*\n"
    for i, row in enumerate(top_scores):
        team_name, game_title, game_date, score = row
        icon = ["🥇", "🥈", "🥉", "4.", "5."][i]
        text += f"{icon} {team_name} — *{score} баллов*\n"
        text += f"   ({game_title}, {game_date})\n"

    text += "\n"

    if most_wins:
        text += "👑 *Больше всего побед:*\n"
        for i, row in enumerate(most_wins):
            team_name, wins = row
            icon = ["🥇", "🥈", "🥉"][i]
            text += f"{icon} {team_name} — {wins} побед\n"
        text += "\n"

    if most_games:
        text += "🎮 *Самые опытные команды:*\n"
        for i, row in enumerate(most_games):
            team_name, games = row
            icon = ["🥇", "🥈", "🥉"][i]
            text += f"{icon} {team_name} — {games} игр\n"

    await message.answer(text, parse_mode="Markdown")
