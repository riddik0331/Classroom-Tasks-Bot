# Google Classroom Notifier

Telegram-бот для мониторинга заданий Google Classroom через email-уведомления.

## Возможности

- 📧 Автоматическое чтение писем от Google Classroom через Gmail API
- 🔄 Проверка только непрочитанных писем с пометкой прочитанными
- 📅 Автоматический расчёт дедлайна по расписанию уроков
- 📱 Telegram-бот с кнопками: "Сформировать", "Сегодня", "Завтра", "Неделя"
- 💾 Сохранение заданий в Excel-файл

## Требования

- Python 3.10+
- Telegram бот (получить от @BotFather)
- Google аккаунт с доступом к Gmail

## Установка

1. Клонировать репозиторий:
```bash
git clone <repo-url>
cd 06_TeleBot-HomeTasks
```

2. Установить зависимости:
```bash
pip install -r requirements.txt
```

3. Настроить Google OAuth:
   - Перейти в [Google Cloud Console](https://console.cloud.google.com)
   - Создать проект
   - Включить Gmail API
   - Создать OAuth 2.0 credentials
   - Скачать `credentials.json` в корень проекта

4. Получить токен доступа:
```bash
python -c "from src.gmail_client import GmailClient; GmailClient('credentials.json', 'config/token.json').authorize()"
```

## Настройка

1. Скопировать `.env.example` в `.env`:
```bash
cp .env.example .env
```

2. Заполнить `.env`:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

## Запуск

### Telegram бот:
```bash
python run_bot.py
```

### CLI команды:
```bash
python src/main.py check        # Проверить новые задания
python src/main.py list       # Показать все задания
python src/main.py today    # Задания на сегодня
python src/main.py tomorrow # Задания на завтра
python src/main.py week     # Задания на неделю
```

## Структура проекта

```
├── src/
│   ├── main.py           # CLI интерфейс
│   ├── config.py       # Загрузка конфигурации
│   ├── gmail_client.py   # Gmail API клиент
│   ├── parser.py       # Парсер писем Classroom
│   ├── storage.py     # Excel хранилище заданий
│   ├── timetable.py   # Модуль расписания
│   └── telegram_bot.py # Telegram бот
├── run_bot.py             # Скрипт запуска бота
├── assignments.xlsx      # Файл с заданиями
├── timetable.xlsx      # Расписание уроков
├── credentials.json    # Google OAuth (git игнор)
└── .env              # Конфигурация (git игнор)
```

## Лицензия

MIT