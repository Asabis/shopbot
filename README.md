
# ShopBuddy Bot

**ShopBuddy** — это простой бот для управления списком покупок, созданный на Python с использованием Telegram Bot API. Бот позволяет пользователям создавать и управлять списками покупок, делиться ими с друзьями и сотрудничать в режиме реального времени. Он разработан для упрощения покупок с помощью удобных команд и кнопок.

## Возможности

- 🛍️ Создание и управление личным списком покупок.
- 👥 Совместное использование списка покупок с друзьями с помощью уникального кода.
- 🔗 Присоединение к общему списку покупок по коду друга.
- 📝 Добавление и удаление товаров из списка.
- 🗑️ Очистка всего списка покупок с подтверждением.
- ℹ️ Узнайте больше о приложении в разделе "О приложении".

## Требования

- Python 3.7+
- Аккаунт Telegram и токен бота от [BotFather](https://core.telegram.org/bots#botfather)
- SQLite3

## Установка

1. Клонируйте репозиторий:

    ```bash
    git clone https://github.com/yourusername/shopbuddy-bot.git
    cd shopbuddy-bot
    ```

2. Настройте виртуальное окружение и установите зависимости:

    ```bash
    python3 -m venv venv
    source venv/bin/activate  # На Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3. Настройте токен бота и имя базы данных в файле `config.py`:

    ```python
    API_TOKEN = 'YOUR_BOT_TOKEN'
    DB_NAME = 'shopbuddy.db'
    ```

4. Создайте базу данных и необходимые таблицы:

    Бот автоматически создаст базу данных и необходимые таблицы при первом запуске. Вы можете вручную создать их, выполнив:

    ```bash
    python main.py
    ```

5. Запустите бота:

    ```bash
    python main.py
    ```

## Команды

- `/start` - Запустить бота и создать новую группу покупок.
- `🛍️ Список покупок` - Показать текущий список покупок.
- `🗑️ Очистить список` - Очистить весь список покупок.
- `🔗 Поделиться списком` - Создать код для совместного использования списка покупок.
- `👥 Присоединиться к списку` - Присоединиться к общему списку покупок по коду.
- `ℹ️ О приложении` - Узнать информацию о боте.

## Использование

После запуска бота вы можете управлять списком покупок с помощью команд или нажатия кнопок в интерфейсе чата. Пользователи могут работать над одним списком вместе, отправляя друг другу коды для присоединения.

### Пример использования

1. **Создание списка покупок**: Когда пользователь запускает бота, он автоматически добавляется в новую группу и может начать добавлять товары в список.
2. **Совместное использование списка**: Пользователь может сгенерировать уникальный код и отправить его друзьям для совместной работы над одним списком покупок.
3. **Присоединение к списку**: Друзья могут присоединиться к списку покупок, введя полученный код.
4. **Обновления и уведомления**: Когда товары добавляются или удаляются из списка, все участники группы получают уведомление.

## Pre-commit Hooks

Для обеспечения качества кода и соблюдения стандартов, рекомендуется настроить pre-commit хуки.

### 1. Установка `pre-commit`

Сначала установите пакет `pre-commit`:

```bash
pip install pre-commit
```

### 2. Добавьте файл `.pre-commit-config.yaml` в корень проекта:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.0.1
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v0.950
    hooks:
      - id: mypy
  - repo: https://github.com/pre-commit/pyupgrade
    rev: v2.25.0
    hooks:
      - id: pyupgrade
```

### 3. Установите pre-commit хуки:

```bash
pre-commit install
```

Теперь при каждом коммите pre-commit хуки будут проверять такие моменты, как наличие лишних пробелов, корректные окончания файлов, синтаксис YAML/JSON, а также форматирование кода с помощью `black`.

### 4. Запуск pre-commit вручную:

Вы также можете запустить хуки на всех файлах вручную:

```bash
pre-commit run --all-files
```

## Вклад в проект

Если вы хотите внести свой вклад в проект, откройте pull request с вашими изменениями или создайте issue для сообщения об ошибке или запроса на добавление функции.

## Лицензия

Этот проект распространяется по лицензии MIT. Подробности смотрите в файле [LICENSE](LICENSE).
