import telebot
import sqlite3
import json
from datetime import datetime, timedelta
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Читаем токен и MASTER_ID из переменных окружения
TOKEN = os.getenv('BOT_TOKEN', '7613022017:AAHm6SgWoIz5Symu7D6mPQv1J6lYwELNY_E')
MASTER_ID = int(os.getenv('MASTER_ID', '1187382462'))
bot = telebot.TeleBot(TOKEN)

DB_PATH = 'appointments.db'
CHANNEL_ID = '@melesha_nails'  # Username канала

# --- DB ---
def db_connect():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    return conn, cursor

def create_tables():
    conn, cursor = db_connect()
    cursor.execute('''CREATE TABLE IF NOT EXISTS services (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        price INTEGER NOT NULL,
                        duration INTEGER NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS appointments (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        username TEXT,
                        service_id TEXT NOT NULL, -- Changed to TEXT to store multiple service IDs
                        appointment_datetime TEXT NOT NULL,
                        status TEXT NOT NULL)''')
    conn.commit()
    conn.close()

def import_services():
    if not os.path.exists('services.json'):
        return
    with open('services.json', 'r', encoding='utf-8') as f:
        services = json.load(f)
    conn, cursor = db_connect()
    for s in services:
        cursor.execute('SELECT 1 FROM services WHERE name=?', (s['name'],))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO services (name, price, duration) VALUES (?, ?, ?)', (s['name'], s['price'], s['duration']))
    conn.commit()
    conn.close()

def load_services():
    conn, cursor = db_connect()
    cursor.execute('SELECT * FROM services')
    services = cursor.fetchall()
    conn.close()
    return services

def recreate_appointments_table():
    conn, cursor = db_connect()
    cursor.execute('''DROP TABLE IF EXISTS appointments''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS appointments (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        username TEXT,
                        service_id TEXT NOT NULL,
                        appointment_datetime TEXT NOT NULL,
                        status TEXT NOT NULL)''')
    conn.commit()
    conn.close()

# --- Меню ---
def main_menu(user_id):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('📋 Услуги', '📅 Записаться')
    markup.add('❓ Вопрос мастеру')
    if user_id == MASTER_ID:
        markup.add('📖 История записей')
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, 'Привет! Я бот мастера маникюра 💅\nВыберите действие:', reply_markup=main_menu(message.from_user.id))

# --- Услуги ---
@bot.message_handler(func=lambda m: m.text == '📋 Услуги')
def show_services(message):
    services = load_services()
    text = '✨ Услуги:\n'
    for s in services:
        text += f"— {s[1]} — {s[2]}₽ ({s[3]} мин.)\n"
    bot.send_message(message.chat.id, text)

# --- Запись ---
user_booking_state = {}

