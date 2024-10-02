import logging
import sqlite3
import sys
from config import API_TOKEN, DB_NAME
import telebot
from telebot import types

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Constants
SHOPPING_LIST = "🛍️ Список покупок"
CLEAR_LIST = "🗑️ Очистить список"
SHARE_LIST = "🔗 Поделиться списком"
ABOUT_APP = "ℹ️ Информация о приложении"
MY_ID = "👤 Мой ID"
MENU = "/menu"

# Initialize the bot
bot = telebot.TeleBot(API_TOKEN)

# Class for database interactions
class Database:
    def __init__(self, db_name):
        self.db_name = db_name

    def connect(self):
        """Connect to the SQLite database."""
        try:
            return sqlite3.connect(self.db_name, check_same_thread=False)
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            return None

    def execute(self, query, params=(), fetch=False):
        """Execute a database query."""
        conn = self.connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                result = cursor.fetchall() if fetch else None
                if not fetch:
                    conn.commit()
                return result
            except sqlite3.Error as e:
                logger.error(f"Query execution error: {e}")
                return None
            finally:
                conn.close()
        logger.error("Database connection failed")
        return None

db = Database(DB_NAME)

# Initialize the database
def init_db():
    """Initialize database tables."""
    db.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    shared_list_with INTEGER)''')

    db.execute('''CREATE TABLE IF NOT EXISTS lists (
                    user_id INTEGER,
                    item TEXT,
                    PRIMARY KEY (user_id, item),
                    FOREIGN KEY (user_id) REFERENCES users(user_id))''')

init_db()

# Main menu
def main_menu():
    """Create the main menu for the bot."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(
        types.KeyboardButton(SHOPPING_LIST),
        types.KeyboardButton(CLEAR_LIST),
        types.KeyboardButton(SHARE_LIST),
        types.KeyboardButton(ABOUT_APP),
        types.KeyboardButton(MY_ID)
    )
    return markup

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    """Handle the start command."""
    user_id = message.from_user.id
    username = message.from_user.username
    db.execute("INSERT OR IGNORE INTO users (user_id, username, shared_list_with) VALUES (?, ?, '')", (user_id, username))
    send_main_menu(message)

# Send the main menu
def send_main_menu(message):
    """Send the main menu message to the user."""
    description = (
        "✨ Привет! Я ваш помощник для управления списком покупок!\n"
        "Вы можете:\n"
        "➕ Добавлять продукты в список.\n"
        "📋 Просматривать текущий список.\n"
        "🗑️ Удалять ненужные элементы.\n"
        "🔗 Делиться списком с друзьями.\n"
        "👤 Узнать свой ID.\n"
        "Нажмите на кнопку ниже, чтобы начать:"
    )
    bot.send_message(message.chat.id, description, reply_markup=main_menu(), parse_mode="Markdown")

# Add item to the list
@bot.message_handler(func=lambda message: message.text not in [SHOPPING_LIST, CLEAR_LIST, SHARE_LIST, ABOUT_APP, MY_ID])
def ask_to_add(message):
    """Ask the user to confirm adding an item to the list."""
    item = message.text
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="✅ Да", callback_data=f"add_{item}"))
    markup.add(types.InlineKeyboardButton(text="❌ Нет", callback_data="cancel"))
    bot.send_message(message.chat.id, f'🤔 *Добавить* "{item}" *в ваш список покупок?*', reply_markup=markup, parse_mode="Markdown")

# Handle adding item
@bot.callback_query_handler(func=lambda call: call.data.startswith('add_') or call.data == 'cancel')
def handle_add_item(call):
    """Handle the confirmation to add an item."""
    if call.data == 'cancel':
        bot.answer_callback_query(call.id, "🚫 Операция отменена.")
        send_main_menu(call.message)
        return

    item = call.data.split('_', 1)[1]
    user_id = call.from_user.id
    db.execute("INSERT INTO lists (user_id, item) VALUES (?, ?)", (user_id, item))
    bot.answer_callback_query(call.id, f'✅ Продукт "{item}" добавлен в список.')
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f'✨ Продукт "{item}" добавлен в ваш список!')
    show_list(call.message, user_id)

# Show the shopping list
@bot.message_handler(func=lambda message: message.text == SHOPPING_LIST)
def show_list(message, user_id=None):
    if user_id is None:
        user_id = message.from_user.id
    items = db.execute("SELECT item FROM lists WHERE user_id IN (SELECT user_id FROM users WHERE user_id = ? OR shared_list_with = ?)", (user_id,user_id,), fetch=True)

    if items:
        markup = types.InlineKeyboardMarkup()
        for item in items:
            markup.add(types.InlineKeyboardButton(text=f"❌ Удалить {item[0]}", callback_data=f"delete_{item[0]}"))
        bot.send_message(message.chat.id, f"🛒 Ваши покупки ({len(items)}):", reply_markup=markup)
        # bot.send_message(message.chat.id, "Главное меню", reply_markup=main_menu())
    else:
        bot.send_message(message.chat.id, "❌ У вас пока нет покупок.", reply_markup=main_menu())

# Delete item from the list
@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_item(call):
    """Delete an item from the user's shopping list."""
    item = call.data.split('_', 1)[1]
    user_id = call.from_user.id
    db.execute("DELETE FROM lists WHERE user_id IN (SELECT user_id FROM users WHERE user_id = ? OR shared_list_with = ?) AND item = ?", (user_id, user_id, item))
    bot.answer_callback_query(call.id, "🗑️ Элемент удалён.")
    show_list(call.message, user_id)

# Clear the shopping list
@bot.message_handler(func=lambda message: message.text == CLEAR_LIST)
def clear_list(message):
    """Clear the user's shopping list."""
    user_id = message.from_user.id
    db.execute("DELETE FROM lists WHERE user_id IN (SELECT user_id FROM users WHERE user_id = ? OR shared_list_with = ?)", (user_id, user_id))
    bot.send_message(message.chat.id, "🗑️ Ваш список покупок очищен.", reply_markup=main_menu())

# Share the shopping list
@bot.message_handler(func=lambda message: message.text == SHARE_LIST)
def share_list(message):
    """Prompt the user to share their shopping list."""
    bot.send_message(message.chat.id, "🤝 Введите ID пользователя для шаринга списка:")
    bot.register_next_step_handler(message, share_with_user)

# Logic for sharing the list
def share_with_user(message):
    """Handle the sharing of the shopping list with another user."""
    try:
        target_id = int(message.text)
        user_id = message.from_user.id
        target_user = db.execute("SELECT username FROM users WHERE user_id = ?", (target_id,), fetch=True)

        if not target_user:
            bot.send_message(message.chat.id, "❌ Пользователь с таким ID не найден.", reply_markup=main_menu())
            return

        # Update shared list information in the users table
        db.execute("UPDATE users SET shared_list_with = shared_list_with || ? WHERE user_id = ?", (target_id, user_id))
        bot.send_message(message.chat.id, f"📤 Список теперь доступен пользователю {target_user[0][0]}.", reply_markup=main_menu())
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректный ID.", reply_markup=main_menu())

# About command
@bot.message_handler(func=lambda message: message.text == ABOUT_APP)
def about_app(message):
    """Provide information about the app."""
    bot.send_message(message.chat.id, "👋 Это Telegram-бот для управления списками покупок.\n\n🔗 *Функции приложения:*\n- Добавление элементов\n- Удаление элементов\n- Общий доступ к спискам\n\n💡 Напишите /start, чтобы начать.", parse_mode="Markdown", reply_markup=main_menu())

# Show user ID
@bot.message_handler(func=lambda message: message.text == MY_ID)
def show_user_id(message):
    """Show the user's ID."""
    bot.send_message(message.chat.id, f"🆔 Ваш ID: {message.from_user.id}", reply_markup=main_menu())

if __name__ == "__main__":
    try:
        bot.polling()
    except KeyboardInterrupt:
        sys.exit()
