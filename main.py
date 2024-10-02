import subprocess
import sys

def run_tests():
    # Запускаем тесты с помощью unittest
    result = subprocess.run([sys.executable, "test_bot.py"], capture_output=True, text=True)
    
    # Выводим результаты тестов
    print(result.stdout)
    
    # Проверяем, прошли ли тесты успешно
    if result.returncode == 0:
        print("Все тесты пройдены успешно. Запускаем бота...")
        return True
    else:
        print("Некоторые тесты не прошли. Бот не будет запущен.")
        return False

def run_bot():
    # Запуск бота, если тесты прошли успешно
    subprocess.run([sys.executable, "bot.py"])

if __name__ == "__main__":
    if run_tests():
        run_bot()
