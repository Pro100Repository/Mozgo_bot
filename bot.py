import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import faq, games, start, admin, rating, contacts
from database.db import init_db, migrate_db

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()
    await migrate_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(rating.router)
    dp.include_router(games.router)
    dp.include_router(faq.router)
    dp.include_router(contacts.router)
    dp.include_router(admin.router)

    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
