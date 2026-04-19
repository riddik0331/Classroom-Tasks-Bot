# Google Classroom Notifier — Спецификация

## 1. Обзор проекта

**Название:** Google Classroom Notifier (Gmail Edition)
**Тип:** CLI-приложение для мониторинга заданий
**Язык:** Python 3.10+
**Платформа:** Linux (облачный сервер)

### Назначение

Автоматическая проверка новых заданий в Google Classroom через Gmail-уведомления. Работает от имени пользователя через OAuth 2.0.

---

## 2. Функциональные требования

### 2.1 Базовая функциональность

| Требование | Приоритет |
|-------------|-----------|
| Подключение к Gmail API через OAuth 2.0 | Must Have |
| Чтение писем от noreply@classroom.google.com | Must Have |
| Парсинг информации о задании из письма | Must Have |
| Определение "новых" заданий | Must Have |
| Вывод списка новых заданий в консоль | Must Have |
| Конфигурация через JSON/ENV файл | Must Have |
| Поддержка проверки по расписанию (cron-подобный режим) | Should Have |

### 2.2 Режимы работы

1. **Однократный запуск** — проверить один раз и вывести результат
2. **Daemon mode** — проверять каждые N минут, пока не остановят

### 2.3 Выходные данные

Для каждого нового задания выводить:
- Название курса
- Название задания
- Дата получения письма
- Ссылка на задание
- Дедлайн (если есть)

---

## 3. Архитектура

### 3.1 Структура проекта

```
google-classroom-notifier/
├── config/
│   ├── config.example.json    # Пример конфигурации
│   └── token.json             # OAuth токен (создаётся при первом запуске)
├── src/
│   ├── __init__.py
│   ├── main.py             # Точка входа
│   ├── config.py          # Загрузка конфигурации
│   ├── gmail_client.py    # Gmail API клиент
│   ├── parser.py          # Парсинг писем Classroom
│   └── notifier.py        # Логика уведомлений
├── credentials.json       # OAuth credentials (скачать из Cloud Console)
├── requirements.txt
├── README.md
└── run.sh                 # Скрипт запуска
```

### 3.2 Модули

| Модуль | Ответственность |
|--------|-----------------|
| `config.py` | Загрузка и валидация конфигурации |
| `gmail_client.py` | Работа с Gmail API |
| `parser.py` | Парсинг писем от Classroom |
| `notifier.py` | Определение новых заданий, форматирование вывода |
| `main.py` | CLI-интерфейс, управление режимами работы |

---

## 4. Технические требования

### 4.1 Зависимости

```
google-api-python-client>=2.100.0
google-auth>=2.20.0
google-auth-oauthlib>=1.0.0
python-dateutil>=2.8.2
```

### 4.2 Требования к окружению

- Python 3.10+
- Linux (Ubuntu 20.04+ / Debian 10+)
- Gmail аккаунт с доступом к письмам от Classroom
- OAuth credentials из Google Cloud Console

### 4.3 Конфигурация

```json
{
  "credentials_file": "credentials.json",
  "token_file": "config/token.json",
  "check_interval_minutes": 15,
  "state_file": "/var/lib/gcn/state.json",
  "daemon_mode": false,
  "log_level": "INFO"
}
```

---

## 5. Интерфейс

### 5.1 CLI-команды

```bash
# Однократный запуск (при первом запуске откроет браузер для авторизации)
python -m src.main check

# Запуск в демон режиме
python -m src.main daemon

# Показать help
python -m src.main --help

# Показать список курсов
python -m src.main courses
```

### 5.2 Пример вывода

```
🔔 Новые задания (2):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 Курс: Mathematics 101
   📝 Задание: Homework #5 - Linear Equations
   📅 Получено: 2026-04-17 10:30:00
   ⏰ Дедлайн: 2026-04-24 23:59:00
   🔗 Ссылка: https://classroom.google.com/...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 Курс: Physics 9A
   📝 Задание: Lab Report - Motion
   📅 Получено: 2026-04-17 09:15:00
   ⏰ Дедлайн: -
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 6. Как это работает

1. Google Classroom отправляет email на адрес ученика при создании задания
2. Письмо приходит от `noreply@classroom.google.com`
3. Программа читает эти письма через Gmail API
4. Парсит тему и тело письма, извлекая:
   - Название курса (из темы письма)
   - Название задания (из темы письма)
   - Дедлайн (из тела письма)
   - Ссылку на задание

### Пример темы письма Classroom:

```
New assignment in Mathematics 101: Homework #5 - Linear Equations
```

### Пример тела письма:

```
You have a new assignment in Mathematics 101.

Homework #5 - Linear Equations
Due: April 24, 2026 at 11:59 PM
```

---

## 7. Настройка Google Cloud Console

**ВНИМАНИЕ:** Настройка делается один раз. Требуется доступ к [Google Cloud Console](https://console.cloud.google.com).

### Шаги:

1. Создай проект в Google Cloud Console

2. Включи Gmail API:
   - APIs & Services > Library
   - Найди "Gmail API"
   - Нажми "Enable"

3. Настрой OAuth consent:
   - APIs & Services > OAuth consent screen
   - External
   - Заполни название приложения
   - Добавь свой email в "Test users"

4. Созда OAuth credentials:
   - APIs & Services > Credentials
   - "Create Credentials" > "OAuth client ID"
   - Desktop application
   - Скачай `credentials.json`

---

## 8. Acceptance Criteria

| Критерий | Проверка |
|----------|----------|
| OAuth авторизация работает | При первом запуске открывается браузер |
| Письма от Classroom читаются | Проверить на реальных письмах |
| Информация о задании парсится корректно | Сравнить с оригинальным письмом |
| Новые задания определяются по времени | Проверить на тестовых данных |
| Daemon mode работает с заданным интервалом | Запустить на 2-3 цикла |
| Конфигурация загружается из файла | Проверить с разными значениями |
| Программа не падает при отсутствии писем | Запустить на пустом inbox |

---

## 9. Ограничения (Out of Scope)

- ❌ Отправка уведомлений в Telegram/Email (добавим позже)
- ❌ Работа с Classroom API напрямую
- ❌ Автоматическая проверка работ учеников
- ❌ GUI-интерфейс

---

## 10. Следующие шаги (Future)

- [ ] Telegram-уведомления
- [ ] Работа нескольких аккаунтов
- [ ] Webhook для новых заданий
- [ ] REST API для внешних интеграций