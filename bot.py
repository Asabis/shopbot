import logging
import sqlite3
import sys
import telebot
from telebot import types
import uuid
from config import API_TOKEN, DB_NAME

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants for buttons and commands
SHOPPING_LIST = "🛍️ Список покупок"
CLEAR_LIST = "🗑️ Очистить список"
SHARE_LIST = "🔗 Объединить списки"
ABOUT_APP = "ℹ️ Информация о приложении"
MY_ID = "👤 Мой ID"

# Initialize bot
bot = telebot.TeleBot(API_TOKEN)

# Helper function for database operations
def execute_query(query, params=(), fetch=False, fetchone=False, lastrowid=False):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(query, params)
        if lastrowid:
            rowid = cursor.lastrowid
            conn.commit()
            conn.close()
            return rowid
        elif fetchone:
            result = cursor.fetchone()
            conn.close()
            return result
        elif fetch:
            result = cursor.fetchall()
            conn.close()
            return result
        else:
            conn.commit()
            conn.close()
            return None
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return None

# Create necessary database tables
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
            group_name TEXT
        )
    ''')
    execute_query('''
        CREATE TABLE IF NOT EXISTS user_groups (
            user_id INTEGER,
            group_id INTEGER,
            PRIMARY KEY (user_id, group_id)
        )
    ''')
    execute_query('''
        CREATE TABLE IF NOT EXISTS lists (
            rowid INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            item TEXT
        )
    ''')

# Escape markdown special characters
def escape_markdown(text):
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(['\\' + char if char in escape_chars else char for char in text])

# Main menu keyboard
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(SHOPPING_LIST, CLEAR_LIST)
    markup.add(SHARE_LIST)
    markup.add(MY_ID, ABOUT_APP)
    return markup

# Start command handler
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or ''
    first_name = message.from_user.first_name or ''

    # Save user to the database
    execute_query("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                  (user_id, username, first_name))

    # If user is not in any group, create a new group
    group = execute_query("SELECT group_id FROM user_groups WHERE user_id = ?", (user_id,), fetchone=True)
    if not group:
        try:
            # Create new group
            new_group_id = execute_query("INSERT INTO groups (group_name) VALUES (?)",
                                         (f"Group_{user_id}",), lastrowid=True)
            # Link user to the new group
            execute_query("INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)", (user_id, new_group_id))
        except sqlite3.Error as e:
            logger.error(f"Error creating new group: {e}")

    send_main_menu(message)

# Send the main menu
def send_main_menu(message):
    """Send the main menu message to the user."""
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

# Get group ID of the user
def get_group_id(user_id):
    """Return the group ID for the given user."""
    group = execute_query(
        "SELECT group_id FROM user_groups WHERE user_id = ?",
        (user_id,),
        fetchone=True
    )
    if group:
        return group[0]
    else:
        # If user doesn't have a group, create a new one
        try:
            new_group_id = execute_query("INSERT INTO groups (group_name) VALUES (?)",
                                         (f"Group_{user_id}",), lastrowid=True)
            execute_query("INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)", (user_id, new_group_id))
            return new_group_id
        except sqlite3.Error as e:
            logger.error(f"Error creating new group: {e}")
            return None

# Send a text-based "animation" for adding/deleting items
def send_animation(chat_id, action):
    """Send a loading text-based animation when adding or deleting items."""
    if action == "add":
        bot.send_message(chat_id, "🔄 *Добавляем продукт...*", parse_mode="Markdown")
    elif action == "delete":
        bot.send_message(chat_id, "🔄 *Удаляем продукт...*", parse_mode="Markdown")

# Notify group members about changes
def notify_group_users(group_id, message_text, actor_id):
    """Notify users in the group about changes, excluding the actor."""
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
                        logger.error(f"Cannot send message to user {user_id}: {e.description}")
                    else:
                        logger.error(f"Error sending message to user {user_id}: {e.description}")
    else:
        logger.error(f"No users found in group {group_id}")

# Handle sharing the list (merging groups)
@bot.message_handler(func=lambda message: message.text == SHARE_LIST)
def share_list(message):
    """Prompt the user to merge their list with another user."""
    bot.send_message(message.chat.id, "🤝 *Введите ID пользователя, с которым хотите объединить списки:*", parse_mode="Markdown")
    bot.register_next_step_handler(message, merge_with_user)

def merge_with_user(message):
    """Handle merging lists with another user."""
    try:
        target_id = int(message.text)
        user_id = message.from_user.id

        # Prevent merging with self
        if target_id == user_id:
            bot.send_message(message.chat.id, "❌ Вы не можете объединить список с самим собой.", reply_markup=main_menu())
            return

        # Check if the target user has started the bot
        try:
            user_info = bot.get_chat(target_id)
            if user_info.type != 'private':
                bot.send_message(message.chat.id, "❌ Нельзя объединить список с ботом или группой.", reply_markup=main_menu())
                return
            # Additionally check that the user is not a bot
            bot_info = bot.get_me()
            if user_info.id == bot_info.id:
                bot.send_message(message.chat.id, "❌ Нельзя объединить список с ботом.", reply_markup=main_menu())
                return
        except telebot.apihelper.ApiTelegramException as e:
            bot.send_message(message.chat.id, "❌ Пользователь с таким ID не найден или не начал диалог с ботом. Попросите пользователя отправить команду /start боту.", reply_markup=main_menu())
            return

        user_group_id = get_group_id(user_id)
        target_group_id = get_group_id(target_id)

        if user_group_id != target_group_id:
            # Merge groups
            # Move all users from target_group_id to user_group_id
            execute_query("UPDATE user_groups SET group_id = ? WHERE group_id = ?", (user_group_id, target_group_id))
            # Delete old group
            execute_query("DELETE FROM groups WHERE group_id = ?", (target_group_id,))
            # Merge lists
            items_to_merge = execute_query("SELECT item FROM lists WHERE group_id = ?", (target_group_id,), fetch=True)
            for item in items_to_merge:
                execute_query("INSERT OR IGNORE INTO lists (group_id, item) VALUES (?, ?)", (user_group_id, item[0]))
            # Delete old items from list
            execute_query("DELETE FROM lists WHERE group_id = ?", (target_group_id,))

            # Notify users
            target_username = user_info.first_name or user_info.username or 'Пользователь'
            bot.send_message(message.chat.id, f"🔗 *Ваш список объединен с пользователем {escape_markdown(target_username)}!*", reply_markup=main_menu(), parse_mode="Markdown")
            bot.send_message(target_id, f"🔗 *Пользователь {escape_markdown(message.from_user.first_name or 'Пользователь')} объединил свой список с вашим!*", parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "🔗 *Ваши списки уже объединены!*", reply_markup=main_menu(), parse_mode="Markdown")

    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректный ID.", reply_markup=main_menu())

# Global dictionary to store items temporarily
temp_items = {}

# Handle adding items when user inputs text
@bot.message_handler(func=lambda message: message.text not in [SHOPPING_LIST, CLEAR_LIST, SHARE_LIST, ABOUT_APP, MY_ID])
def ask_to_add(message):
    """Ask the user to confirm adding an item to the list."""
    item = message.text.strip()
    if item:
        item_id = str(uuid.uuid4())
        temp_items[item_id] = item  # Store item temporarily
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="✅ Да", callback_data=f"add_{item_id}"))
        markup.add(types.InlineKeyboardButton(text="❌ Нет", callback_data="cancel"))
        bot.send_message(message.chat.id, f'🤔 *Добавить* "{escape_markdown(item)}" *в список покупок?*', reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректное название продукта.", reply_markup=main_menu())

# Handle adding the item to the list
@bot.callback_query_handler(func=lambda call: call.data.startswith('add_') or call.data == 'cancel')
def handle_add_item(call):
    """Handle the confirmation to add an item."""
    if call.data == 'cancel':
        bot.answer_callback_query(call.id, "🚫 Операция отменена.")
        send_main_menu(call.message)
        return

    item_id = call.data.split('_', 1)[1]
    item = temp_items.pop(item_id, None)  # Retrieve and remove the item
    if not item:
        bot.answer_callback_query(call.id, "❌ Не удалось добавить продукт.")
        return

    user_id = call.from_user.id
    group_id = get_group_id(user_id)

    send_animation(call.message.chat.id, "add")

    # Add item to group's list
    execute_query("INSERT OR IGNORE INTO lists (group_id, item) VALUES (?, ?)", (group_id, item))

    # Notify group members (excluding the actor)
    notify_group_users(group_id, f'🔔 *"{escape_markdown(item)}" был добавлен в список!*', user_id)

    bot.answer_callback_query(call.id, f'✅ Продукт "{item}" добавлен в список.')
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=f'✨ Продукт "{escape_markdown(item)}" добавлен в список!', parse_mode="Markdown")

    # Display the updated shopping list
    show_list(call.message)

# Handle deleting an item from the list
@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_item(call):
    """Delete an item from the group's shopping list."""
    item_id = call.data.split('_', 1)[1]
    user_id = call.from_user.id
    group_id = get_group_id(user_id)

    # Retrieve item name before deletion for notification
    item = execute_query("SELECT item FROM lists WHERE rowid = ? AND group_id = ?", (item_id, group_id), fetchone=True)
    if not item:
        bot.answer_callback_query(call.id, "❌ Элемент не найден.")
        return
    item = item[0]

    send_animation(call.message.chat.id, "delete")

    # Delete item from group's list
    execute_query("DELETE FROM lists WHERE rowid = ? AND group_id = ?", (item_id, group_id))

    # Notify group members (excluding the actor)
    notify_group_users(group_id, f'🔔 *"{escape_markdown(item)}" был удалён из списка!*', user_id)

    bot.answer_callback_query(call.id, "🗑️ Элемент удалён.")

    # Display the updated shopping list
    show_list(call.message)

# Show the shopping list
@bot.message_handler(func=lambda message: message.text == SHOPPING_LIST)
def show_list(message):
    user_id = message.from_user.id
    group_id = get_group_id(user_id)

    # Fetch items from group's list
    items = execute_query(
        '''SELECT rowid, item FROM lists WHERE group_id = ?''',
        (group_id,),
        fetch=True
    )

    if items:
        item_list = ''
        markup = types.InlineKeyboardMarkup()
        for idx, (item_id, item) in enumerate(items, 1):
            item_text = f"{idx}. {item}"
            item_list += item_text + "\n"
            # Add delete button for each item
            button = types.InlineKeyboardButton(text=f"❌ Удалить {item}", callback_data=f"delete_{item_id}")
            markup.add(button)

        bot.send_message(message.chat.id, f"🛒 *Ваш список покупок*:\n\n{escape_markdown(item_list)}",
                         parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "🛒 *Ваш список покупок пуст.*\n\nДобавьте товары, отправив их названия сообщением.", parse_mode="Markdown")

    # Show main menu after displaying the list
    bot.send_message(message.chat.id, "👇 *Выберите действие из меню ниже:*", reply_markup=main_menu(), parse_mode="Markdown")

# Clear the shopping list
@bot.message_handler(func=lambda message: message.text == CLEAR_LIST)
def clear_list(message):
    """Clear the group's shopping list."""
    user_id = message.from_user.id
    group_id = get_group_id(user_id)

    send_animation(message.chat.id, "delete")

    # Clear group's list
    execute_query("DELETE FROM lists WHERE group_id = ?", (group_id,))
    bot.send_message(message.chat.id, "🗑️ *Список покупок очищен*.", reply_markup=main_menu(), parse_mode="Markdown")

    # Notify group members (excluding the actor)
    notify_group_users(group_id, f'🗑️ *Список покупок был очищен!*', user_id)

# About command
@bot.message_handler(func=lambda message: message.text == ABOUT_APP)
def about_app(message):
    """Provide information about the app."""
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

# Show user ID
@bot.message_handler(func=lambda message: message.text == MY_ID)
def show_user_id(message):
    """Show the user's ID."""
    bot.send_message(message.chat.id, f"🆔 *Ваш ID*: `{message.from_user.id}`", parse_mode="Markdown", reply_markup=main_menu())

if __name__ == "__main__":
    create_tables()
    try:
        bot.polling()
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1)
