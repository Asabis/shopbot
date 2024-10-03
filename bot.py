# bot.py

import logging
import sqlite3
import telebot
from telebot import types, custom_filters
import uuid
from config import API_TOKEN, DB_NAME

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы для кнопок и команд
SHOPPING_LIST = "🛍️ Список покупок"
CLEAR_LIST = "🗑️ Очистить список"
SHARE_LIST = "🔗 Поделиться списком"
JOIN_LIST = "👥 Присоединиться к списку"
VIEW_SHARED_USERS = "👤 Участники списка"
ABOUT_APP = "ℹ️ О приложении"

COMMANDS = [
    SHOPPING_LIST,
    CLEAR_LIST,
    SHARE_LIST,
    JOIN_LIST,
    VIEW_SHARED_USERS,
    ABOUT_APP,
]

# Инициализация бота
bot = telebot.TeleBot(API_TOKEN)
bot.add_custom_filter(custom_filters.StateFilter(bot))


# Определение состояний пользователя
class States:
    ADD_ITEM = "add_item"


# Функция для выполнения запросов к базе данных
def execute_query(query, params=(), fetch=False, fetchone=False, lastrowid=False):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            cursor.execute(query, params)
            if lastrowid:
                return cursor.lastrowid
            elif fetchone:
                return cursor.fetchone()
            elif fetch:
                return cursor.fetchall()
            return None
    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных: {e}")
        raise


