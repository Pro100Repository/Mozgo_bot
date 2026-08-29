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

# ID админов, которым приходят уведомления о новых подписках/рассылках — через запятую
_subscription_admin_raw = os.getenv("SUBSCRIPTION_ADMIN_IDS", "")
SUBSCRIPTION_ADMIN_IDS = [int(x.strip()) for x in _subscription_admin_raw.split(",") if x.strip()]

if not SUBSCRIPTION_ADMIN_IDS:
    print(
        "⚠️ SUBSCRIPTION_ADMIN_IDS не найден в .env — уведомления о новых "
        "подписках отправляться не будут. Добавь строку SUBSCRIPTION_ADMIN_IDS=id1,id2 в .env"
    )

# Назва файлу бази даних
DATABASE_NAME = "quiz_bot.db"
