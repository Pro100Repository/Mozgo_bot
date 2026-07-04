# handlers/quiz.py — квіз "Попробуй свои силы"

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    CATEGORIES, get_questions, count_questions,
    save_quiz_result, Q_OPEN
)

router = Router()

QUESTIONS_PER_QUIZ = 10

# ─── РЕЗУЛЬТАТИ: тексти залежно від кількості правильних відповідей ────────
# Формат: (мін_включно, макс_включно, заголовок, текст)
RESULT_TEXTS = [
    (0,  3,  "🫣 Новичок",
     "Похоже, квиз — не твоя стихия... пока что! "
     "Приходи на игры, там ты точно раскроешься 😄"),
    (4,  5,  "🙂 Любитель",
     "Неплохой результат! Базу ты знаешь, "
     "но есть куда расти. Попробуй ещё раз?"),
    (6,  7,  "😎 Знаток",
     "Крепкий середнячок! Ты явно бываешь на квизах "
     "или просто хорошо знаешь жизнь 😏"),
    (8,  9,  "🔥 Профи",
     "Почти идеально! Один-два вопроса тебя подвели. "
     "Ещё немного — и ты легенда!"),
    (10, 10, "🏆 Квизмонстр!",
     "10 из 10! Ты настоящий квизмонстр! "
     "Срочно записывайся на игру — ты нужен своей команде! 💪"),
]


def get_result_text(correct: int, total: int) -> str:
    for mn, mx, title, text in RESULT_TEXTS:
        if mn <= correct <= mx:
            return f"{title}\n\n{text}\n\n✅ Правильных ответов: {correct} из {total}"
    return f"Результат: {correct} из {total}"


# ─── FSM ─────────────────────────────────────────────────────────────────────

class QuizState(StatesGroup):
    choosing_category = State()
    answering         = State()   # кнопки
    answering_open    = State()   # открытый ввод


# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ─────────────────────────────────────────────────

def options_keyboard(q_id: int, options: list[str]) -> InlineKeyboardMarkup:
    """Кнопки с вариантами ответа (A/B/C/D)"""
    labels = ["A", "B", "C", "D"]
    buttons = [
        [InlineKeyboardButton(
            text=f"{labels[i]}. {opt}",
            callback_data=f"quiz_ans_{q_id}_{labels[i]}"
        )]
        for i, opt in enumerate(options) if opt
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def categories_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=cat, callback_data=f"quiz_cat_{cat}")]
        for cat in CATEGORIES
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_question(message_or_callback, state: FSMContext, edit: bool = False):
    """Отправляет текущий вопрос пользователю"""
    data   = await state.get_data()
    questions = data["questions"]
    index     = data["index"]

    q = questions[index]
    q_id, q_type, question, opt_a, opt_b, opt_c, opt_d, correct, media_id, media_type = q

    total  = len(questions)
    is_open = (q_type == Q_OPEN)

    # Варіанти для закритих питань
    options = [o for o in [opt_a, opt_b, opt_c, opt_d] if o]

    # Зберігаємо мапу "буква -> текст варіанта" (порядок відповідає кнопкам)
    # та сирий текст правильної відповіді. Порівняння з обраним варіантом
    # відбувається за ТЕКСТОМ (див. quiz_answer_chosen), а не за буквою,
    # щоб не залежати від того, як саме адмін заповнив поле "correct".
    if not is_open and options:
        labels = ["A", "B", "C", "D"]
        options_map = {lbl: txt for lbl, txt in zip(labels, options)}

        def _normalize(s: str) -> str:
            return " ".join(s.strip().lower().split())

        correct_variants = [_normalize(v) for v in correct.split("|")]
        if not any(_normalize(txt) in correct_variants for txt in options_map.values()):
            # Правильна відповідь з БД не збігається за текстом з жодним
            # видимим варіантом — ознака биття даних у цьому питанні.
            print(f"⚠️ QUIZ: правильна відповідь не знайдена серед варіантів "
                  f"для питання id={q_id}. correct='{correct}', options={options}")

        await state.update_data(current_options_map=options_map,
                                current_correct_text=correct.strip())
    else:
        await state.update_data(current_correct_text=correct.strip())

    caption = f"❓ Вопрос {index + 1} из {total}\n\n{question}"
    if not is_open:
        caption += "\n\nВыбери правильный ответ 👇"
    else:
        caption += "\n\n✍️ Напиши свой ответ"

    keyboard = options_keyboard(q_id, options) if not is_open else None

    # Відправляємо в залежності від типу
    msg = message_or_callback if isinstance(message_or_callback, Message) \
        else message_or_callback.message

    if media_id:
        if media_type == "photo":
            await msg.answer_photo(photo=media_id, caption=caption, reply_markup=keyboard)
        elif media_type == "audio":
            await msg.answer_audio(audio=media_id, caption=caption, reply_markup=keyboard)
        elif media_type == "video":
            await msg.answer_video(video=media_id, caption=caption, reply_markup=keyboard)
        elif media_type == "voice":
            await msg.answer_voice(voice=media_id, caption=caption, reply_markup=keyboard)
    else:
        await msg.answer(caption, reply_markup=keyboard)

    if is_open:
        await state.set_state(QuizState.answering_open)
    else:
        await state.set_state(QuizState.answering)


