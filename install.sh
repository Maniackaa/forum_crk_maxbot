#!/bin/bash

# Скрипт установки и настройки бота для форума CRK MAX
# Использование: sudo ./install.sh

set -e

echo "=========================================="
echo "Установка Forum CRK MAX Bot"
echo "=========================================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Ошибка: Скрипт должен быть запущен от root (используйте sudo)${NC}"
    exit 1
fi

# Путь к директории бота (по умолчанию)
BOT_DIR="/opt/forum-crk-maxbot"
SERVICE_FILE="forum-crk-maxbot.service"

echo -e "${YELLOW}Шаг 1: Проверка директории бота...${NC}"
if [ ! -d "$BOT_DIR" ]; then
    echo -e "${RED}Ошибка: Директория $BOT_DIR не найдена!${NC}"
    echo "Создайте директорию и скопируйте туда файлы бота, затем запустите скрипт снова."
    exit 1
fi

echo -e "${GREEN}✓ Директория найдена: $BOT_DIR${NC}"

echo -e "${YELLOW}Шаг 2: Проверка виртуального окружения...${NC}"
if [ ! -d "$BOT_DIR/.venv" ]; then
    echo -e "${YELLOW}Виртуальное окружение не найдено, создаю...${NC}"
    cd "$BOT_DIR"
    python3 -m venv .venv
    echo -e "${GREEN}✓ Виртуальное окружение создано${NC}"
else
    echo -e "${GREEN}✓ Виртуальное окружение найдено${NC}"
fi

echo -e "${YELLOW}Шаг 3: Установка зависимостей...${NC}"
cd "$BOT_DIR"
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Зависимости установлены${NC}"

echo -e "${YELLOW}Шаг 4: Проверка .env файла...${NC}"
if [ ! -f "$BOT_DIR/.env" ]; then
    echo -e "${YELLOW}Файл .env не найден. Создаю шаблон...${NC}"
    cat > "$BOT_DIR/.env" << EOF
# Токен бота MAX
BOT_TOKEN=your_bot_token_here

# Ссылка на регистрацию
REGISTRATION_URL=https://olddigital.rkomi.ru/event/#visit

# Ссылка на сайт форума
FORUM_SITE_URL=https://olddigital.rkomi.ru/event/#visit

# Ссылка на яндекс форму для вопросов
QUESTION_FORM_URL=

# URL изображений для треков (графика)
TRACK_GAMEDEV_IMAGE=
TRACK_AI_IMAGE=
TRACK_DRONES_IMAGE=
TRACK_MEDIA_IMAGE=

# Путь к Excel файлу для хранения вопросов и отзывов
EXCEL_FILE_PATH=forum_data.xlsx

# ID админа для рассылки (опционально)
ADMIN_ID=
EOF
    echo -e "${RED}⚠️ ВНИМАНИЕ: Отредактируйте файл .env и укажите токен бота!${NC}"
    echo "   Файл: $BOT_DIR/.env"
else
    echo -e "${GREEN}✓ Файл .env найден${NC}"
fi

echo -e "${YELLOW}Шаг 5: Установка прав доступа...${NC}"
chown -R www-data:www-data "$BOT_DIR"
chmod +x "$BOT_DIR/main.py"
echo -e "${GREEN}✓ Права установлены${NC}"

echo -e "${YELLOW}Шаг 6: Копирование systemd service файла...${NC}"
if [ ! -f "$SERVICE_FILE" ]; then
    echo -e "${RED}Ошибка: Файл $SERVICE_FILE не найден в текущей директории!${NC}"
    exit 1
fi

cp "$SERVICE_FILE" /etc/systemd/system/
echo -e "${GREEN}✓ Service файл скопирован${NC}"

echo -e "${YELLOW}Шаг 7: Перезагрузка systemd...${NC}"
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd перезагружен${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}Установка завершена!${NC}"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo "1. Отредактируйте файл .env: $BOT_DIR/.env"
echo "2. Убедитесь, что токен бота указан правильно"
echo ""
echo "Команды для управления ботом:"
echo "  Запустить:    sudo systemctl start forum-crk-maxbot"
echo "  Остановить:   sudo systemctl stop forum-crk-maxbot"
echo "  Перезапустить: sudo systemctl restart forum-crk-maxbot"
echo "  Статус:       sudo systemctl status forum-crk-maxbot"
echo "  Логи:         sudo journalctl -u forum-crk-maxbot -f"
echo "  Автозапуск:   sudo systemctl enable forum-crk-maxbot"
echo ""
echo -e "${YELLOW}После настройки .env файла запустите бота командой:${NC}"
echo "  sudo systemctl start forum-crk-maxbot"
echo "  sudo systemctl enable forum-crk-maxbot  # для автозапуска при перезагрузке"
echo ""