@bot.message_handler(func=lambda m: m.text == '📅 Записаться')
def start_booking(message):
    user_id = message.from_user.id
    services = load_services()
    user_booking_state[user_id] = {'services': set()}
    markup = InlineKeyboardMarkup(row_width=2)
    for s in services:
        markup.add(InlineKeyboardButton(f'☑️ {s[1]}', callback_data=f'sel_service_{s[0]}'))
    markup.add(InlineKeyboardButton('Готово', callback_data='services_done'))
    bot.send_message(message.chat.id, 'Выберите одну или несколько услуг:', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sel_service_') or call.data == 'services_done')
def handle_service_selection(call):
    user_id = call.from_user.id
    services = load_services()
    if call.data.startswith('sel_service_'):
        service_id = int(call.data.split('_')[-1])
        state = user_booking_state.setdefault(user_id, {'services': set()})
        if service_id in state['services']:
            state['services'].remove(service_id)
        else:
            state['services'].add(service_id)
        # Обновить кнопки
        markup = InlineKeyboardMarkup(row_width=2)
        for s in services:
            checked = '✅' if s[0] in state['services'] else '☑️'
            markup.add(InlineKeyboardButton(f'{checked} {s[1]}', callback_data=f'sel_service_{s[0]}'))
        markup.add(InlineKeyboardButton('Готово', callback_data='services_done'))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        return
    # Если нажали "Готово"
    state = user_booking_state.get(user_id, {'services': set()})
    if not state['services']:
        bot.answer_callback_query(call.id, 'Выберите хотя бы одну услугу!')
        return
    # Переход к выбору даты
    service_ids = list(state['services'])
    user_booking_state[user_id]['service_ids'] = service_ids
    today = datetime.now().date()
    markup = InlineKeyboardMarkup(row_width=2)
    for i in range(7):
        d = today + timedelta(days=i)
        markup.add(InlineKeyboardButton(d.strftime('%d.%m.%Y'), callback_data=f"choose_date_multi_{'_'.join(map(str, service_ids))}_{d}"))
    bot.edit_message_text('Выберите дату:', call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('choose_date_multi_'))
def choose_time_multi(call):
    parts = call.data.split('_')
    service_ids = list(map(int, parts[3:-1]))
    date_str = parts[-1]
    user_id = call.from_user.id
    date = datetime.strptime(date_str, '%Y-%m-%d').date()
    conn, cursor = db_connect()
    # Суммарная длительность
    total_duration = 0
    for sid in service_ids:
        cursor.execute('SELECT duration FROM services WHERE id=?', (sid,))
        total_duration += cursor.fetchone()[0]
    slots = []
    start = datetime.combine(date, datetime.strptime('13:00', '%H:%M').time())
    end = datetime.combine(date, datetime.strptime('21:00', '%H:%M').time())
    while start + timedelta(minutes=total_duration) <= end:
        slots.append(start.time().strftime('%H:%M'))
        start += timedelta(minutes=60)
    cursor.execute('''SELECT appointment_datetime, service_id FROM appointments WHERE status = "confirmed"''')
    busy = []
    for row in cursor.fetchall():
        app_dt = datetime.strptime(row[0], '%Y-%m-%d %H:%M')
        app_service_ids = [int(x) for x in row[1].split(',')] if ',' in str(row[1]) else [int(row[1])]
        app_total_duration = 0
        for sid in app_service_ids:
            cursor.execute('SELECT duration FROM services WHERE id=?', (sid,))
            app_total_duration += cursor.fetchone()[0]
        app_end = app_dt + timedelta(minutes=app_total_duration)
        if app_dt.date() == date:
            busy.append((app_dt.time(), app_end.time()))
    free_slots = []
    for slot in slots:
        slot_start = datetime.combine(date, datetime.strptime(slot, '%H:%M').time())
        slot_end = slot_start + timedelta(minutes=total_duration)
        overlap = False
        for b_start, b_end in busy:
            b_start_dt = datetime.combine(date, b_start)
            b_end_dt = datetime.combine(date, b_end)
            if not (slot_end <= b_start_dt or slot_start >= b_end_dt):
                overlap = True
                break
        if not overlap:
            free_slots.append(slot)
    markup = InlineKeyboardMarkup(row_width=3)
    for slot in free_slots:
        markup.add(InlineKeyboardButton(slot, callback_data=f"confirm_booking_multi_{'_'.join(map(str, service_ids))}_{date}_{slot}"))
    if free_slots:
        bot.edit_message_text('Выберите время:', call.message.chat.id, call.message.message_id, reply_markup=markup)
    else:
        bot.edit_message_text('Нет свободных слотов на этот день.', call.message.chat.id, call.message.message_id)
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_booking_multi_'))
def confirm_booking_multi(call):
    parts = call.data.split('_')
    service_ids = list(map(int, parts[3:-2]))
    date_str = parts[-2]
    time_str = parts[-1]
    user_id = call.from_user.id
    username = call.from_user.username or ''
    dt = datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
    service_ids_str = ','.join(map(str, service_ids))
    conn, cursor = db_connect()
    cursor.execute('''INSERT INTO appointments (user_id, username, service_id, appointment_datetime, status) VALUES (?, ?, ?, ?, ?)''', (user_id, username, service_ids_str, dt.strftime('%Y-%m-%d %H:%M'), 'pending'))
    app_id = cursor.lastrowid
    # Получить имена услуг
    service_names = []
    for sid in service_ids:
        cursor.execute('SELECT name FROM services WHERE id=?', (sid,))
        service_names.append(cursor.fetchone()[0])
    conn.commit()
    conn.close()
    services_text = ', '.join(service_names)
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('✅ Подтвердить', callback_data=f'approve_{app_id}'),
        InlineKeyboardButton('❌ Отклонить', callback_data=f'reject_{app_id}')
    )
    bot.send_message(MASTER_ID, f'📢 Новая заявка от @{username or user_id}\nУслуги: {services_text}\nДата и время: {dt.strftime("%d.%m.%Y %H:%M")}', reply_markup=markup)
    bot.send_message(user_id, f'Ваша заявка отправлена мастеру. Ожидайте подтверждения!')

