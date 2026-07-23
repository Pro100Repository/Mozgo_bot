# database/db.py — робота з базою даних SQLite

import aiosqlite
from datetime import datetime, timedelta
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
                event_datetime TEXT,
                location TEXT,
                price TEXT DEFAULT '',
                registration_link TEXT DEFAULT '',
                max_players INTEGER DEFAULT 0,
                city TEXT DEFAULT '',
                photo_id TEXT DEFAULT ''
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

        # ─── КВІЗ ────────────────────────────────

        # Таблиця питань
        await db.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category    TEXT NOT NULL,
                q_type      TEXT NOT NULL DEFAULT 'text',
                question    TEXT NOT NULL,
                option_a    TEXT,
                option_b    TEXT,
                option_c    TEXT,
                option_d    TEXT,
                correct     TEXT NOT NULL,
                media_id    TEXT DEFAULT '',
                media_type  TEXT DEFAULT ''
            )
        """)

        # Таблиця результатів квізу
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                username    TEXT,
                category    TEXT NOT NULL,
                correct     INTEGER DEFAULT 0,
                total       INTEGER DEFAULT 0,
                played_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.commit()
        print("✅ Таблиці квізу готові")


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

        if "event_datetime" not in columns:
            await db.execute("ALTER TABLE games ADD COLUMN event_datetime TEXT")
            await db.commit()
            print("✅ Миграция: добавлено поле event_datetime")

        if "photo_id" not in columns:
            await db.execute("ALTER TABLE games ADD COLUMN photo_id TEXT DEFAULT ''")
            await db.commit()
            print("✅ Миграция: добавлено поле photo_id")

        if "price" not in columns:
            await db.execute("ALTER TABLE games ADD COLUMN price TEXT DEFAULT ''")
            await db.commit()
            print("✅ Миграция: добавлено поле price")


# ─── ІГРИ ───────────────────────────────

async def get_upcoming_games(with_id: bool = False):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if with_id:
            query = "SELECT id, title, date, location, price, registration_link, max_players, city FROM games ORDER BY date"
        else:
            query = "SELECT title, date, location, price, registration_link, city FROM games ORDER BY date"
        async with db.execute(query) as cursor:
            return await cursor.fetchall()


async def get_game_by_id(game_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT id, title, date, location, price, registration_link, max_players, city FROM games WHERE id = ?",
            (game_id,)
        ) as cursor:
            return await cursor.fetchone()


async def add_game(title, date, location, registration_link="", max_players=0, city="", event_datetime=None, photo_id="", price=""):
    """
    event_datetime — дата и время начала игры в формате ISO ("2026-06-25 20:00"),
    нужно для автоматического удаления завершившихся игр.
    Если не передано — берётся как None (игра не будет удаляться автоматически).
    photo_id — file_id фотографии в Telegram (не сама картинка, а её идентификатор).
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO games (title, date, location, price, registration_link, max_players, city, event_datetime, photo_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, date, location, price, registration_link, max_players, city, event_datetime, photo_id)
        )
        await db.commit()


def parse_game_datetime(date_str: str, time_str: str):
    """
    Преобразует дату (ДД.MM.ГГГГ) и время (ЧЧ:MM) в строку ISO для хранения в БД.
    Возвращает None если формат не распознан.
    """
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return None


