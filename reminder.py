import sqlite3
import telebot
from datetime import datetime, timedelta

TOKEN = '7613022017:AAHm6SgWoIz5Symu7D6mPQv1J6lYwELNY_E'
MASTER_ID = 1187382462
bot = telebot.TeleBot(TOKEN)

def send_reminders():
    conn = sqlite3.connect('appointments.db')
    cursor = conn.cursor()
    now = datetime.now()
    # 24 часа и 2 часа до записи
    for hours in [24, 2]:
        remind_time = now + timedelta(hours=hours)
        cursor.execute('''SELECT a.id, a.user_id, a.appointment_datetime, s.name, a.status
                          FROM appointments a
                          JOIN services s ON a.service_id = s.id
                          WHERE a.status = 'confirmed' ''')
        for row in cursor.fetchall():
            app_id, user_id, dt_str, service_name, status = row
            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
            if abs((dt - remind_time).total_seconds()) < 60:  # 1 минута точности
                # Проверяем, не отправляли ли уже уведомление
                cursor.execute('''SELECT 1 FROM notifications WHERE appointment_id=? AND type=?''', (app_id, f'{hours}h'))
                if not cursor.fetchone():
                    # Отправляем напоминание клиенту
                    bot.send_message(user_id, f'⏰ Напоминание! Ваша запись на {service_name} через {hours} часа(ов): {dt.strftime("%d.%m.%Y %H:%M")}')
                    # Мастеру только за 24 часа
                    if hours == 24:
                        bot.send_message(MASTER_ID, f'⏰ Напоминание! Запись клиента на {service_name} через 24 часа: {dt.strftime("%d.%m.%Y %H:%M")}')
                    cursor.execute('''INSERT INTO notifications (appointment_id, type, sent_at) VALUES (?, ?, ?)''', (app_id, f'{hours}h', now.strftime('%Y-%m-%d %H:%M')))
    conn.commit()
    conn.close() 