# handlers/faq.py — FAQ с иерархией категорий

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

router = Router()

FAQ_DATA = {

    "participation": {
        "question": "🎮 Участие в игре",
        "sub": {
            "teams_count": {
                "question": "Сколько команд участвует?",
                "answer": (
                    "👥 Количество команд-участников:\n\n"
                    "Зависит от места проведения и количества участников.\n\n"
                    "• Минимум для проведения игры — 4 команды\n"
                    "• Максимум — до 10 команд\n"
                    "• Общее количество участников — до 150 человек\n\n"
                    "В каждом анонсе указывается количество доступных мест!"
                )
            },
            "team_size": {
                "question": "Сколько человек в команде?",
                "answer": (
                    "👥 Состав команды:\n\n"
                    "• Минимум — 3 человека\n"
                    "• Максимум — 6 человек\n\n"
                    "Оптимальный состав — 4–5 игроков.\n"
                    "Играть можно и вдвоём, но это сложнее 😊"
                )
            },
            "no_team": {
                "question": "Нет команды — можно ли участвовать?",
                "answer": (
                    "🙋 Нет команды — не проблема!\n\n"
                    "Есть несколько вариантов:\n\n"
                    "1. Напиши администратору — мы поможем найти команду\n"
                    "2. Приходи один — объединим с другими одиночными игроками\n"
                    "3. Собери друзей прямо перед игрой\n\n"
                    "Контакт администратора: @organizer_username"
                )
            },
        }
    },

    "registration": {
        "question": "📝 Регистрация",
        "sub": {
            "how_to_register": {
                "question": "Как пройти регистрацию?",
                "answer": (
                    "📝 Способы регистрации:\n\n"
                    "По телефону или в личные сообщения:\n"
                    "Да, можно! Свяжись с администратором:\n\n"
                    "📞 Телефон: +38 (050) 000-00-00\n"
                    "✉️ Telegram: @organizer_username\n\n"
                    "При регистрации сообщи:\n"
                    "• Название команды\n"
                    "• Количество игроков\n"
                    "• Контактные данные капитана"
                )
            },
            "registration_deadline": {
                "question": "До какого времени открыта регистрация?",
                "answer": (
                    "⏰ Дедлайн регистрации:\n\n"
                    "Регистрация закрывается за 24 часа до начала игры.\n\n"
                    "Рекомендуем регистрироваться заранее — "
                    "места ограничены и заканчиваются быстро!\n\n"
                    "Если регистрация закрыта — напиши администратору: @organizer_username"
                )
            },
            "cancel_registration": {
                "question": "Как отменить регистрацию?",
                "answer": (
                    "❌ Отмена регистрации:\n\n"
                    "Напиши администратору не позднее чем за 12 часов до игры:\n\n"
                    "✉️ Telegram: @organizer_username\n\n"
                    "Сообщи название своей команды и игру, на которую зарегистрирован."
                )
            },
        }
    },

    "rules": {
        "question": "📋 Правила и формат",
        "sub": {
            "game_format": {
                "question": "Как проходит игра?",
                "answer": (
                    "🎮 Формат игры:\n\n"
                    "• Игра состоит из 6–8 раундов\n"
                    "• В каждом раунде 5–7 вопросов\n"
                    "• Время на обсуждение — 60 секунд\n"
                    "• Ответ подаётся письменно на бланке\n"
                    "• Между раундами — небольшие перерывы\n\n"
                    "Общая продолжительность игры — 2.5–3 часа"
                )
            },
            "phones": {
                "question": "Можно ли пользоваться телефоном?",
                "answer": (
                    "📵 Использование телефонов:\n\n"
                    "Нет! Телефоны и интернет во время игры запрещены.\n\n"
                    "Это честная игра на эрудицию и командную работу.\n"
                    "Нарушителей могут дисквалифицировать 🚫"
                )
            },
            "scoring": {
                "question": "Как начисляются очки?",
                "answer": (
                    "⭐ Система подсчёта очков:\n\n"
                    "• За каждый правильный ответ — 1 балл\n"
                    "• В некоторых раундах есть удвоение ставки\n"
                    "• Итоговый счёт — сумма баллов за все раунды\n\n"
                    "Победитель определяется по наибольшей сумме баллов.\n"
                    "При ничьей — проводится дополнительный вопрос."
                )
            },
        }
    },

    "payment": {
        "question": "💰 Оплата",
        "sub": {
            "price": {
                "question": "Сколько стоит участие?",
                "answer": (
                    "💰 Стоимость участия:\n\n"
                    "Цена указывается в каждом анонсе отдельно.\n\n"
                    "Оплата — за команду, не за каждого игрока.\n\n"
                    "Для уточнения стоимости: @organizer_username"
                )
            },
            "payment_method": {
                "question": "Как и когда платить?",
                "answer": (
                    "💳 Способы оплаты:\n\n"
                    "• Наличными на месте перед началом игры\n"
                    "• Переводом на карту (реквизиты у администратора)\n\n"
                    "Оплатить нужно до начала игры.\n"
                    "Без оплаты команда не допускается к участию."
                )
            },
            "refund": {
                "question": "Можно ли вернуть деньги если не пришёл?",
                "answer": (
                    "💸 Возврат средств:\n\n"
                    "Возврат возможен если ты предупредил за 24 часа до игры.\n\n"
                    "Если предупредил менее чем за 24 часа — "
                    "оплата не возвращается, но можно передать место другой команде.\n\n"
                    "По вопросам возврата: @organizer_username"
                )
            },
        }
    },

    "location": {
        "question": "📍 Место и время",
        "sub": {
            "where": {
                "question": "Где проходят игры?",
                "answer": (
                    "📍 Место проведения:\n\n"
                    "Место указывается в каждом анонсе.\n\n"
                    "Обычно это:\n"
                    "• Бары и кафе города\n"
                    "• Культурные пространства\n"
                    "• Антикафе\n\n"
                    "Проверяй раздел Предстоящие игры для актуальных адресов."
                )
            },
            "when": {
                "question": "Как часто проходят игры?",
                "answer": (
                    "📅 Расписание игр:\n\n"
                    "Игры проходят 1–2 раза в месяц.\n\n"
                    "Следи за анонсами в:\n"
                    "• Этом боте в разделе Предстоящие игры\n"
                    "• Нашем Telegram-канале: @quiz_channel\n\n"
                    "Включи уведомления, чтобы не пропустить!"
                )
            },
        }
    },

}


# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ────────────

def categories_keyboard():
    buttons = []
    for key, data in FAQ_DATA.items():
        buttons.append([InlineKeyboardButton(
            text=data["question"],
            callback_data=f"faq_cat_{key}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subcategory_keyboard(category_key: str):
    sub = FAQ_DATA.get(category_key, {}).get("sub", {})
    buttons = []
    for key, data in sub.items():
        buttons.append([InlineKeyboardButton(
            text=data["question"],
            callback_data=f"faq_sub_{category_key}|{key}"
        )])
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад к категориям",
        callback_data="faq_back"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_sub_keyboard(category_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="◀️ Назад к вопросам",
            callback_data=f"faq_cat_{category_key}"
        )
    ]])


# ─── ОБРАБОТЧИКИ ────────────────────────

@router.message(F.text == "❓ FAQ")
async def show_faq(message: Message):
    await message.answer(
        "❓ Частые вопросы\n\nВыбери категорию 👇",
        reply_markup=categories_keyboard()
    )


@router.callback_query(F.data.startswith("faq_cat_"))
async def show_subcategory(callback: CallbackQuery):
    category_key = callback.data.replace("faq_cat_", "")
    category = FAQ_DATA.get(category_key)
    if not category:
        await callback.answer("Категория не найдена.")
        return

    await callback.message.edit_text(
        f"{category['question']}\n\nВыбери вопрос 👇",
        reply_markup=subcategory_keyboard(category_key)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faq_sub_"))
async def show_answer(callback: CallbackQuery):
    parts = callback.data.replace("faq_sub_", "").split("|", 1)
    if len(parts) < 2:
        await callback.answer("Ошибка.")
        return

    category_key, sub_key = parts
    sub = FAQ_DATA.get(category_key, {}).get("sub", {}).get(sub_key)
    if not sub:
        await callback.answer("Вопрос не найден.")
        return

    await callback.message.edit_text(
        sub["answer"],
        reply_markup=back_to_sub_keyboard(category_key)
    )
    await callback.answer()


@router.callback_query(F.data == "faq_back")
async def back_to_categories(callback: CallbackQuery):
    await callback.message.edit_text(
        "❓ Частые вопросы\n\nВыбери категорию 👇",
        reply_markup=categories_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faq_"))
async def faq_fallback(callback: CallbackQuery):
    await callback.message.edit_text(
        "❓ Частые вопросы\n\nВыбери категорию 👇",
        reply_markup=categories_keyboard()
    )
    await callback.answer("Меню обновлено, выбери категорию")