async def cleanup_finished_games(hours_after_start: int = 2):
    """
    Удаляет игры, начало которых было больше чем hours_after_start часов назад.
    Игры без указанного event_datetime не трогает (чтобы не удалить случайно).
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT id, event_datetime FROM games WHERE event_datetime IS NOT NULL AND event_datetime != ''"
        ) as cursor:
            rows = await cursor.fetchall()

        now = datetime.now()
        ids_to_delete = []

        for game_id, event_datetime in rows:
            try:
                game_dt = datetime.strptime(event_datetime, "%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                continue  # пропускаем некорректные значения

            if now >= game_dt + timedelta(hours=hours_after_start):
                ids_to_delete.append(game_id)

        if ids_to_delete:
            await db.executemany(
                "DELETE FROM games WHERE id = ?",
                [(gid,) for gid in ids_to_delete]
            )
            await db.commit()

        return len(ids_to_delete)


async def get_cities():
    """Повертає список унікальних міст"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT DISTINCT city FROM games WHERE city != '' ORDER BY city"
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def get_games_by_city(city: str):
    """Повертає ігри в конкретному місті (тільки ті, що ще не завершились)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT title, date, location, price, registration_link, event_datetime, photo_id "
            "FROM games WHERE LOWER(city) = LOWER(?) ORDER BY date",
            (city,)
        ) as cursor:
            rows = await cursor.fetchall()

    now = datetime.now()
    result = []
    for title, date, location, price, registration_link, event_datetime, photo_id in rows:
        if event_datetime:
            try:
                game_dt = datetime.strptime(event_datetime, "%Y-%m-%d %H:%M")
                if now >= game_dt + timedelta(hours=2):
                    continue
            except (ValueError, TypeError):
                pass
        result.append((title, date, location, price, registration_link, photo_id))

    return result


async def delete_game(game_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("DELETE FROM games WHERE id = ?", (game_id,))
        await db.commit()
        return cursor.rowcount > 0


async def set_game_photo(game_id: int, photo_id: str) -> bool:
    """Прикрепляет фото к игре по её ID. Возвращает True если игра найдена."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(
            "UPDATE games SET photo_id = ? WHERE id = ?",
            (photo_id, game_id)
        )
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


# ─── КВІЗ ────────────────────────────────

CATEGORIES = ["Классика", "Туц Туц Quiz", "Квизмашина"]

# Типи питань
Q_TEXT  = "text"    # текст + 4 варіанти
Q_OPEN  = "open"    # відкрита відповідь (без варіантів)
Q_PHOTO = "photo"   # фото + варіанти або відкрита
Q_AUDIO = "audio"   # аудіо + варіанти або відкрита
Q_VIDEO = "video"   # відео + варіанти або відкрита


async def add_question(category, q_type, question, correct,
                       option_a="", option_b="", option_c="", option_d="",
                       media_id="", media_type=""):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO questions
                (category, q_type, question, option_a, option_b, option_c, option_d,
                 correct, media_id, media_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (category, q_type, question,
              option_a, option_b, option_c, option_d,
              correct, media_id, media_type))
        await db.commit()


async def get_questions(category: str, limit: int = 10):
    """Повертає випадкові limit питань з категорії"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("""
            SELECT id, q_type, question, option_a, option_b, option_c, option_d,
                   correct, media_id, media_type
            FROM questions
            WHERE category = ?
            ORDER BY RANDOM()
            LIMIT ?
        """, (category, limit)) as cursor:
            return await cursor.fetchall()


async def count_questions(category: str) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM questions WHERE category = ?", (category,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def delete_question(question_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        await db.commit()
        return cursor.rowcount > 0


async def list_questions(category: str):
    """Список питань для адміна (ID + скорочений текст)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("""
            SELECT id, q_type, question, correct
            FROM questions WHERE category = ?
            ORDER BY id
        """, (category,)) as cursor:
            return await cursor.fetchall()


async def save_quiz_result(user_id: int, username: str, category: str,
                           correct: int, total: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO quiz_results (user_id, username, category, correct, total)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, category, correct, total))
        await db.commit()


async def get_user_quiz_stats(user_id: int, category: str):
    """Найкращий результат користувача в категорії"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("""
            SELECT MAX(correct), total, COUNT(*)
            FROM quiz_results
            WHERE user_id = ? AND category = ?
        """, (user_id, category)) as cursor:
            return await cursor.fetchone()


# ─── РЕЗУЛЬТАТИ ІГОР (НОВА СИСТЕМА) ──────────────────────────────────────────

RESULT_CITIES    = ["Москва «бар Liberty»", "Красногорск", "Истра", "Обнинск"]
RESULT_GAME_TYPES = {
    "mozgoboynya": "Мозгобойня",
    "kvizmashina": "Квизмашина",
    "tuc_tuc":     "Туц Туц QUIZ",
}
# Групи для користувача
RATING_GROUPS = {
    "erudition": {"label": "🧠 Эрудиция", "types": ["mozgoboynya", "kvizmashina"]},
    "tuc_tuc":   {"label": "🎵 Туц Туц QUIZ",  "types": ["tuc_tuc"]},
}


async def init_results_db():
    """Створює таблицю результатів ігор"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS game_results (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                city          TEXT NOT NULL,
                game_type     TEXT NOT NULL,
                game_name     TEXT NOT NULL,
                place1_team   TEXT DEFAULT '',
                place1_photo  TEXT DEFAULT '',
                place2_team   TEXT DEFAULT '',
                place2_photo  TEXT DEFAULT '',
                place3_team   TEXT DEFAULT '',
                place3_photo  TEXT DEFAULT '',
                created_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.commit()


