import unittest
import sqlite3
from bot import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = Database('test_database.db')

    def tearDown(self):
        self.db.execute('DROP TABLE IF EXISTS users')
        self.db.execute('DROP TABLE IF EXISTS lists')
        self.db.close()

    def test_execute_query_with_invalid_sql(self):
        with self.assertRaises(sqlite3.OperationalError):
            self.db.execute('SELECT * FROM non_existent_table')

if __name__ == '__main__':
    unittest.main()