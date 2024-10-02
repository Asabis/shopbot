import logging
import sqlite3
import sys
import telebot
from telebot import types
import uuid
from config import API_TOKEN, DB_NAME

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Константы для кнопок и команд
SHOPPING_LIST = "🛍️ Список покупок"
CLEAR_LIST = "🗑️ Очистить список"
SHARE_LIST = "🔗 Объединить списки"
ABOUT_APP = "ℹ️ Информация о приложении"
MY_ID = "👤 Мой ID"

# Инициализация бота
bot = telebot.TeleBot(API_TOKEN)

# Хранение временных данных на уровне пользователя
user_temp_items = {}

# Функция для выполнения запросов к базе данных
def execute_query(query, params=(), fetch=False, fetchone=False, lastrowid=False):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            cursor = conn.cursor()
            cursor.execute(query, params)
            if lastrowid:
                return cursor.lastrowid
            elif fetchone:
                return cursor.fetchone()
            elif fetch:
                return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных: {e}")
        raise

# Создание необходимых таблиц в базе данных
def create_tables():
    execute_query('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
    ''')
    execute_query('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            share_code TEXT UNIQUE
        )
    ''')
    execute_query('''
        CREATE TABLE IF NOT EXISTS user_groups (
            user_id INTEGER,
            group_id INTEGER,
            PRIMARY KEY (user_id, group_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (group_id) REFERENCES groups(group_id)
        )
    ''')
    execute_query('''
        CREATE TABLE IF NOT EXISTS lists (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            item TEXT,
            FOREIGN KEY (group_id) REFERENCES groups(group_id)
        )
    ''')

# Экранирование специальных символов Markdown
def escape_markdown(text):
    escape_chars = '_*[]()~`>#+-=|{}!'
    return ''.join(['\\' + char if char in escape_chars else char for char in text])


# Главное меню клавиатуры
def main_menu(has_items=True):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(SHOPPING_LIST)
    if has_items:
        markup.add(CLEAR_LIST)
    markup.add(SHARE_LIST)
    markup.add(MY_ID, ABOUT_APP)
    return markup

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or ''
    first_name = message.from_user.first_name or ''

    # Сохраняем пользователя в базе данных
    execute_query("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                  (user_id, username, first_name))

    # Получаем или создаем группу для пользователя
    group_id = get_or_create_group(user_id)

    send_main_menu(message)

# Отправка главного меню
def send_main_menu(message):
    """Отправляет главное меню пользователю."""
    description = (
        "✨ *Привет!* Я ваш помощник для управления списком покупок!\n\n"
        "Вы можете:\n"
        "➕ *Добавлять продукты* в список.\n"
        "📋 *Просматривать текущий список*.\n"
        "🗑️ *Удалять ненужные элементы*.\n"
        "🔗 *Объединять списки* с друзьями.\n"
        "👤 *Узнать свой ID*.\n\n"
        "Нажмите на кнопку ниже, чтобы начать:"
    )
    bot.send_message(message.chat.id, description, reply_markup=main_menu(), parse_mode="Markdown")

# Получение или создание группы для пользователя
def get_or_create_group(user_id):
    """Возвращает ID группы для данного пользователя, создавая новую, если необходимо."""
    group = execute_query(
        "SELECT group_id FROM user_groups WHERE user_id = ?",
        (user_id,),
        fetchone=True
    )
    if group:
        return group[0]
    else:
        # Создаем новую группу
        new_group_id = execute_query("INSERT INTO groups (group_name) VALUES (?)",
                                     (f"Group_{user_id}",), lastrowid=True)
        execute_query("INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)", (user_id, new_group_id))
        return new_group_id

# Отправка действия "печатает"
def send_typing_action(chat_id):
    bot.send_chat_action(chat_id, 'typing')

# Уведомление участников группы о изменениях
def notify_group_users(group_id, message_text, actor_id):
    """Уведомляет пользователей в группе об изменениях, исключая инициатора."""
    users = execute_query(
        "SELECT user_id FROM user_groups WHERE group_id = ?",
        (group_id,),
        fetch=True
    )

    if users:
        for user in users:
            user_id = user[0]
            if user_id != actor_id:
                try:
                    bot.send_message(user_id, message_text, parse_mode="Markdown")
                except telebot.apihelper.ApiTelegramException as e:
                    if e.error_code == 403:
                        logger.error(f"Не могу отправить сообщение пользователю {user_id}: {e.description}")
                    else:
                        logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e.description}")
    else:
        logger.error(f"Пользователи не найдены в группе {group_id}")

