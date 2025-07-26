#!/bin/bash

# Скрипт для развёртывания Telegram бота на сервере

echo "🚀 Начинаем развёртывание Melesha Nails Bot..."

# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Python и pip
sudo apt install python3 python3-pip python3-venv -y

# Создаём директорию для бота
mkdir -p /opt/melesha-bot
cd /opt/melesha-bot

# Клонируем репозиторий (замените на ваш URL)
git clone https://github.com/IgorSuhh/melesha_nails-2.0.git .
# Или копируем файлы вручную

# Создаём виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt

# Создаём systemd сервис
sudo tee /etc/systemd/system/melesha-bot.service > /dev/null <<EOF
[Unit]
Description=Melesha Nails Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/melesha-bot
Environment=PATH=/opt/melesha-bot/venv/bin
ExecStart=/opt/melesha-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd и запускаем сервис
sudo systemctl daemon-reload
sudo systemctl enable melesha-bot
sudo systemctl start melesha-bot

echo "✅ Бот запущен! Проверьте статус:"
echo "sudo systemctl status melesha-bot"
echo "sudo journalctl -u melesha-bot -f" 