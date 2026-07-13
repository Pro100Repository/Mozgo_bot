# handlers/rules.py — правила игр

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from handlers.start import main_menu

router = Router()

# ─── ТЕКСТИ ПРАВИЛ ───────────────────────────────────────────────────────────
# Редактируй тексты ниже под каждую игру

RULES = {
    "mozgoboynya": {
        "title": "🧠 Правила Мозгобойни",
        "pages": [
            # Сторінка 1
            (
                "🧠 *Правила Мозгобойни*\n\n"
                "📍 *1. Количество участников*\n\n"
                "Число команд ограничивается вместимостью помещения.\n\n"
                "Количество человек в команде — от 2 до 10.\n"
                "По опыту идеальный состав — 7–8 человек.\n\n"
                "Участвовать могут лица от 12 лет. Лица младше — только с законным представителем."
            ),
            # Сторінка 2
            (
                "🧠 *Правила Мозгобойни*\n\n"
                "📍 *2. Регистрация на игру*\n\n"
                "Для участия нужно зарегистрироваться на сайте *rudagames.com*\n\n"
                "Название команды — буквы или цифры, без нецензурной лексики.\n\n"
                "Места ограничены — кто успел, тот и играет. Остальные — в резерв.\n\n"
                "⚠️ При дублированной регистрации учитывается только первая!\n\n"
                "💰 Стоимость: *700 рублей с человека*. Оплата наличными в перерыв после 3 тура."
            ),
            # Сторінка 3
            (
                "🧠 *Правила Мозгобойни*\n\n"
                "📍 *3. Регламент*\n\n"
                "Продолжительность игры — примерно *2 часа 15 минут*.\n\n"
                "Два перерыва по 10 минут — после 3-го и 6-го туров.\n\n"
                "Во время игры можно заказывать еду и напитки 🍕🍹\n\n"
                "Курение — только на улице 🚭"
            ),
            # Сторінка 4
            (
                "🧠 *Правила Мозгобойни*\n\n"
                "📍 *4. Формат — 7 туров по 7 вопросов*\n\n"
                "1️⃣ Классический текстовый тур (50 сек)\n"
                "2️⃣ «3 факта О» — три факта об одном объекте (50 сек)\n"
                "3️⃣ Медиа-тур — аудио и видео вопросы\n"
                "4️⃣ Текстовый тур + Интерактив «Выбор тура» (100 сек)\n"
                "5️⃣ Тур с картинками — визуальный тур (50 сек)\n"
                "6️⃣ Тур повышенной сложности (100 сек)\n"
                "7️⃣ Финальный тур\n\n"
                "Вопросы показываются на экране и зачитываются ведущим, затем — быстрый повтор и обратный отсчёт."
            ),
            # Сторінка 5
            (
                "🧠 *Правила Мозгобойни*\n\n"
                "📍 *5. Тай-брейк и сложность*\n\n"
                "При равенстве очков побеждает команда, которая была лучше в последнем туре "
                "(если равенство — смотрим 6 тур, 5 тур и т.д.).\n\n"
                "Все вопросы берутся кругозором, логикой и эрудицией 🧩\n\n"
                "После каждого тура оглашаются правильные ответы — обычно это самые весёлые моменты игры 😄"
            ),
        ]
    },
    "tuc_tuc": {
        "title": "🎵 Правила Туц Туц QUIZ",
        "pages": [
            (
                "🎵 *Правила Туц Туц QUIZ*\n\n"
                "Здесь будут правила Туц Туц QUIZ.\n\n"
                "✏️ Администратор может отредактировать этот текст в файле `handlers/rules.py`"
            ),
        ]
    },
    "kvizmashina": {
        "title": "🎮 Правила Квизмашины",
        "pages": [
            (
                "🎮 *Правила Квизмашины*\n\n"
                "Здесь будут правила Квизмашины.\n\n"
                "✏️ Администратор может отредактировать этот текст в файле `handlers/rules.py`"
            ),
        ]
    },
}


# ─── КЛАВІАТУРИ ──────────────────────────────────────────────────────────────

def rules_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Мозгобойня",     callback_data="rules_mozgoboynya_0")],
        [InlineKeyboardButton(text="🎵 Туц Туц QUIZ",   callback_data="rules_tuc_tuc_0")],
        [InlineKeyboardButton(text="🎮 Квизмашина",     callback_data="rules_kvizmashina_0")],
        [InlineKeyboardButton(text="🏠 Главное меню",   callback_data="rules_close")],
    ])


def page_kb(game: str, page: int, total: int):
    buttons = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"rules_{game}_{page - 1}"))
    if page < total - 1:
        nav.append(InlineKeyboardButton(text="Далее ▶️", callback_data=f"rules_{game}_{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="📋 К выбору игры", callback_data="rules_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── ХЕНДЛЕРИ ────────────────────────────────────────────────────────────────

@router.message(F.text == "📖 Правила")
async def show_rules_menu(message: Message):
    await message.answer(
        "📖 *Правила игр*\n\nВыбери игру:",
        reply_markup=rules_menu_kb(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "rules_menu")
async def rules_back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📖 *Правила игр*\n\nВыбери игру:",
        reply_markup=rules_menu_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "rules_close")
async def rules_close(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("👇 Главное меню:", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("rules_"))
async def show_rules_page(callback: CallbackQuery):
    # rules_GAME_PAGE
    parts = callback.data.replace("rules_", "").rsplit("_", 1)
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer()
        return

    game = parts[0]
    page = int(parts[1])

    if game not in RULES:
        await callback.answer("Правила не найдены.")
        return

    rule_data = RULES[game]
    pages = rule_data["pages"]
    total = len(pages)
    page = max(0, min(page, total - 1))

    text = pages[page]
    if total > 1:
        text += f"\n\n_Страница {page + 1} из {total}_"

    await callback.message.edit_text(
        text,
        reply_markup=page_kb(game, page, total),
        parse_mode="Markdown"
    )
    await callback.answer()