async def add_game_result(city, game_type, game_name,
                          place1_team='', place1_photo='',
                          place2_team='', place2_photo='',
                          place3_team='', place3_photo=''):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("""
            INSERT INTO game_results
                (city, game_type, game_name,
                 place1_team, place1_photo,
                 place2_team, place2_photo,
                 place3_team, place3_photo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (city, game_type, game_name,
              place1_team, place1_photo,
              place2_team, place2_photo,
              place3_team, place3_photo))
        await db.commit()
        return cursor.lastrowid


async def get_game_result(result_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT * FROM game_results WHERE id = ?", (result_id,)
        ) as cursor:
            return await cursor.fetchone()


async def update_game_result(result_id: int, **fields):
    """Оновлює довільні поля результату гри (для редагування)"""
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [result_id]
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(
            f"UPDATE game_results SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_game_result(result_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(
            "DELETE FROM game_results WHERE id = ?", (result_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_rating(city: str, group_key: str):
    """
    Повертає рейтинг команд для міста і групи типів ігор.
    group_key: 'erudition' або 'tuc_tuc'
    Повертає: список (team, wins1, wins2, wins3, total_games, photos)
    """
    types = RATING_GROUPS[group_key]["types"]
    placeholders = ",".join("?" * len(types))

    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Отримуємо всі результати
        async with db.execute(f"""
            SELECT place1_team, place1_photo,
                   place2_team, place2_photo,
                   place3_team, place3_photo
            FROM game_results
            WHERE city = ? AND game_type IN ({placeholders})
        """, [city] + types) as cursor:
            rows = await cursor.fetchall()

    # Рахуємо статистику по кожній команді
    from collections import defaultdict
    teams = defaultdict(lambda: {"w1": 0, "w2": 0, "w3": 0, "photos": []})

    total_games = len(rows)
    for p1t, p1p, p2t, p2p, p3t, p3p in rows:
        if p1t:
            teams[p1t]["w1"] += 1
            if p1p:
                teams[p1t]["photos"].append(p1p)
        if p2t:
            teams[p2t]["w2"] += 1
            if p2p:
                teams[p2t]["photos"].append(p2p)
        if p3t:
            teams[p3t]["w3"] += 1
            if p3p:
                teams[p3t]["photos"].append(p3p)

    # Сортуємо: спочатку за 1 місцями, потім за 2, потім за 3
    sorted_teams = sorted(
        teams.items(),
        key=lambda x: (x[1]["w1"], x[1]["w2"], x[1]["w3"]),
        reverse=True
    )

    return sorted_teams, total_games


async def list_game_results(city: str = None, game_type: str = None, limit: int = 20):
    """Список результатів для адміна"""
    conditions = []
    params = []
    if city:
        conditions.append("city = ?")
        params.append(city)
    if game_type:
        conditions.append("game_type = ?")
        params.append(game_type)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(f"""
            SELECT id, city, game_type, game_name,
                   place1_team, place2_team, place3_team, created_at
            FROM game_results
            {where}
            ORDER BY id DESC
            LIMIT ?
        """, params + [limit]) as cursor:
            return await cursor.fetchall()


# ─── ПІДПИСКИ НА РОЗСИЛКУ ────────────────────────────────────────────────────

async def init_subscriptions_db():
    """Створює таблицю підписок"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                city       TEXT NOT NULL,
                username   TEXT DEFAULT '',
                UNIQUE(user_id, city)
            )
        """)
        await db.commit()


async def subscribe(user_id: int, city: str, username: str = "") -> bool:
    """Підписати користувача на місто. Повертає True якщо підписка нова."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO subscriptions (user_id, city, username) VALUES (?, ?, ?)",
                (user_id, city, username)
            )
            await db.commit()
            return True
        except Exception:
            return False  # вже підписаний


