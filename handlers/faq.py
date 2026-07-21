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
                    "👥 Количество команд:\n\n"
                    "Зависит от места проведения и количества участников.\n\n"
                    "• Минимум для проведения игры — 4 команды\n"
                    "• Максимум ограничивается вместимостью бара/кафе (обычно до 25 команд)"
                )
            },
            "team_size": {
                "question": "Сколько человек в команде?",
                "answer": (
                    "👥 Состав команды:\n\n"
                    "• Минимум — 2 человека\n"
                    "• Максимум — 10 человек\n\n"
                    "Оптимальный комфортный состав — 5-7 игроков, но все индивидуально. Кому-то удобно играть вдвоем, а кто-то предпочитает шумные компании по 10 человек 🙃\n\n"
                    "Дети до 12 лет не считаются участниками и не оплачивают игру.\n\n"
                    "Вы можете собрать команду более 10 человек. В таком случае, вы будете играть вне зачета - ваш результат будет отображаться внизу таблицы с пометкой «н/з» и не сможете претендовать на подарки за призовые места."
                )
            },
            "no_team": {
                "question": "Нет команды — можно ли участвовать?",
                "answer": (
                    "🙋 Нет команды — не проблема!\n\n"
                    "Приходи на игру (можно без регистрации) — мы поможем объединиться на месте с другими одиночными игроками или примкнуть к уже существующей команде."
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
                    'Способ регистрации существует только один - на сайте <a href="https://rudagames.com">Ruda Games</a> 💜\n\n'
                    "ТУТ ТЕКСТ\n\n"
                    'Возникли проблемы при регистрации? Напиши нашему <a href="https://t.me/kotlettttka">Администратору</a> '
                    'или в поддержку на сайте <a href="https://rudagames.com">Ruda Games</a>'
                )
            },
            "registration_deadline": {
                "question": "До какого времени открыта регистрация?",
                "answer": (
                    "⏰ Дедлайн регистрации:\n\n"
                    "Как такового ограничения по времени регистрации нет, при наличии мест можно регистрироваться вплоть до начала игры.\n\n"
                    "Но все же, мы рекомендуем регистрироваться заранее. Во-первых, места ограничены и иногда заканчиваются очень быстро, во-вторых, чем раньше вы зарегистрируетесь, тем больше шансов получить лучшие места в зале.\n\n"
                    "В комментариях к регистрации вы можете указать, где именно хотели бы сидеть. Мы стараемся учитывать все ваши пожелания, но, к сожалению, не можем гарантировать, что в 100% случаев вы сядете там, где и планировали. Это связано с особенностями залов, количеством игроков, а также с вашим местом в таблице регистрации. Чем раньше, тем выше шанс!\n\n"
                    'Остались вопросы по регистрации? Напиши нашему <a href="https://t.me/@kotlettttka">Администратору</a> \n\n'
                    "Регистрация закрывается за 24 часа до начала игры."
                ),
                "extra_button": {
                    "text": "🔔 Подписаться на рассылку",
                    "callback_data": "open_subscription_menu"
                }
            },
            "cancel_registration": {
                "question": "Как отменить регистрацию?",
                "answer": (
                    "❌ Отмена регистрации:\n\n"
                    'Если у вас возникли непредвиденные обстоятельства, отменить регистрацию можно в личном кабинете на сайте <a href="https://rudagames.com">Ruda Games</a> 😔\n\n'
                    "Мы очень просим вас не пренебрегать этой функцией, если вы точно знаете, что не придете на игру. \n"
                    "Это даст шанс сыграть командам из резерва, а также облегчит работу администраторов на площадке 🙏"
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
                    "Цена указывается в каждом анонсе отдельно и зависит от города проведения, а также формата игры.\n\n"
                    "Цена указана за 1 человека."
                )
            },
            "payment_method": {
                "question": "Как и когда платить?",
                "answer": (
                    "💳 Способы оплаты:\n\n"
                    "• Наличными\n"
                    "• По QR-коду \n\n"
                    "Оплата производится на игре, после 3-го тура.\n"
                    "Мы будем очень благодарны, если вы внесете сумму за всю команду, это уменьшит очередь на оплату в перерыве ☺️"
                )
            },
            "refund": {
                "question": "Можно ли вернуть деньги если не пришёл?",
                "answer": (
                    "💸 Возврат средств:\n\n"
                    "Мы не берем предоплату! Оплачивайте игру на месте и только за тех, кто пришел.\n\n"
                    "Возврат средств после игры не предусмотрен."
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
                    "Проверяй раздел «Предстоящие игры» и подписывайся на рассылку о предстоящих играх в твоем городе! 👇"
                ),
                "extra_button": {
                    "text": "🔔 Подписка на игры",
                    "callback_data": "open_subscription_menu"
                }
            },
            "when": {
                "question": "Как часто проходят игры?",
                "answer": (
                    "📅 Расписание игр:\n\n"
                    "Игры проходят 1–2 раза в неделю, в зависимости от города.\n\n"
                    "Следи за анонсами в:\n"
                    "• Этом боте в разделе «Предстоящие игры»\n"
                    "• Наших Telegram-каналах: \n"
                    '<a href="https://t.me/rudagamespriglosmsc">Москва</a> \n'
                    '<a href="https://t.me/rudagameskrgk">Красногорск</a> \n'
                    '<a href="https://t.me/rudagamesobninsk">Обнинск</a> \n\n'
                    "• Подписывайся на рассылку 👇"
                ),
                "extra_button": {
                    "text": "🔔 Подписка на игры",
                    "callback_data": "open_subscription_menu"
                }
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


def back_to_sub_keyboard(category_key: str, extra_button: dict | None = None):
    buttons = []
    if extra_button:
        buttons.append([InlineKeyboardButton(
            text=extra_button["text"],
            callback_data=extra_button["callback_data"]
        )])
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад к вопросам",
        callback_data=f"faq_cat_{category_key}"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── ОБРАБОТЧИКИ ────────────────────────

@router.message(F.text == "❓ FAQ")
async def show_faq(message: Message):
    await message.answer(
        "❓ Частые вопросы\n\nВыбери категорию 👇",
        reply_markup=categories_keyboard(),
        parse_mode="HTML"
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
        reply_markup=subcategory_keyboard(category_key),
        parse_mode="HTML"
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
        reply_markup=back_to_sub_keyboard(category_key, sub.get("extra_button")),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "faq_back")
async def back_to_categories(callback: CallbackQuery):
    await callback.message.edit_text(
        "❓ Частые вопросы\n\nВыбери категорию 👇",
        reply_markup=categories_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faq_"))
async def faq_fallback(callback: CallbackQuery):
    await callback.message.edit_text(
        "❓ Частые вопросы\n\nВыбери категорию 👇",
        reply_markup=categories_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("Меню обновлено, выбери категорию")