async def process_result(message: Message, state: FSMContext):
    """Показує фінальний результат і зберігає в БД"""
    data = await state.get_data()
    correct = data.get("correct", 0)
    total   = len(data["questions"])
    category = data["category"]
    await state.clear()

    result_text = get_result_text(correct, total)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сыграть ещё раз", callback_data=f"quiz_cat_{category}")],
        [InlineKeyboardButton(text="📋 Выбрать категорию", callback_data="quiz_choose")],
    ])

    await message.answer(
        f"🏁 Квиз завершён!\n\n{result_text}",
        reply_markup=keyboard
    )

    # Зберігаємо результат
    await save_quiz_result(
        user_id=message.from_user.id,
        username=message.from_user.username or message.from_user.first_name,
        category=category,
        correct=correct,
        total=total
    )


# ─── ХЕНДЛЕРИ ────────────────────────────────────────────────────────────────

@router.message(F.text == "🎯 Попробуй свои силы")
async def quiz_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🎯 *Попробуй свои силы!*\n\n"
        "Выбери категорию:",
        reply_markup=categories_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(QuizState.choosing_category)


@router.callback_query(F.data == "quiz_choose")
async def quiz_choose_category(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "🎯 Выбери категорию:",
        reply_markup=categories_keyboard()
    )
    await state.set_state(QuizState.choosing_category)
    await callback.answer()


@router.callback_query(F.data.startswith("quiz_cat_"))
async def quiz_category_chosen(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("quiz_cat_", "")

    total = await count_questions(category)
    if total == 0:
        await callback.message.answer(
            f"😔 В категории «{category}» пока нет вопросов.\n"
            "Загляни позже!"
        )
        await callback.answer()
        await state.clear()
        return

    questions = await get_questions(category, limit=QUESTIONS_PER_QUIZ)

    await state.update_data(
        questions=questions,
        index=0,
        correct=0,
        category=category
    )

    await callback.message.answer(
        f"🚀 Начинаем! Категория: *{category}*\n"
        f"Вопросов: {len(questions)}. Удачи! 🍀",
        parse_mode="Markdown"
    )
    await callback.answer()
    await send_question(callback, state)


@router.callback_query(F.data.startswith("quiz_ans_"))
async def quiz_answer_chosen(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа с кнопки (закрытый вопрос)"""
    _, _, q_id_str, chosen_label = callback.data.split("_", 3)

    data = await state.get_data()
    options_map  = data.get("current_options_map", {})
    correct_text = data.get("current_correct_text", "")
    index   = data["index"]
    correct = data["correct"]

    chosen_text = options_map.get(chosen_label.upper(), "")

    def normalize(s: str) -> str:
        return " ".join(s.strip().lower().split())

    # Допускаємо кілька правильних варіантів через "|" в полі correct
    correct_variants = [normalize(v) for v in correct_text.split("|")]
    is_correct = normalize(chosen_text) in correct_variants

    # Для показу як основну беремо першу відповідь (до "|"),
    # або, якщо вона не збігається з жодним варіантом кнопок,
    # шукаємо текст кнопки, що відповідає правильній відповіді
    main_correct = correct_text.split("|")[0].strip()
    displayed_correct = main_correct
    for txt in options_map.values():
        if normalize(txt) in correct_variants:
            displayed_correct = txt
            break

    if is_correct:
        await callback.message.answer(f"✅ Правильно! 🎉")
        correct += 1
    else:
        await callback.message.answer(
            f"❌ Неправильно.\nПравильный ответ: *{displayed_correct}*",
            parse_mode="Markdown"
        )

    await callback.answer("✅" if is_correct else "❌")

    index += 1
    await state.update_data(index=index, correct=correct)

    if index >= len(data["questions"]):
        await process_result(callback.message, state)
    else:
        await send_question(callback, state)


@router.message(QuizState.answering_open)
async def quiz_open_answer(message: Message, state: FSMContext):
    """Обработка открытого ответа (пользователь пишет текстом)"""
    data = await state.get_data()
    correct_text = data.get("current_correct_text", "")
    index   = data["index"]
    correct = data["correct"]

    # Нормалізація: прибираємо пробіли, приводимо до нижнього регістру
    def normalize(s: str) -> str:
        return " ".join(s.strip().lower().split())

    user_answer    = normalize(message.text)
    correct_answer = normalize(correct_text)

    # Допускаємо кілька правильних відповідей через "|" в полі correct
    correct_variants = [normalize(v) for v in correct_text.split("|")]
    is_correct = user_answer in correct_variants

    if is_correct:
        await message.answer("✅ Правильно! 🎉")
        correct += 1
    else:
        # Показуємо першу відповідь (до "|") як основну
        main_correct = correct_text.split("|")[0].strip()
        await message.answer(
            f"❌ Неправильно.\nПравильный ответ: *{main_correct}*",
            parse_mode="Markdown"
        )

    index += 1
    await state.update_data(index=index, correct=correct)

    if index >= len(data["questions"]):
        await process_result(message, state)
    else:
        await send_question(message, state)


# Захист: якщо під час квізу натиснули кнопку головного меню
MENU_BUTTONS = [
    "📅 Предстоящие игры", "🏅 Рейтинг команд",
    "❓ FAQ", "📞 Контакты", "🎯 Попробуй свои силы"
]

@router.message(QuizState.answering_open, F.text.in_(MENU_BUTTONS))
async def quiz_cancel_on_menu(message: Message, state: FSMContext):
    await state.clear()