# Обработка объединения списков
@bot.message_handler(func=lambda message: message.text == SHARE_LIST)
def share_list(message):
    """Предлагает пользователю объединить список с другим пользователем."""
    share_code = generate_share_code(message.from_user.id)
    bot.send_message(message.chat.id,
                     f"🤝 *Ваш код для объединения списка*: `{share_code}`\n\n"
                     "Отправьте этот код другу, чтобы он мог присоединиться к вашему списку.",
                     parse_mode="Markdown")
    bot.send_message(message.chat.id, "👥 *Когда ваш друг будет готов, пусть отправит боту команду /join* и введет код.", parse_mode="Markdown")

# Генерация кода для объединения списков
def generate_share_code(user_id):
    group_id = get_or_create_group(user_id)
    share_code = str(uuid.uuid4())[:8]
    execute_query("UPDATE groups SET share_code = ? WHERE group_id = ?", (share_code, group_id))
    return share_code

# Обработчик команды /join
@bot.message_handler(commands=['join'])
def join_group(message):
    bot.send_message(message.chat.id, "🔑 *Пожалуйста, введите код для присоединения к списку:*", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_join_code)

def process_join_code(message):
    share_code = message.text.strip()
    group = execute_query("SELECT group_id FROM groups WHERE share_code = ?", (share_code,), fetchone=True)
    if group:
        group_id = group[0]
        user_id = message.from_user.id
        # Проверяем, не состоит ли пользователь уже в этой группе
        existing = execute_query("SELECT 1 FROM user_groups WHERE user_id = ? AND group_id = ?", (user_id, group_id), fetchone=True)
        if not existing:
            # Удаляем пользователя из его текущей группы
            execute_query("DELETE FROM user_groups WHERE user_id = ?", (user_id,))
            # Добавляем в новую группу
            execute_query("INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)", (user_id, group_id))
            bot.send_message(message.chat.id, "✅ *Вы успешно присоединились к списку!*", reply_markup=main_menu(), parse_mode="Markdown")
            # Уведомляем других участников группы
            notify_group_users(group_id, f'👤 *{escape_markdown(message.from_user.first_name)} присоединился к вашему списку!*', user_id)
        else:
            bot.send_message(message.chat.id, "ℹ️ *Вы уже состоите в этом списке.*", reply_markup=main_menu(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ *Неверный код. Пожалуйста, попробуйте еще раз.*", reply_markup=main_menu(), parse_mode="Markdown")

# Обработка добавления элементов по тексту
@bot.message_handler(func=lambda message: message.text not in [SHOPPING_LIST, CLEAR_LIST, SHARE_LIST, ABOUT_APP, MY_ID])
def ask_to_add(message):
    """Спрашивает пользователя, хочет ли он добавить товар в список."""
    item = message.text.strip()
    if item:
        user_id = message.from_user.id
        user_temp_items[user_id] = item  # Сохраняем элемент для пользователя
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="✅ Да", callback_data=f"add_yes"))
        markup.add(types.InlineKeyboardButton(text="❌ Нет", callback_data="cancel"))
        bot.send_message(message.chat.id, f'🤔 *Добавить* "{escape_markdown(item)}" *в список покупок?*', reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректное название продукта.", reply_markup=main_menu())

# Обработка подтверждения добавления элемента
@bot.callback_query_handler(func=lambda call: call.data in ['add_yes', 'cancel'])
def handle_add_item(call):
    """Обрабатывает подтверждение добавления элемента."""
    user_id = call.from_user.id
    if call.data == 'cancel':
        user_temp_items.pop(user_id, None)
        bot.answer_callback_query(call.id, "🚫 Операция отменена.")
        send_main_menu(call.message)
        return

    item = user_temp_items.pop(user_id, None)
    if not item:
        bot.answer_callback_query(call.id, "❌ Не удалось добавить продукт.")
        return

    group_id = get_or_create_group(user_id)

    send_typing_action(call.message.chat.id)

    # Добавляем элемент в список группы
    execute_query("INSERT OR IGNORE INTO lists (group_id, item) VALUES (?, ?)", (group_id, item))

    # Уведомляем участников группы
    notify_group_users(group_id, f'🔔 *"{escape_markdown(item)}" был добавлен в список!*', user_id)

    bot.answer_callback_query(call.id, f'✅ Продукт "{item}" добавлен в список.')
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=f'✨ Продукт "{escape_markdown(item)}" добавлен в список!', parse_mode="Markdown")

    # Отображаем обновленный список покупок
    show_list(call.message, user_id)

