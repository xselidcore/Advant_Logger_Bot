# Advant

> Telegram Business бот, который молча перехватывает удалённые и отредактированные сообщения в ваших личных чатах.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![aiogram](https://img.shields.io/badge/aiogram-3.5.0-009CC8?style=flat-square)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=flat-square)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479A1?style=flat-square&logo=mysql&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

---

## Что делает

Собеседник удалил сообщение. Отредактировал текст. Вы этого не увидите — если не используете Advant.

Бот подключается через Telegram Business и в реальном времени перехватывает все входящие сообщения, сохраняя их в зашифрованном виде. Как только собеседник удаляет или редактирует что-то — вы сразу получаете уведомление с оригинальным содержимым.

| Тип события | Что поддерживается |
|-------------|-------------------|
| 🗑 Удаление | Текст, фото, видео, голосовые, стикеры, документы, анимации, кружки |
| ✏️ Редактирование | Текст, подписи к медиа |

---

## Как работает хранение сообщений

### Жизненный цикл сообщения

```
Собеседник отправил сообщение
        │
        ▼
handlers/receive.py перехватывает его через business_message
        │
        ▼
Текст / file_id шифруется через Fernet (AES-128-CBC)
        │   ключ = business_connection_id бота (SHA-256 хеш для связки)
        ▼
Запись сохраняется в таблицу messages (MySQL)
        │
        ▼
Собеседник удалил / отредактировал сообщение
        │
        ▼
handlers/deleting.py или handlers/edit.py получают событие
        │
        ▼
Запись достаётся из БД, дешифруется, отправляется владельцу
        │
        ▼
Запись удаляется из БД (при удалении)
или обновляется новым зашифрованным текстом (при редактировании)
```

### Шифрование

Каждый пользователь имеет уникальный `business_connection_id` — строку, которую Telegram выдаёт при подключении бота к аккаунту. Именно она служит ключом шифрования.

```python
# utils/encryptor.py
class TextEncryptor:
    def __init__(self, key):
        key_bytes = str(key).encode()
        key_bytes += b'\x00' * (32 - len(key_bytes))  # дополняем до 32 байт
        self.cipher_suite = Fernet(base64.urlsafe_b64encode(key_bytes))
```

Алгоритм: **Fernet** (AES-128-CBC + HMAC-SHA256). Данные в базе нечитаемы без знания `connection_id`.

`connection_id` в таблице `users` хранится как **SHA-256 хеш** — даже зная содержимое БД, нельзя восстановить оригинальный ключ шифрования.

### Структура базы данных

**Таблица `users`**

| Поле | Тип | Описание |
|------|-----|---------|
| `id` | BIGINT PK | Telegram user ID |
| `connection_id` | VARCHAR(255) UNIQUE | SHA-256 хеш business_connection_id |
| `channel_id` | BIGINT | Зарезервировано |
| `language` | VARCHAR(4) | Язык пользователя (en/ru) |

**Таблица `messages`**

| Поле | Тип | Описание |
|------|-----|---------|
| `id` | INT PK | Автоинкремент |
| `connection_id` | VARCHAR | SHA-256 хеш — привязка к пользователю |
| `message_id` | BIGINT | ID сообщения в Telegram |
| `message` | TEXT | Зашифрованный текст / подпись |
| `is_sticker` | BOOL | Флаг стикера |
| `is_media` | BOOL | Флаг медиафайла |
| `sticker` | TEXT | Зашифрованный file_id стикера |
| `media` | TEXT | Зашифрованный file_id медиа |
| `media_type` | TEXT | Тип медиа (photo, video, voice…) |

> Сообщения хранятся **только до момента удаления или редактирования** — после отправки уведомления запись сразу удаляется из БД.

### Что происходит при отключении

Если пользователь отключает бота через Telegram Business:

1. Все записи в `messages` с его `connection_id` удаляются
2. Запись в `users` удаляется
3. Пользователь получает уведомление

При повторном подключении с новым `connection_id` — история предыдущей сессии также очищается.

---

## Стек

| Компонент | Технология |
|-----------|-----------|
| Bot framework | aiogram 3.5 |
| Database ORM | SQLAlchemy 2.0 + PyMySQL |
| Шифрование | cryptography ~42.0 (Fernet) |
| i18n | Babel 2.13 |
| Конфиг | configparser + pydantic |

---

## Структура проекта

```
advant/
├── filters/
│   └── ContentTypeFilter.py   # Определяет тип сообщения по записи в БД
├── handlers/
│   ├── receive.py             # Перехват входящих → шифрование → сохранение в БД
│   ├── deleting.py            # Обработка удалений → уведомление → удаление из БД
│   └── edit.py                # Обработка редактирований → уведомление → обновление в БД
├── locales/
│   ├── en/LC_MESSAGES/
│   └── ru/LC_MESSAGES/
├── middlewares/
│   └── user_check.py          # Синхронизация connection_id при каждом апдейте
├── repo/
│   ├── modules/
│   │   ├── users.py           # ORM модель + репозиторий пользователей
│   │   └── messages.py        # ORM модель + репозиторий сообщений
│   └── repo.py                # Точка входа в БД, создание таблиц
├── utils/
│   ├── config.py              # Парсинг config.ini через pydantic
│   └── encryptor.py           # Fernet шифрование + SHA-256 хеш
├── images/
│   └── welcome.png
├── config.ini.example
└── main.py                    # Точка входа, регистрация хендлеров
```

---

## Установка

### 1. Клонировать и создать окружение

```bash
git clone https://github.com/SyperAlexKomp/tg-message-logger-bot
cd tg-message-logger-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Настроить конфиг

```bash
cp config.ini.example config.ini
nano config.ini
```

```ini
[BOT]
token = ваш_токен_бота

[DATABASE]
username = root
password = пароль
ip = 127.0.0.1
port = 3306
db = advant
```

### 3. Включить Business Mode в BotFather

```
/mybots → ваш бот → Bot Settings → Business Mode → Enable
```

### 4. Скомпилировать переводы

```bash
msgfmt locales/ru/LC_MESSAGES/messages.po -o locales/ru/LC_MESSAGES/messages.mo
msgfmt locales/en/LC_MESSAGES/messages.po -o locales/en/LC_MESSAGES/messages.mo
```

### 5. Запустить

```bash
python main.py
```

---

## Деплой через systemd

```bash
cat > /etc/systemd/system/advant.service << 'EOF'
[Unit]
Description=Advant Bot
After=network.target

[Service]
WorkingDirectory=/root/advant
ExecStart=/root/advant/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now advant
```

---

## Подключение к Telegram

После запуска бота:

**Настройки → Telegram Business → Чат-боты → введите @username бота**

> Требуется активная подписка **Telegram Premium**.

---

## Лицензия

MIT