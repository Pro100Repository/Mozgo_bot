import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import faq, games, start, admin, admin_games, rating, contacts, quiz, admin_quiz, admin_results, results, rules, subscription
from database.db import init_db, migrate_db, cleanup_finished_games, init_results_db, init_subscriptions_db

logging.basicConfig(level=logging.INFO)

# ─── ВРЕМЕННЫЙ ДИАГНОСТИЧЕСКИЙ РОУТЕР ────────────────────────────
# Ловит любое текстовое сообщение, которое не обработал ни один
# другой хендлер, и печатает его repr() — точные байты, включая
# невидимые символы. Удалить после диагностики!
debug_router = Router()

@debug_router.message(F.text)
async def debug_unhandled(message: Message):
    print(f"🔍 DEBUG необработанный текст: {repr(message.text)}")



async def cleanup_loop():
    """Фоновая задача: каждые 10 минут удаляет игры, начавшиеся более 2 часов назад"""
    while True:
        try:
            deleted = await cleanup_finished_games(hours_after_start=2)
            if deleted:
                print(f"🧹 Удалено завершённых игр: {deleted}")
        except Exception as e:
            print(f"⚠️ Ошибка при очистке игр: {e}")
        await asyncio.sleep(600)  # 10 минут


async def main():
    await init_db()
    await migrate_db()
    await init_results_db()
    await init_subscriptions_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(subscription.router)
    dp.include_router(rating.router)
    dp.include_router(results.router)
    dp.include_router(rules.router)
    dp.include_router(quiz.router)
    dp.include_router(games.router)
    dp.include_router(faq.router)
    dp.include_router(contacts.router)
    dp.include_router(admin_results.router)
    dp.include_router(admin_games.router)
    dp.include_router(admin_quiz.router)
    dp.include_router(admin.router)
    dp.include_router(debug_router)  # ВРЕМЕННЫЙ, удалить после диагностики

    # Запускаем фоновую очистку завершённых игр параллельно с ботом
    asyncio.create_task(cleanup_loop())

    print("✅ Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