# Обработка удаления элемента из списка
@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_item(call):
    """Удаляет элемент из списка группы."""
    item_id = call.data.split('_', 1)[1]
    user_id = call.from_user.id
    group_id = get_or_create_group(user_id)

    # Получаем название элемента перед удалением
    item = execute_query("SELECT item FROM lists WHERE item_id = ? AND group_id = ?", (item_id, group_id), fetchone=True)
    if not item:
        bot.answer_callback_query(call.id, "❌ Элемент не найден.")
        return
    item = item[0]

    send_typing_action(call.message.chat.id)

    # Удаляем элемент из списка группы
    execute_query("DELETE FROM lists WHERE item_id = ? AND group_id = ?", (item_id, group_id))

    # Уведомляем участников группы
    notify_group_users(group_id, f'🔔 *"{escape_markdown(item)}" был удалён из списка!*', user_id)

    bot.answer_callback_query(call.id, "🗑️ Элемент удалён.")

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
        '''SELECT item_id, item FROM lists WHERE group_id = ?''',
        (group_id,),
        fetch=True
    )

    if items:
        item_list = ''
        markup = types.InlineKeyboardMarkup()
        for idx, (item_id, item) in enumerate(items, 1):
            item_text = f"{idx}. {item}"
            item_list += item_text + "\n"
            # Добавляем кнопку удаления для каждого элемента
            button = types.InlineKeyboardButton(text=f"❌ {item}", callback_data=f"delete_{item_id}")
            markup.add(button)

        bot.send_message(message.chat.id, f"🛒 *Ваш список покупок*:\n\n{escape_markdown(item_list)}",
                         parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "🛒 *Ваш список покупок пуст.*\n\nДобавьте товары, отправив их названия сообщением.", parse_mode="Markdown")

    # Отображаем главное меню
    bot.send_message(message.chat.id, "👇 *Выберите действие из меню ниже:*", reply_markup=main_menu(has_items=bool(items)), parse_mode="Markdown")

# Подтверждение очистки списка
@bot.message_handler(func=lambda message: message.text == CLEAR_LIST)
def confirm_clear_list(message):
    """Запрашивает подтверждение перед очисткой списка."""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Да", callback_data="confirm_clear"))
    markup.add(types.InlineKeyboardButton("❌ Нет", callback_data="cancel"))
    bot.send_message(message.chat.id, "🗑️ *Вы уверены, что хотите очистить список?*", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'confirm_clear')
def clear_list(call):
    """Очищает список группы после подтверждения."""
    user_id = call.from_user.id
    group_id = get_or_create_group(user_id)

    send_typing_action(call.message.chat.id)

    # Очищаем список группы
    execute_query("DELETE FROM lists WHERE group_id = ?", (group_id,))
    bot.answer_callback_query(call.id, "🗑️ Список очищен.")
    bot.send_message(call.message.chat.id, "🗑️ *Список покупок очищен.*", reply_markup=main_menu(has_items=False), parse_mode="Markdown")

    # Уведомляем участников группы
    notify_group_users(group_id, f'🗑️ *Список покупок был очищен!*', user_id)

# Отмена действия
@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def cancel_action(call):
    bot.answer_callback_query(call.id, "🚫 Действие отменено.")
    send_main_menu(call.message)

# Информация о приложении
@bot.message_handler(func=lambda message: message.text == ABOUT_APP)
def about_app(message):
    """Предоставляет информацию о приложении."""
    bot.send_message(
        message.chat.id,
        "👋 *Добро пожаловать!*\n\n"
        "Я - ваш персональный бот для управления списками покупок. С помощью меня вы можете:\n\n"
        "🔹 Добавлять товары в список.\n"
        "🔹 Удалять товары из списка.\n"
        "🔹 Объединять списки с друзьями и родственниками.\n\n"
        "Просто отправьте название товара, и я помогу вам его добавить!",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

# Показать ID пользователя
@bot.message_handler(func=lambda message: message.text == MY_ID)
def show_user_id(message):
    """Показывает ID пользователя."""
    bot.send_message(message.chat.id, f"🆔 *Ваш ID*: `{message.from_user.id}`", parse_mode="Markdown", reply_markup=main_menu())

if __name__ == "__main__":
    create_tables()
    # Бот будет запущен из main.py
