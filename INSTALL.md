# Установка Forum CRK MAX Bot на Ubuntu

Инструкция по установке и настройке бота для форума "Цифровая республика. ИТ-герои" на Ubuntu сервере.

## Требования

- Ubuntu 18.04 или выше
- Python 3.8 или выше
- Права root (sudo)

## Шаги установки

### 1. Подготовка сервера

Установите необходимые пакеты:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

### 2. Копирование файлов бота

Скопируйте все файлы бота в директорию `/opt/forum-crk-maxbot`:

```bash
sudo mkdir -p /opt/forum-crk-maxbot
sudo cp -r * /opt/forum-crk-maxbot/
```

Или используйте git:

```bash
sudo mkdir -p /opt/forum-crk-maxbot
sudo git clone <repository_url> /opt/forum-crk-maxbot
```

### 3. Запуск установочного скрипта

Перейдите в директорию с файлами бота и запустите установочный скрипт:

```bash
cd /opt/forum-crk-maxbot
sudo chmod +x install.sh
sudo ./install.sh
```

Скрипт автоматически:
- Создаст виртуальное окружение (если его нет)
- Установит все зависимости из `requirements.txt`
- Создаст шаблон файла `.env` (если его нет)
- Настроит права доступа
- Установит systemd service файл

### 4. Настройка .env файла

Отредактируйте файл `.env` и укажите необходимые параметры:

```bash
sudo nano /opt/forum-crk-maxbot/.env
```

Обязательно укажите:
- `BOT_TOKEN` - токен бота MAX
- `ADMIN_ID` - ваш user_id в MAX (для команды `/send_feedback`)

Пример файла `.env`:

```env
BOT_TOKEN=f9LHodD0cOJGwOcjJIQC...
REGISTRATION_URL=https://olddigital.rkomi.ru/event/#visit
FORUM_SITE_URL=https://olddigital.rkomi.ru/event/#visit
QUESTION_FORM_URL=https://forms.yandex.ru/...
TRACK_GAMEDEV_IMAGE=https://example.com/gamedev.jpg
TRACK_AI_IMAGE=https://example.com/ai.jpg
TRACK_DRONES_IMAGE=https://example.com/drones.jpg
TRACK_MEDIA_IMAGE=https://example.com/media.jpg
EXCEL_FILE_PATH=forum_data.xlsx
ADMIN_ID=17628474
```

### 5. Запуск бота

После настройки `.env` файла запустите бота:

```bash
# Запуск бота
sudo systemctl start forum-crk-maxbot

# Включить автозапуск при перезагрузке системы
sudo systemctl enable forum-crk-maxbot

# Проверить статус
sudo systemctl status forum-crk-maxbot
```

## Управление ботом

### Основные команды

```bash
# Запустить бота
sudo systemctl start forum-crk-maxbot

# Остановить бота
sudo systemctl stop forum-crk-maxbot

# Перезапустить бота
sudo systemctl restart forum-crk-maxbot

# Проверить статус
sudo systemctl status forum-crk-maxbot

# Включить автозапуск при загрузке системы
sudo systemctl enable forum-crk-maxbot

# Отключить автозапуск
sudo systemctl disable forum-crk-maxbot
```

### Просмотр логов

```bash
# Последние логи
sudo journalctl -u forum-crk-maxbot -n 50

# Логи в реальном времени (live)
sudo journalctl -u forum-crk-maxbot -f

# Логи за последний час
sudo journalctl -u forum-crk-maxbot --since "1 hour ago"

# Логи за сегодня
sudo journalctl -u forum-crk-maxbot --since today
```

### Просмотр ошибок

```bash
# Только ошибки
sudo journalctl -u forum-crk-maxbot -p err

# Ошибки и предупреждения
sudo journalctl -u forum-crk-maxbot -p warning
```

## Обновление бота

Если нужно обновить код бота:

```bash
# Остановить бота
sudo systemctl stop forum-crk-maxbot

# Обновить файлы (например, через git)
cd /opt/forum-crk-maxbot
sudo git pull

# Или скопировать новые файлы
sudo cp -r /path/to/new/files/* /opt/forum-crk-maxbot/

# Обновить зависимости (если изменились)
cd /opt/forum-crk-maxbot
source .venv/bin/activate
pip install -r requirements.txt

# Запустить бота снова
sudo systemctl start forum-crk-maxbot
```

## Ручная установка (без скрипта)

Если вы предпочитаете установить вручную:

### 1. Создать виртуальное окружение

```bash
cd /opt/forum-crk-maxbot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Создать .env файл

```bash
nano /opt/forum-crk-maxbot/.env
# Заполните необходимые переменные
```

### 3. Установить права

```bash
sudo chown -R www-data:www-data /opt/forum-crk-maxbot
```

### 4. Скопировать service файл

```bash
sudo cp forum-crk-maxbot.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### 5. Запустить бота

```bash
sudo systemctl start forum-crk-maxbot
sudo systemctl enable forum-crk-maxbot
```

## Устранение неполадок

### Бот не запускается

1. Проверьте логи:
   ```bash
   sudo journalctl -u forum-crk-maxbot -n 100
   ```

2. Проверьте файл `.env`:
   ```bash
   sudo cat /opt/forum-crk-maxbot/.env
   ```

3. Проверьте права доступа:
   ```bash
   ls -la /opt/forum-crk-maxbot
   ```

4. Проверьте, что токен бота указан правильно в `.env`

### Бот падает с ошибками

1. Проверьте логи на наличие ошибок:
   ```bash
   sudo journalctl -u forum-crk-maxbot -p err -f
   ```

2. Убедитесь, что все зависимости установлены:
   ```bash
   cd /opt/forum-crk-maxbot
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Проверьте подключение к интернету (боту нужен доступ к MAX API)

### Изменить пользователя для запуска

Если нужно запускать от другого пользователя, отредактируйте service файл:

```bash
sudo nano /etc/systemd/system/forum-crk-maxbot.service
```

Измените строки:
```
User=your-username
Group=your-groupname
```

Затем перезагрузите systemd и перезапустите бота:

```bash
sudo systemctl daemon-reload
sudo systemctl restart forum-crk-maxbot
```

## Структура файлов

После установки структура должна быть такой:

```
/opt/forum-crk-maxbot/
├── .venv/              # Виртуальное окружение
├── .env                # Конфигурация (создается автоматически)
├── main.py             # Главный файл бота
├── config.py           # Модуль конфигурации
├── requirements.txt    # Зависимости
├── forum_data.xlsx     # Excel файл с данными (создается автоматически)
├── users_db.json       # База пользователей (создается автоматически)
├── user_states.json    # Состояния FSM (создается автоматически)
├── utils/
│   └── sheets.py       # Модуль работы с Excel
└── ...
```

## Безопасность

- Файл `.env` содержит конфиденциальные данные (токен бота)
- Убедитесь, что права доступа настроены правильно:
  ```bash
  sudo chmod 600 /opt/forum-crk-maxbot/.env
  ```

- Не коммитьте файл `.env` в git репозиторий (он должен быть в `.gitignore`)

## Контакты и поддержка

При возникновении проблем проверьте логи и убедитесь, что все шаги установки выполнены правильно.

