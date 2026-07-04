# handlers/admin_quiz.py — управление вопросами квиза (только для админов)

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from database.db import (
    CATEGORIES, add_question, delete_question, list_questions, count_questions,
    Q_TEXT, Q_OPEN, Q_PHOTO, Q_AUDIO, Q_VIDEO
)

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── FSM для добавления вопроса ──────────────────────────────────────────────

class AddQuestionForm(StatesGroup):
    choose_category = State()
    choose_type     = State()
    enter_question  = State()
    enter_media     = State()   # фото/аудіо/відео (якщо потрібно)
    enter_options   = State()   # варіанти відповідей (для закритих)
    enter_correct   = State()   # правильна відповідь


# ─── СТАРТ ────────────────────────────────────────────────────────────────────

@router.message(Command("add_question"))
async def cmd_add_question(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    await state.clear()

    buttons = [
        [InlineKeyboardButton(text=cat, callback_data=f"aq_cat_{cat}")]
        for cat in CATEGORIES
    ]
    await message.answer(
        "📚 *Добавление вопроса*\n\nШаг 1. Выбери категорию:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await state.set_state(AddQuestionForm.choose_category)


@router.callback_query(AddQuestionForm.choose_category, F.data.startswith("aq_cat_"))
async def aq_category_chosen(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("aq_cat_", "")
    await state.update_data(category=category)

    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Текст + 4 варианта",   callback_data="aq_type_text")],
        [InlineKeyboardButton(text="✍️ Открытый ответ",       callback_data="aq_type_open")],
        [InlineKeyboardButton(text="🖼 Фото + варианты",      callback_data="aq_type_photo")],
        [InlineKeyboardButton(text="🎵 Аудио + варианты",     callback_data="aq_type_audio")],
        [InlineKeyboardButton(text="🎬 Видео + варианты",     callback_data="aq_type_video")],
        [InlineKeyboardButton(text="🖼 Фото + открытый",      callback_data="aq_type_photo_open")],
        [InlineKeyboardButton(text="🎵 Аудио + открытый",     callback_data="aq_type_audio_open")],
        [InlineKeyboardButton(text="🎬 Видео + открытый",     callback_data="aq_type_video_open")],
    ])

    await callback.message.edit_text(
        f"Категория: *{category}*\n\nШаг 2. Выбери тип вопроса:",
        reply_markup=buttons,
        parse_mode="Markdown"
    )
    await state.set_state(AddQuestionForm.choose_type)
    await callback.answer()


@router.callback_query(AddQuestionForm.choose_type, F.data.startswith("aq_type_"))
async def aq_type_chosen(callback: CallbackQuery, state: FSMContext):
    q_type_raw = callback.data.replace("aq_type_", "")

    # Розбиваємо на базовий тип медіа і чи відкрита відповідь
    is_open = q_type_raw.endswith("_open")
    base    = q_type_raw.replace("_open", "")

    # Зіставляємо з константами БД
    type_map = {
        "text": Q_TEXT, "open": Q_OPEN,
        "photo": Q_PHOTO, "audio": Q_AUDIO, "video": Q_VIDEO
    }
    q_type = type_map.get(base, Q_TEXT)
    if is_open:
        q_type = base  # зберігаємо "photo_open", "audio_open" тощо

    await state.update_data(q_type=q_type, is_open=is_open, base_media=base)

    await callback.message.edit_text(
        f"Тип вопроса выбран.\n\n"
        "Шаг 3. Напиши *текст вопроса*:",
        parse_mode="Markdown"
    )
    await state.set_state(AddQuestionForm.enter_question)
    await callback.answer()


@router.message(AddQuestionForm.enter_question)
async def aq_question_entered(message: Message, state: FSMContext):
    await state.update_data(question=message.text.strip())
    data = await state.get_data()
    base_media = data.get("base_media", "text")

    if base_media in ("photo", "audio", "video"):
        type_labels = {"photo": "фото 🖼", "audio": "аудіофайл 🎵", "video": "відео 🎬"}
        await message.answer(
            f"Шаг 4. Отправь {type_labels[base_media]} для этого вопроса.\n\n"
            "Или напиши /skip чтобы пропустить (вопрос будет без медиа)."
        )
        await state.set_state(AddQuestionForm.enter_media)
    else:
        await ask_for_options_or_correct(message, state)


@router.message(AddQuestionForm.enter_media, Command("skip"))
@router.message(AddQuestionForm.enter_media, F.text == "/skip")
async def aq_media_skipped(message: Message, state: FSMContext):
    await state.update_data(media_id="", media_type="")
    await ask_for_options_or_correct(message, state)


@router.message(AddQuestionForm.enter_media, F.photo)
async def aq_media_photo(message: Message, state: FSMContext):
    await state.update_data(media_id=message.photo[-1].file_id, media_type="photo")
    await ask_for_options_or_correct(message, state)


@router.message(AddQuestionForm.enter_media, F.audio)
async def aq_media_audio(message: Message, state: FSMContext):
    await state.update_data(media_id=message.audio.file_id, media_type="audio")
    await ask_for_options_or_correct(message, state)


@router.message(AddQuestionForm.enter_media, F.video)
async def aq_media_video(message: Message, state: FSMContext):
    await state.update_data(media_id=message.video.file_id, media_type="video")
    await ask_for_options_or_correct(message, state)


@router.message(AddQuestionForm.enter_media, F.voice)
async def aq_media_voice(message: Message, state: FSMContext):
    await state.update_data(media_id=message.voice.file_id, media_type="voice")
    await ask_for_options_or_correct(message, state)


async def ask_for_options_or_correct(message: Message, state: FSMContext):
    data = await state.get_data()
    is_open = data.get("is_open", False)
    q_type  = data.get("q_type", Q_TEXT)

    if is_open or q_type == Q_OPEN:
        await message.answer(
            "✍️ Шаг 5. Напиши *правильный ответ*.\n\n"
            "Если ответов несколько — разделяй через `|`\n"
            "Пример: `Пушкин|А.С. Пушкин|Александр Пушкин`",
            parse_mode="Markdown"
        )
        await state.update_data(is_open=True)
        await state.set_state(AddQuestionForm.enter_correct)
    else:
        await message.answer(
            "📋 Шаг 5. Напиши *4 варианта ответа* — каждый с новой строки:\n\n"
            "Пример:\n"
            "Вариант А\n"
            "Вариант Б\n"
            "Вариант В\n"
            "Вариант Г",
            parse_mode="Markdown"
        )
        await state.set_state(AddQuestionForm.enter_options)


@router.message(AddQuestionForm.enter_options)
async def aq_options_entered(message: Message, state: FSMContext):
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]

    if len(lines) < 2:
        await message.answer("❌ Нужно минимум 2 варианта. Попробуй ещё раз:")
        return

    while len(lines) < 4:
        lines.append("")

    await state.update_data(
        option_a=lines[0], option_b=lines[1],
        option_c=lines[2], option_d=lines[3]
    )

    await message.answer(
        "✅ Шаг 6. Напиши *правильный ответ* — точно так, как написан в вариантах:\n\n"
        f"A: {lines[0]}\n"
        f"B: {lines[1]}\n"
        f"C: {lines[2] or '—'}\n"
        f"D: {lines[3] or '—'}",
        parse_mode="Markdown"
    )
    await state.set_state(AddQuestionForm.enter_correct)


