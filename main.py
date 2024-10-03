def start_bot():
    print("Запуск бота...")
    import bot

    bot.create_tables()
    bot.bot.polling()


if __name__ == "__main__":
    start_bot()
