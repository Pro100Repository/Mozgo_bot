# config.py — загружает настройки из .env файла (безопасно для Git)

import os
from dotenv import load_dotenv

load_dotenv()  # подгружает переменные из файла .env

# Токен бота — берётся из .env, НИКОГДА не пишется прямо здесь
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError(
        "❌ BOT_TOKEN не найден! Проверь файл .env — он должен лежать "
        "в корне проекта и содержать строку BOT_TOKEN=твой_токен"
    )

# ID администраторов — также берутся из .env, через запятую
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip()]

# Назва файлу бази даних
DATABASE_NAME = "quiz_bot.db"
