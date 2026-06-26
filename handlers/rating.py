# handlers/rating.py — рейтинг команд и таблица рекордов

from aiogram import Router, F
from aiogram.types import Message
from database.db import get_top_teams, get_records

router = Router()


@router.message(F.text == "🏅 Рейтинг команд")
async def show_rating(message: Message):
    teams = await get_top_teams(limit=10)

    if not teams:
        await message.answer(
            "📭 Рейтинг пока пустой.\n"
            "Он сформируется после первых игр!"
        )
        return

    text = "🏅 *Рейтинг команд:*\n\n"
    text += "Очки: 🥇=3 | 🥈=2 | 🥉=1\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"

    position_icons = ["🥇", "🥈", "🥉"]

    for i, team in enumerate(teams):
        team_name, games_played, points, gold, silver, bronze, best_score, avg_score = team
        icon = position_icons[i] if i < 3 else f"{i+1}."
        text += f"{icon} *{team_name}*\n"
        text += f"   ⭐ Очки: {points} | 🎮 Игр: {games_played}\n"
        text += f"   🥇{gold} 🥈{silver} 🥉{bronze} | Средний балл: {avg_score}\n\n"

    await message.answer(text, parse_mode="Markdown")


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
