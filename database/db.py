# database/db.py — робота з базою даних SQLite

import aiosqlite
from config import DATABASE_NAME


async def init_db():
    """Створює таблиці при першому запуску бота"""
    async with aiosqlite.connect(DATABASE_NAME) as db:

        # Таблиця майбутніх ігор
        await db.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                location TEXT,
                registration_link TEXT DEFAULT '',
                max_players INTEGER DEFAULT 0,
                city TEXT DEFAULT ''
            )
        """)

        # Таблиця результатів попередніх ігор
        await db.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_title TEXT NOT NULL,
                game_date TEXT NOT NULL,
                team_name TEXT NOT NULL,
                place INTEGER,
                score REAL
            )
        """)

        await db.commit()
        print("✅ База даних готова")


async def migrate_db():
    """Додає нові колонки якщо вони ще не існують (міграція)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("PRAGMA table_info(games)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]

        if "city" not in columns:
            await db.execute("ALTER TABLE games ADD COLUMN city TEXT DEFAULT ''")
            await db.commit()
            print("✅ Миграция: добавлено поле city")

        if "registration_link" not in columns:
            await db.execute("ALTER TABLE games ADD COLUMN registration_link TEXT DEFAULT ''")
            await db.commit()
            print("✅ Миграция: добавлено поле registration_link")


# ─── ІГРИ ───────────────────────────────

async def get_upcoming_games(with_id: bool = False):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if with_id:
            query = "SELECT id, title, date, location, registration_link, max_players, city FROM games ORDER BY date"
        else:
            query = "SELECT title, date, location, registration_link, city FROM games ORDER BY date"
        async with db.execute(query) as cursor:
            return await cursor.fetchall()


async def get_game_by_id(game_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT id, title, date, location, registration_link, max_players, city FROM games WHERE id = ?",
            (game_id,)
        ) as cursor:
            return await cursor.fetchone()


async def add_game(title, date, location, registration_link="", max_players=0, city=""):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO games (title, date, location, registration_link, max_players, city) VALUES (?, ?, ?, ?, ?, ?)",
            (title, date, location, registration_link, max_players, city)
        )
        await db.commit()


async def get_cities():
    """Повертає список унікальних міст"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT DISTINCT city FROM games WHERE city != '' ORDER BY city"
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def get_games_by_city(city: str):
    """Повертає ігри в конкретному місті"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT title, date, location, registration_link FROM games WHERE LOWER(city) = LOWER(?) ORDER BY date",
            (city,)
        ) as cursor:
            return await cursor.fetchall()


async def delete_game(game_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("DELETE FROM games WHERE id = ?", (game_id,))
        await db.commit()
        return cursor.rowcount > 0


# ─── РЕЗУЛЬТАТИ ─────────────────────────

async def get_results(limit: int = 10):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT game_title, game_date, team_name, place, score FROM results ORDER BY game_date DESC LIMIT ?",
            (limit,)
        ) as cursor:
            return await cursor.fetchall()


async def add_result(game_title, game_date, team_name, place, score):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO results (game_title, game_date, team_name, place, score) VALUES (?, ?, ?, ?, ?)",
            (game_title, game_date, team_name, place, score)
        )
        await db.commit()


# ─── РЕЙТИНГ ────────────────────────────

async def get_top_teams(limit: int = 10):
    """Рейтинг команд: рахуємо очки за місця (1 місце = 3 очки, 2 = 2, 3 = 1)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("""
            SELECT
                team_name,
                COUNT(*) as games_played,
                SUM(CASE WHEN place = 1 THEN 3
                         WHEN place = 2 THEN 2
                         WHEN place = 3 THEN 1
                         ELSE 0 END) as points,
                SUM(CASE WHEN place = 1 THEN 1 ELSE 0 END) as gold,
                SUM(CASE WHEN place = 2 THEN 1 ELSE 0 END) as silver,
                SUM(CASE WHEN place = 3 THEN 1 ELSE 0 END) as bronze,
                MAX(score) as best_score,
                ROUND(AVG(score), 1) as avg_score
            FROM results
            GROUP BY team_name
            ORDER BY points DESC, avg_score DESC
            LIMIT ?
        """, (limit,)) as cursor:
            return await cursor.fetchall()


async def get_records():
    """Таблиця рекордів — найкращі результати в історії"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("""
            SELECT team_name, game_title, game_date, score
            FROM results
            ORDER BY score DESC
            LIMIT 5
        """) as cursor:
            top_scores = await cursor.fetchall()

        async with db.execute("""
            SELECT team_name, COUNT(*) as wins
            FROM results
            WHERE place = 1
            GROUP BY team_name
            ORDER BY wins DESC
            LIMIT 3
        """) as cursor:
            most_wins = await cursor.fetchall()

        async with db.execute("""
            SELECT team_name, COUNT(*) as games
            FROM results
            GROUP BY team_name
            ORDER BY games DESC
            LIMIT 3
        """) as cursor:
            most_games = await cursor.fetchall()

        return top_scores, most_wins, most_games
