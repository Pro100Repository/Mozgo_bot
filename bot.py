import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import faq, games, start, admin, rating, contacts, quiz, admin_quiz, admin_results, results
from database.db import init_db, migrate_db, cleanup_finished_games, init_results_db

logging.basicConfig(level=logging.INFO)


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

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(rating.router)
    dp.include_router(results.router)
    dp.include_router(quiz.router)
    dp.include_router(games.router)
    dp.include_router(faq.router)
    dp.include_router(contacts.router)
    dp.include_router(admin_results.router)
    dp.include_router(admin_quiz.router)
    dp.include_router(admin.router)

    # Запускаем фоновую очистку завершённых игр параллельно с ботом
    asyncio.create_task(cleanup_loop())

    print("✅ Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
