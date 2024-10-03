# main.py


def start_bot():
    print("Запуск бота...")
    # Импортируем модуль бота и запускаем его
    import bot

    bot.create_tables()
    bot.bot.polling()


if __name__ == "__main__":
    start_bot()