@router.message(AddQuestionForm.enter_correct)
async def aq_correct_entered(message: Message, state: FSMContext):
    correct = message.text.strip()
    await state.update_data(correct=correct)
    data = await state.get_data()

    # Зберігаємо питання в БД
    await add_question(
        category   = data["category"],
        q_type     = data["q_type"],
        question   = data["question"],
        correct    = correct,
        option_a   = data.get("option_a", ""),
        option_b   = data.get("option_b", ""),
        option_c   = data.get("option_c", ""),
        option_d   = data.get("option_d", ""),
        media_id   = data.get("media_id", ""),
        media_type = data.get("media_type", ""),
    )
    await state.clear()

    await message.answer(
        f"✅ Вопрос добавлен в категорию *{data['category']}*!",
        parse_mode="Markdown"
    )


# ─── СПИСОК ПИТАНЬ ────────────────────────────────────────────────────────────

@router.message(Command("list_questions"))
async def cmd_list_questions(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    buttons = [
        [InlineKeyboardButton(text=cat, callback_data=f"lq_cat_{cat}")]
        for cat in CATEGORIES
    ]
    await message.answer(
        "📋 Выбери категорию для просмотра вопросов:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("lq_cat_"))
async def lq_show_category(callback: CallbackQuery):
    category = callback.data.replace("lq_cat_", "")
    questions = await list_questions(category)

    if not questions:
        await callback.message.edit_text(
            f"📭 В категории «{category}» вопросов нет.\n"
            "Добавь первый через /add_question"
        )
        await callback.answer()
        return

    text = f"📋 *{category}* — {len(questions)} вопросов:\n\n"
    for q_id, q_type, question, correct in questions:
        short = question[:50] + "..." if len(question) > 50 else question
        text += f"ID `{q_id}` [{q_type}]: {short}\n"
        text += f"   ✅ {correct[:30]}\n\n"

    text += "Чтобы удалить: `/del_question ID`"
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()


# ─── ВИДАЛЕННЯ ПИТАННЯ ───────────────────────────────────────────────────────

@router.message(Command("del_question"))
async def cmd_del_question(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    args = message.text.replace("/del_question", "").strip()

    if not args or not args.isdigit():
        await message.answer(
            "📝 Формат: `/del_question ID`\n"
            "ID узнать через /list_questions",
            parse_mode="Markdown"
        )
        return

    deleted = await delete_question(int(args))
    if deleted:
        await message.answer(f"✅ Вопрос ID {args} удалён.")
    else:
        await message.answer(f"❌ Вопрос ID {args} не найден.")


# ─── СТАТИСТИКА ПИТАНЬ ────────────────────────────────────────────────────────

@router.message(Command("quiz_stats"))
async def cmd_quiz_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    text = "📊 *Статистика вопросов:*\n\n"
    for cat in CATEGORIES:
        count = await count_questions(cat)
        text += f"• {cat}: {count} вопросов\n"

    await message.answer(text, parse_mode="Markdown")