async def unsubscribe(user_id: int, city: str) -> bool:
    """Відписати користувача від міста."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(
            "DELETE FROM subscriptions WHERE user_id = ? AND city = ?",
            (user_id, city)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_user_subscriptions(user_id: int) -> list:
    """Список міст на які підписаний користувач."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT city FROM subscriptions WHERE user_id = ? ORDER BY city",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def get_city_subscribers(city: str) -> list:
    """Список user_id всіх підписників міста."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT user_id FROM subscriptions WHERE city = ?",
            (city,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def remove_subscriber(user_id: int):
    """Видалити всі підписки користувача (заблокував бота)."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_subscription_stats() -> list:
    """Кількість підписників по кожному місту (від більшого до меншого)."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT city, COUNT(*) as cnt FROM subscriptions GROUP BY city ORDER BY cnt DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [(r[0], r[1]) for r in rows]


async def get_total_subscribers_count() -> int:
    """Кількість унікальних користувачів, підписаних хоча б на одне місто."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM subscriptions"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_games_for_broadcast(target_date: str) -> list:
    """
    Повертає ігри на конкретну дату для розсилки.
    target_date — рядок у форматі 'ГГГГ-ММ-ДД'
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("""
            SELECT title, date, location, price, registration_link, city, photo_id
            FROM games
            WHERE event_datetime LIKE ?
            ORDER BY event_datetime
        """, (f"{target_date}%",)) as cursor:
            return await cursor.fetchall()


# ─── МЕМ ДНЯ ─────────────────────────────────────────────────────────────────

async def init_meme_db():
    """Створює таблиці для мему дня"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Черга мемів (в порядку завантаження)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id    TEXT NOT NULL,
                added_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        # Підписники на мем дня
        await db.execute("""
            CREATE TABLE IF NOT EXISTS meme_subscribers (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT DEFAULT ''
            )
        """)
        await db.commit()


async def add_meme(photo_id: str):
    """Додає мем в кінець черги"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO memes (photo_id) VALUES (?)", (photo_id,)
        )
        await db.commit()


async def get_next_meme():
    """Повертає перший мем з черги (найстаріший)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT id, photo_id FROM memes ORDER BY id ASC LIMIT 1"
        ) as cursor:
            return await cursor.fetchone()


async def delete_meme(meme_id: int):
    """Видаляє мем з черги після відправки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("DELETE FROM memes WHERE id = ?", (meme_id,))
        await db.commit()


async def count_memes() -> int:
    """Кількість мемів в черзі"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM memes") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def meme_subscribe(user_id: int, username: str = "") -> bool:
    """Підписати на мем дня. Повертає True якщо підписка нова."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO meme_subscribers (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            await db.commit()
            return True
        except Exception:
            return False


async def meme_unsubscribe(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(
            "DELETE FROM meme_subscribers WHERE user_id = ?", (user_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def is_meme_subscribed(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT 1 FROM meme_subscribers WHERE user_id = ?", (user_id,)
        ) as cursor:
            return await cursor.fetchone() is not None


async def get_meme_subscribers() -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT user_id FROM meme_subscribers") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def remove_meme_subscriber(user_id: int):
    """Видалити підписника (заблокував бота)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "DELETE FROM meme_subscribers WHERE user_id = ?", (user_id,)
        )
        await db.commit()


# ─── СТАН ПЛАНУВАЛЬНИКА (щоб рестарт бота не дублював розсилки) ─────────────

async def init_scheduler_db():
    """Створює таблицю для зберігання дат останніх розсилок (переживає рестарт бота)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_state (
                key    TEXT PRIMARY KEY,
                value  TEXT
            )
        """)
        await db.commit()


async def get_scheduler_state(key: str):
    """Повертає збережене значення (наприклад, дату останньої розсилки) або None"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT value FROM scheduler_state WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_scheduler_state(key: str, value: str):
    """Зберігає значення (upsert)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO scheduler_state (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        await db.commit()
