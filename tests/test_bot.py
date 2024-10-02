# test_bot.py
import unittest
import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from telebot import types

from bot import execute_query, create_tables, get_group_id
from bot import SHOPPING_LIST, CLEAR_LIST, SHARE_LIST, ABOUT_APP, MY_ID
from bot import bot
from config import API_TOKEN, TEST_DB_NAME

class TestShoppingListBot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set up the test database
        if os.path.exists(TEST_DB_NAME):
            os.remove(TEST_DB_NAME)
        create_tables(db_name=TEST_DB_NAME)

    @classmethod
    def tearDownClass(cls):
        # Remove the test database
        if os.path.exists(TEST_DB_NAME):
            os.remove(TEST_DB_NAME)

    def setUp(self):
        # Mock the bot's send_message and other methods
        self.bot_patcher = patch('bot.bot')
        self.mock_bot = self.bot_patcher.start()
        self.addCleanup(self.bot_patcher.stop)

    def test_start_command(self):
        # Simulate a /start command
        from bot import start

        message = MagicMock()
        message.from_user.id = 12345
        message.from_user.username = 'testuser'
        message.from_user.first_name = 'Test'
        message.chat.id = 12345

        with patch('bot.execute_query') as mock_execute_query:
            start(message)
            # Check that the user is inserted into the database
            mock_execute_query.assert_any_call(
                "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (12345, 'testuser', 'Test'),
                db_name=TEST_DB_NAME
            )

    def test_add_item(self):
        # Simulate adding an item
        from bot import ask_to_add, handle_add_item, temp_items

        message = MagicMock()
        message.from_user.id = 12345
        message.text = 'Milk'
        message.chat.id = 12345

        # Mock get_group_id to return a test group id
        with patch('bot.get_group_id', return_value=1), \
             patch('bot.execute_query') as mock_execute_query:

            # Simulate sending item name
            ask_to_add(message)

            # Check that temp_items has been populated
            self.assertEqual(len(temp_items), 1)
            item_id, item_name = next(iter(temp_items.items()))
            self.assertEqual(item_name, 'Milk')

            # Simulate the callback query for adding the item
            call = MagicMock()
            call.data = f'add_{item_id}'
            call.from_user.id = 12345
            call.message.chat.id = 12345
            call.message.message_id = 1

            handle_add_item(call)

            # Check that the item was added to the database
            mock_execute_query.assert_any_call(
                "INSERT OR IGNORE INTO lists (group_id, item) VALUES (?, ?)",
                (1, 'Milk'),
                db_name=TEST_DB_NAME
            )

    def test_delete_item(self):
        # Simulate deleting an item
        from bot import delete_item

        # Assume the item with rowid 1 exists
        execute_query("INSERT INTO lists (group_id, item) VALUES (?, ?)", (1, 'Milk'), db_name=TEST_DB_NAME)

        call = MagicMock()
        call.data = 'delete_1'
        call.from_user.id = 12345
        call.message.chat.id = 12345
        call.message.message_id = 1

        with patch('bot.execute_query') as mock_execute_query, \
             patch('bot.get_group_id', return_value=1):

            # Mock the select query to return the item
            mock_execute_query.side_effect = [
                ('Milk',),  # Return value for SELECT item
                None  # Return value for DELETE operation
            ]

            delete_item(call)

            # Check that the delete query was executed
            mock_execute_query.assert_any_call(
                "DELETE FROM lists WHERE rowid = ? AND group_id = ?",
                ('1', 1),
                db_name=TEST_DB_NAME
            )

    def test_show_list(self):
        # Simulate showing the shopping list
        from bot import show_list

        message = MagicMock()
        message.from_user.id = 12345
        message.chat.id = 12345

        # Insert test data
        execute_query("INSERT INTO lists (group_id, item) VALUES (?, ?)", (1, 'Milk'), db_name=TEST_DB_NAME)
        execute_query("INSERT INTO lists (group_id, item) VALUES (?, ?)", (1, 'Bread'), db_name=TEST_DB_NAME)

        with patch('bot.get_group_id', return_value=1), \
             patch('bot.execute_query') as mock_execute_query:

            # Mock the select query to return items
            mock_execute_query.return_value = [
                (1, 'Milk'),
                (2, 'Bread')
            ]

            show_list(message)

            # Check that the bot sends the correct message
            bot.send_message.assert_any_call(
                12345,
                '🛒 *Ваш список покупок*:\n\n1. Milk\n2. Bread',
                parse_mode='Markdown',
                reply_markup=types.InlineKeyboardMarkup()
            )

if __name__ == '__main__':
    unittest.main()