# --- Вопрос мастеру ---
@bot.message_handler(func=lambda m: m.text == '❓ Вопрос мастеру')
def ask_master(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add('❌ Отмена')
    bot.send_message(message.chat.id, 'Напишите ваш вопрос, мастер получит его лично. Для отмены нажмите ❌ Отмена.', reply_markup=markup)
    bot.register_next_step_handler(message, forward_question_to_master)

def forward_question_to_master(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, 'Ввод вопроса отменён.', reply_markup=main_menu(message.from_user.id))
        return
    menu_buttons = ['📋 Услуги', '📅 Записаться', '❓ Вопрос мастеру', '📖 История записей']
    if message.text in menu_buttons:
        bot.send_message(message.chat.id, 'Пожалуйста, введите ваш вопрос текстом, а не выбирайте кнопку.')
        bot.register_next_step_handler(message, forward_question_to_master)
        return
    bot.send_message(MASTER_ID, f'💬 Вопрос от @{message.from_user.username or message.from_user.id}:\n{message.text}')
    bot.send_message(message.chat.id, 'Ваш вопрос отправлен мастеру!', reply_markup=main_menu(message.from_user.id))

# --- Подтверждение/отклонение ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_'))
def approve_appointment(call):
    app_id = int(call.data.split('_')[1])
    conn, cursor = db_connect()
    cursor.execute('UPDATE appointments SET status="confirmed" WHERE id=?', (app_id,))
    cursor.execute('SELECT user_id, appointment_datetime, service_id FROM appointments WHERE id=?', (app_id,))
    user_id, dt, service_ids_str = cursor.fetchone()
    service_ids = [int(x) for x in service_ids_str.split(',')]
    service_names = []
    for sid in service_ids:
        cursor.execute('SELECT name FROM services WHERE id=?', (sid,))
        service_names.append(cursor.fetchone()[0])
    conn.commit()
    conn.close()
    services_text = ', '.join(service_names)
    bot.send_message(user_id, f'🎉 Ваша запись подтверждена мастером!\nУслуги: {services_text}\nДата и время: {dt}')
    bot.edit_message_text('Запись подтверждена.', call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def reject_appointment(call):
    app_id = int(call.data.split('_')[1])
    conn, cursor = db_connect()
    cursor.execute('UPDATE appointments SET status="rejected" WHERE id=?', (app_id,))
    cursor.execute('SELECT user_id FROM appointments WHERE id=?', (app_id,))
    user_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    bot.send_message(user_id, 'К сожалению, мастер отклонил вашу запись.')
    bot.edit_message_text('Запись отклонена.', call.message.chat.id, call.message.message_id)

# --- История записей для мастера ---
@bot.message_handler(func=lambda m: m.text == '📖 История записей' and m.from_user.id == MASTER_ID)
def show_history(message):
    conn, cursor = db_connect()
    cursor.execute('''SELECT a.appointment_datetime, a.service_id, a.username, a.user_id FROM appointments a ORDER BY a.appointment_datetime DESC''')
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        bot.send_message(message.chat.id, 'Нет записей.')
        return
    total_income = 0
    text = 'История записей:\n'
    for dt, service_ids_str, username, user_id in rows:
        service_ids = [int(x) for x in service_ids_str.split(',')]
        service_names = []
        sum_price = 0
        for sid in service_ids:
            cursor2 = sqlite3.connect(DB_PATH).cursor()
            cursor2.execute('SELECT name, price FROM services WHERE id=?', (sid,))
            res = cursor2.fetchone()
            if res:
                service_names.append(res[0])
                sum_price += res[1]
        user_display = f'@{username}' if username else f'user_id: {user_id}'
        text += f'{dt} | {", ".join(service_names)} | {sum_price}₽ | {user_display}\n'
        total_income += sum_price
    text += f'\nОбщий доход: {total_income}₽'
    bot.send_message(message.chat.id, text)

# --- Запуск ---
if __name__ == '__main__':
    create_tables()                # Сначала создать все таблицы
    recreate_appointments_table()  # Потом пересоздать appointments
    import_services()
    bot.polling(none_stop=True)


@bot.message_handler(commands=['post_signup_button'])
def post_signup_button(message):
    if message.from_user.id != MASTER_ID:
        bot.reply_to(message, 'Только мастер может отправлять кнопку в канал.')
        return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('💅 Записаться', url='https://t.me/MeleshaNailsBot'))
    try:
        bot.send_message(CHANNEL_ID, 'Хотите записаться на маникюр? Нажмите кнопку ниже!', reply_markup=markup)
        bot.reply_to(message, 'Сообщение отправлено в канал!')
    except Exception as e:
        bot.reply_to(message, f'Ошибка при отправке: {e}')