# Создание необходимых таблиц в базе данных
def create_tables():
    execute_query(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
    """
    )
    execute_query(
        """
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            share_code TEXT UNIQUE
        )
    """
    )
    execute_query(
        """
        CREATE TABLE IF NOT EXISTS user_groups (
            user_id INTEGER,
            group_id INTEGER,
            PRIMARY KEY (user_id, group_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (group_id) REFERENCES groups(group_id)
        )
    """
    )
    execute_query(
        """
        CREATE TABLE IF NOT EXISTS lists (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            item TEXT,
            FOREIGN KEY (group_id) REFERENCES groups(group_id)
        )
    """
    )


# Экранирование специальных символов Markdown
def escape_markdown(text):
    escape_chars = "_*[]()~`>#+-=|{}.!\\"
    return "".join(["\\" + char if char in escape_chars else char for char in text])


# Главное меню клавиатуры
def main_menu(has_items=True):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(SHOPPING_LIST)
    if has_items:
        markup.add(CLEAR_LIST)
    markup.add(SHARE_LIST)
    markup.add(JOIN_LIST)
    markup.add(VIEW_SHARED_USERS)
    markup.add(ABOUT_APP)
    return markup


# Функция для отправки сообщений с Markdown и главным меню
def send_markdown_message(chat_id, text, reply_markup=None):
    bot.send_message(
        chat_id,
        text,
        reply_markup=reply_markup or main_menu(),
        parse_mode="Markdown",
    )


# Функция для отправки действия "печатает"
def send_typing_action(chat_id):
    bot.send_chat_action(chat_id, "typing")


# Обработчик команды /start
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""

    # Сохраняем пользователя в базе данных
    execute_query(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user_id, username, first_name),
    )

    send_welcome_message(message)


# Отправка приветственного сообщения и главного меню
WELCOME_MESSAGE = (
    "👋 *Привет, {first_name}!* Добро пожаловать в *ShopBuddy* 🛍️\n\n"
    "Я помогу вам управлять вашими списками покупок легко и удобно!\n\n"
    "📌 *Что я умею?*\n"
    "• 📝 Добавлять товары в список\n"
    "• 📋 Показывать ваш список покупок\n"
    "• ❌ Удалять товары из списка\n"
    "• 🤝 Объединять списки с друзьями\n\n"
    "Чтобы начать, просто отправьте мне название товара или выберите действие из меню ниже👇"
)


def send_welcome_message(message):
    text = WELCOME_MESSAGE.format(
        first_name=escape_markdown(message.from_user.first_name or "друг")
    )
    send_markdown_message(
        message.chat.id,
        text,
    )


# Получение или создание группы для пользователя
def get_or_create_group(user_id):
    """Возвращает ID группы для данного пользователя, создавая новую, если необходимо."""
    group = execute_query(
        "SELECT group_id FROM user_groups WHERE user_id = ?", (user_id,), fetchone=True
    )
    if group:
        return group[0]
    else:
        # Создаем новую группу
        new_group_id = execute_query(
            "INSERT INTO groups (group_name) VALUES (?)",
            (f"Group_{user_id}",),
            lastrowid=True,
        )
        execute_query(
            "INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)",
            (user_id, new_group_id),
        )
        return new_group_id


# Уведомление участников группы о изменениях
def notify_group_users(group_id, message_text, actor_id, exclude_actor=True):
    """Уведомляет пользователей в группе об изменениях."""
    users = execute_query(
        "SELECT user_id FROM user_groups WHERE group_id = ?", (group_id,), fetch=True
    )

    for user in users:
        user_id = user[0]
        if exclude_actor and user_id == actor_id:
            continue
        try:
            send_markdown_message(user_id, message_text)
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 403:
                logger.error(
                    f"Не могу отправить сообщение пользователю {user_id}: {e.description}"
                )
            else:
                logger.error(
                    f"Ошибка отправки сообщения пользователю {user_id}: {e.description}"
                )


# Обработка объединения списков (создание кода для обмена)
@bot.message_handler(func=lambda message: message.text == SHARE_LIST)
def share_list(message):
    """Предлагает пользователю поделиться списком с другим пользователем."""
    share_code = generate_share_code(message.from_user.id)
    send_markdown_message(
        message.chat.id,
        f"🔗 *Ваш код для совместного списка*: `{share_code}`\n\n"
        "Отправьте этот код другу, чтобы он мог присоединиться к вашему списку.\n\n"
        'Когда ваш друг будет готов, пусть нажмет кнопку *"Присоединиться к списку"* и введет код.',
    )


# Генерация кода для объединения списков
def generate_share_code(user_id):
    group_id = get_or_create_group(user_id)
    share_code = str(uuid.uuid4())[:8]
    execute_query(
        "UPDATE groups SET share_code = ? WHERE group_id = ?", (share_code, group_id)
    )
    return share_code


# Обработка присоединения к списку
@bot.message_handler(func=lambda message: message.text == JOIN_LIST)
def join_list(message):
    """Обрабатывает присоединение к существующему списку по коду."""
    send_markdown_message(
        message.chat.id,
        "🔑 *Введите код для присоединения к списку:*",
        reply_markup=types.ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(message, process_join_code)


def process_join_code(message):
    share_code = message.text.strip()
    group = execute_query(
        "SELECT group_id FROM groups WHERE share_code = ?", (share_code,), fetchone=True
    )
    if group:
        group_id = group[0]
        user_id = message.from_user.id
        # Проверяем, не состоит ли пользователь уже в этой группе
        existing = execute_query(
            "SELECT 1 FROM user_groups WHERE user_id = ? AND group_id = ?",
            (user_id, group_id),
            fetchone=True,
        )
        if not existing:
            # Удаляем пользователя из его текущей группы
            execute_query("DELETE FROM user_groups WHERE user_id = ?", (user_id,))
            # Добавляем в новую группу
            execute_query(
                "INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)",
                (user_id, group_id),
            )
            send_markdown_message(
                message.chat.id,
                "🎉 *Вы успешно присоединились к списку!*",
            )
            # Уведомляем других участников группы
            notify_group_users(
                group_id,
                f"👥 *{escape_markdown(message.from_user.first_name)}* присоединился к вашему списку!",
                user_id,
            )
        else:
            send_markdown_message(
                message.chat.id,
                "ℹ️ *Вы уже состоите в этом списке.*",
            )
    else:
        send_markdown_message(
            message.chat.id,
            "❌ *Неверный код. Пожалуйста, проверьте код и попробуйте снова.*",
        )


# Обработка добавления элементов по тексту
@bot.message_handler(func=lambda message: message.text not in COMMANDS)
def ask_to_add(message):
    """Спрашивает пользователя, хочет ли он добавить товар в список."""
    item = message.text.strip()
    if item:
        user_id = message.from_user.id
        # Сохраняем состояние пользователя и передаем данные через аргументы
        bot.set_state(user_id, States.ADD_ITEM, message.chat.id)
        with bot.retrieve_data(user_id, message.chat.id) as data:
            data["item"] = item
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="✅ Да", callback_data=f"add_yes"))
        markup.add(types.InlineKeyboardButton(text="❌ Нет", callback_data="cancel"))
        send_markdown_message(
            message.chat.id,
            f'🛍️ *Добавить товар* "{escape_markdown(item)}" *в ваш список покупок?*',
            reply_markup=markup,
        )
    else:
        send_markdown_message(
            message.chat.id,
            "⚠️ *Пожалуйста, введите название продукта.*",
        )


# Обработка подтверждения добавления элемента
@bot.callback_query_handler(func=lambda call: call.data in ["add_yes", "cancel"])
def handle_add_item(call):
    """Обрабатывает подтверждение добавления элемента."""
    user_id = call.from_user.id
    if call.data == "cancel":
        bot.delete_state(user_id, call.message.chat.id)
        handle_cancel_action(call)
        return

    with bot.retrieve_data(user_id, call.message.chat.id) as data:
        item = data.get("item")
    if not item:
        bot.answer_callback_query(call.id, "❌ Не удалось добавить продукт.")
        return

    group_id = get_or_create_group(user_id)

    send_typing_action(call.message.chat.id)

    # Добавляем элемент в список группы
    execute_query(
        "INSERT OR IGNORE INTO lists (group_id, item) VALUES (?, ?)", (group_id, item)
    )

    # Уведомляем участников группы
    notify_group_users(
        group_id,
        f'🛒 *{escape_markdown(call.from_user.first_name)}* добавил товар "*{escape_markdown(item)}*" в список покупок!',
        user_id,
    )

    bot.answer_callback_query(call.id, f'✅ "{item}" добавлен в список.')
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f'✅ Товар *"{escape_markdown(item)}"* успешно добавлен в ваш список покупок!',
        parse_mode="Markdown",
    )

    # Отображаем обновленный список покупок
    show_list(call.message, user_id)


# Обработка удаления элемента из списка
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_item(call):
    """Удаляет элемент из списка группы."""
    item_id = call.data.split("_", 1)[1]
    user_id = call.from_user.id
    group_id = get_or_create_group(user_id)

    # Получаем название элемента перед удалением
    item = execute_query(
        "SELECT item FROM lists WHERE item_id = ? AND group_id = ?",
        (item_id, group_id),
        fetchone=True,
    )
    if not item:
        bot.answer_callback_query(call.id, "❌ Элемент не найден.")
        return
    item = item[0]

    send_typing_action(call.message.chat.id)

    # Удаляем элемент из списка группы
    execute_query(
        "DELETE FROM lists WHERE item_id = ? AND group_id = ?", (item_id, group_id)
    )

    # Уведомляем участников группы
    notify_group_users(
        group_id,
        f'🗑️ *{escape_markdown(call.from_user.first_name)}* удалил товар "*{escape_markdown(item)}*" из списка покупок.',
        user_id,
    )

    bot.answer_callback_query(call.id, "🗑️ Элемент удален.")
    send_markdown_message(
        call.message.chat.id,
        f'🗑️ Товар *"{escape_markdown(item)}"* был удален из вашего списка покупок.',
    )

    # Отображаем обновленный список покупок
    show_list(call.message, user_id)


# Отображение списка покупок
@bot.message_handler(func=lambda message: message.text == SHOPPING_LIST)
def show_list(message, user_id=None):
    if user_id is None:
        user_id = message.from_user.id
    group_id = get_or_create_group(user_id)

    # Получаем элементы списка группы
    items = execute_query(
        """SELECT item_id, item FROM lists WHERE group_id = ?""",
        (group_id,),
        fetch=True,
    )

    if items:
        item_list = ""
        markup = types.InlineKeyboardMarkup()
        for idx, (item_id, item) in enumerate(items, 1):
            item_text = f"• {escape_markdown(item)}"
            item_list += item_text + "\n"
            # Добавляем кнопку удаления для каждого элемента
            button = types.InlineKeyboardButton(
                text=f"❌ {item}", callback_data=f"delete_{item_id}"
            )
            markup.add(button)

        send_markdown_message(
            message.chat.id,
            f"🛒 *Ваш список покупок* ({len(items)} товаров):\n"
            "--------------------------------------\n"
            f"{item_list}"
            "--------------------------------------",
            reply_markup=markup,
        )
    else:
        send_markdown_message(
            message.chat.id,
            "🛒 *Ваш список покупок пуст.*\n\nДобавьте товары, отправив их названия сообщением.",
        )

    # Отображаем главное меню
    send_markdown_message(
        message.chat.id,
        "🔖 *Выберите действие из меню ниже или добавьте новый товар:*",
        reply_markup=main_menu(has_items=bool(items)),
    )


# Подтверждение очистки списка
@bot.message_handler(func=lambda message: message.text == CLEAR_LIST)
def confirm_clear_list(message):
    """Запрашивает подтверждение перед очисткой списка."""
    buttons = [
        ("✅ Да, очистить", "confirm_clear"),
        ("❌ Отмена", "cancel"),
    ]
    prompt_user(
        message.chat.id,
        "🗑️ *Вы уверены, что хотите полностью очистить ваш список покупок?*",
        buttons,
    )


@bot.callback_query_handler(func=lambda call: call.data == "confirm_clear")
def clear_list(call):
    """Очищает список группы после подтверждения."""
    user_id = call.from_user.id
    group_id = get_or_create_group(user_id)

    send_typing_action(call.message.chat.id)

    # Очищаем список группы
    execute_query("DELETE FROM lists WHERE group_id = ?", (group_id,))
    bot.answer_callback_query(call.id, "🗑️ Список очищен.")
    send_markdown_message(
        call.message.chat.id,
        "🗑️ *Ваш список покупок был успешно очищен!*",
        reply_markup=main_menu(has_items=False),
    )

    # Уведомляем участников группы
    notify_group_users(
        group_id,
        f"🗑️ *{escape_markdown(call.from_user.first_name)}* очистил список покупок!",
        user_id,
    )


# Универсальный обработчик отмены действия
def handle_cancel_action(call):
    bot.answer_callback_query(call.id, "🔙 Действие отменено.")
    send_markdown_message(
        call.message.chat.id,
        "🔙 *Действие отменено.*",
    )


# Регистрируем обработчик для всех случаев, когда data == "cancel"
@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_action(call):
    handle_cancel_action(call)


# Информация о приложении
@bot.message_handler(func=lambda message: message.text == ABOUT_APP)
def about_app(message):
    """Предоставляет информацию о приложении."""
    send_markdown_message(
        message.chat.id,
        "ℹ️ *О приложении*\n\n"
        "🤖 *ShopBuddy* - ваш надежный помощник в управлении списками покупок!\n\n"
        "С помощью меня вы можете:\n"
        "• 📝 Легко добавлять товары в список.\n"
        "• ❌ Удалять товары одним нажатием.\n"
        "• 🤝 Делиться списком с близкими и друзьями.\n"
        "• 👤 Просматривать участников списка.\n\n"
        "Просто начните вводить названия товаров, и я помогу вам их сохранить!",
    )


# Показ участников списка
@bot.message_handler(func=lambda message: message.text == VIEW_SHARED_USERS)
def show_shared_users(message):
    """Показывает список пользователей, с которыми вы поделились списком."""
    user_id = message.from_user.id
    group_id = get_or_create_group(user_id)

    # Получаем список пользователей в группе
    users = execute_query(
        """
        SELECT u.first_name, u.username FROM user_groups ug
        JOIN users u ON ug.user_id = u.user_id
        WHERE ug.group_id = ?
    """,
        (group_id,),
        fetch=True,
    )

    if users:
        user_list = "\n".join(
            [
                f"• {escape_markdown(first_name)}{' (@' + escape_markdown(username) + ')' if username else ''}"
                for first_name, username in users
            ]
        )
        send_markdown_message(
            message.chat.id,
            f"👥 *Участники вашего списка покупок*:\n\n{user_list}",
        )
    else:
        send_markdown_message(
            message.chat.id,
            "ℹ️ *Вы пока не поделились списком ни с кем.*",
        )


# Функция для отправки сообщения с кнопками
def prompt_user(chat_id, text, buttons, state=None):
    markup = types.InlineKeyboardMarkup()
    for button_text, callback_data in buttons:
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    send_markdown_message(chat_id, text, reply_markup=markup)
    if state:
        bot.set_state(chat_id, state)


if __name__ == "__main__":
    create_tables()
    # Бот будет запущен из main.py
