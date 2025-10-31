#!/bin/bash

# Простой скрипт для установки и запуска демона Forum CRK MAX Bot
# Использование: sudo ./install.sh

set -e

echo "=========================================="
echo "Установка Forum CRK MAX Bot демона"
echo "=========================================="

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "Ошибка: Скрипт должен быть запущен от root (используйте sudo)"
    exit 1
fi

# Путь к директории бота
BOT_DIR="/root/maxbot/forum_crk_maxbot"
SERVICE_FILE="forum-crk-maxbot.service"

# Проверка директории
if [ ! -d "$BOT_DIR" ]; then
    echo "Ошибка: Директория $BOT_DIR не найдена!"
    echo "Создайте директорию и скопируйте туда файлы бота."
    exit 1
fi

echo "✓ Директория найдена: $BOT_DIR"

# Проверка service файла
if [ ! -f "$SERVICE_FILE" ]; then
    echo "Ошибка: Файл $SERVICE_FILE не найден!"
    exit 1
fi

echo "✓ Service файл найден"

# Копирование service файла
echo "Копирование systemd service файла..."
cp "$SERVICE_FILE" /etc/systemd/system/
echo "✓ Service файл установлен"

# Перезагрузка systemd
echo "Перезагрузка systemd..."
systemctl daemon-reload
echo "✓ Systemd перезагружен"

# Включение автозапуска
echo "Включение автозапуска..."
systemctl enable forum-crk-maxbot
echo "✓ Автозапуск включен"

# Запуск демона
echo "Запуск демона..."
systemctl start forum-crk-maxbot
echo "✓ Демон запущен"

# Проверка статуса
echo ""
echo "Проверка статуса..."
systemctl status forum-crk-maxbot --no-pager -l

echo ""
echo "=========================================="
echo "✓ Установка завершена!"
echo "=========================================="
echo ""
echo "Команды для управления:"
echo "  Статус:     sudo systemctl status forum-crk-maxbot"
echo "  Логи:       sudo journalctl -u forum-crk-maxbot -f"
echo "  Перезапуск: sudo systemctl restart forum-crk-maxbot"
echo "  Остановка:  sudo systemctl stop forum-crk-maxbot"
echo ""
