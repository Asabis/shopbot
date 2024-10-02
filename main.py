# main.py
import subprocess
import sys
import os

# def run_tests():
#     print("Running tests...")
#     test_script = os.path.join('tests', 'test_bot.py')
#     result = subprocess.run([sys.executable, test_script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
#     print(result.stdout.decode())

#     if result.returncode != 0:
#         print("Tests failed. Exiting.")
#         sys.exit(1)
#     else:
#         print("All tests passed.")

def start_bot():
    print("Starting the bot...")
    # Import the bot module and start polling
    import bot
    bot.create_tables()
    bot.bot.polling()

if __name__ == '__main__':
    # run_tests()
    start_bot()
