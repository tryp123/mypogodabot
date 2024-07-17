import telebot
from telebot import types
import config
import requests
from bs4 import BeautifulSoup as BS
import schedule
import time
import threading
import json
import os

bot = telebot.TeleBot(config.token)

# Збереження даних користувачів у файлі
data_file = 'user_data.json'
user_city = {}
user_timers = {}

# Завантаження даних користувачів з файлу
if os.path.exists(data_file):
    with open(data_file, 'r') as f:
        data = json.load(f)
        user_city = data.get('user_city', {})
        user_timers = data.get('user_timers', {})

# Збереження даних користувачів у файлі
def save_user_data():
    with open(data_file, 'w') as f:
        json.dump({'user_city': user_city, 'user_timers': user_timers}, f)

# Функція для парсингу погоди
def get_weather(city, days=1):
    url = f'https://ua.sinoptik.ua/погода-{city}'
    try:
        r = requests.get(url)
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        return None
    
    html = BS(r.content, 'html.parser')
    weather_data = []

    for day_id in range(1, days + 1):
        day_block = html.select_one(f'#bd{day_id}')
        if not day_block:
            continue
        
        day_info = {}
        day_info['day'] = day_block.select_one('.day-link').text
        day_info['date'] = day_block.select_one('.date').text
        day_info['month'] = day_block.select_one('.month').text
        day_info['min_temp'] = day_block.select_one('.temperature .min span').text
        day_info['max_temp'] = day_block.select_one('.temperature .max span').text
        day_info['weather_class'] = day_block.select_one('.weatherIco')['class'][1]
        day_info['img_url'] = 'https:' + day_block.select_one('.weatherImg')['src']
        weather_data.append(day_info)
    
    return weather_data

# Функція для парсингу детальної погоди
def get_detailed_weather(city):
    url = f'https://ua.sinoptik.ua/погода-{city}'
    try:
        r = requests.get(url)
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        return None

    html = BS(r.content, 'html.parser')
    weather_table = html.select_one('.weatherDetails')

    if not weather_table:
        return None

    rows = weather_table.find_all('tr')
    time_row = rows[1].find_all('td')
    temp_row = rows[3].find_all('td')
    wind_row = rows[7].find_all('td')
    rain_probability_row = rows[8].find_all('td')

    detailed_data = {
        'time': [cell.get_text(strip=True) for cell in time_row],
        'temperature': [cell.get_text(strip=True) for cell in temp_row],
        'wind': [cell.select_one('div').get_text(strip=True) if cell.select_one('div') else '' for cell in wind_row],
        'rain_probability': [cell.get_text(strip=True) for cell in rain_probability_row]
    }

    return detailed_data

# Функція для відправки погоди за день
def send_daily_weather(chat_id, weather_info, detailed_info):
    weather_message = f"👋 Погода на {weather_info['day']} {weather_info['date']} {weather_info['month']}\n"
    weather_message += f"📉 Мін.: {weather_info['min_temp']}\n📈 Макс.: {weather_info['max_temp']}\n"

    bot.send_message(chat_id, weather_message)
    
    img_url = weather_info['img_url']
    weather_class = weather_info['weather_class']
    
    if weather_class == 'd000':
        bot.send_photo(chat_id, img_url, caption="Ясно")
    elif weather_class == 'd100':
        bot.send_photo(chat_id, img_url, caption="Невелика хмарність")
    elif weather_class == 'd200':
        bot.send_photo(chat_id, 'path/to/d200.gif', caption="Мінлива хмарність")
    elif weather_class == 'd210':
        bot.send_photo(chat_id, 'path/to/d210.gif', caption="Мінлива хмарність, невеликий дощ")
    elif weather_class == 'd240':
        bot.send_photo(chat_id, img_url, caption="Мінлива хмарність, дощ, можливі грози")
    elif weather_class == 'd300':
        bot.send_photo(chat_id, 'path/to/d300.gif', caption="Хмарно з проясненнями")
    else:
        bot.send_message(chat_id, 'Нажаль, фото не має в базі. Очікуйте оновлень бота. 🫡')

    if detailed_info:
        detailed_message = "📅 Детальна погода:\n"
        detailed_message += "```\n"
        detailed_message += f"{'Час':<10} {'Температура°':<12} {'Вітер(м/с)':<12} {'Ймовірність опадів(%)':<18}\n"
        for i in range(len(detailed_info['time'])):
            detailed_message += f"{detailed_info['time'][i]:<10} {detailed_info['temperature'][i]:<12} {detailed_info['wind'][i]:<12} {detailed_info['rain_probability'][i]:<18}\n"
        detailed_message += "```"

        bot.send_message(chat_id, detailed_message, parse_mode='MarkdownV2')

# Функція для створення кнопок
def create_buttons():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(types.KeyboardButton("/help"), types.KeyboardButton("/start"))
    return markup

# Обробник команди старт
@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "👋Привіт! Введіть назву вашого населеного пункту:", reply_markup=create_buttons())

# Обробник команди /help
@bot.message_handler(commands=['help'])
def help_message(message):
    bot.send_message(message.chat.id, "☂️Це бот для отримання інформації про погоду. Введіть назву вашого населеного пункту, щоб дізнатися погоду.👍")

# Обробник введення населеного пункту
@bot.message_handler(content_types=['text'])
def get_city_weather(message):
    city = message.text.strip().lower().replace(' ', '-')
    user_city[message.chat.id] = city

    weather_data = get_weather(city)
    if not weather_data:
        bot.send_message(message.chat.id, "🥲Не вдалося отримати дані про погоду. Перевірте правильність введеного населеного пункту.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🌞Погода сьогодні", callback_data="weather_today"))
    markup.add(types.InlineKeyboardButton("❄️Погода на тиждень", callback_data="weather_week"))
    markup.add(types.InlineKeyboardButton("📨Розсилка", callback_data="set_timer"))
    markup.add(types.InlineKeyboardButton("🔕Вимкнути розсилку", callback_data="cancel_timer"))
    bot.send_message(message.chat.id, f"🙂Населений пункт: {city}. 🫱Виберіть опцію:", reply_markup=markup)

# Обробник кнопок
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        city = user_city.get(call.message.chat.id, None)
        if not city:
            bot.send_message(call.message.chat.id, "🥲Не вдалося знайти місто. Спробуйте ще раз.")
            return

        if call.data == "weather_today":
            weather_data = get_weather(city)
            if weather_data:
                detailed_info = get_detailed_weather(city)
                send_daily_weather(call.message.chat.id, weather_data[0], detailed_info)
            else:
                bot.send_message(call.message.chat.id, "🥲Не вдалося отримати дані про погоду.")
        elif call.data == "weather_week":
            weather_data = get_weather(city, days=7)
            if weather_data:
                for day_weather in weather_data:
                    send_daily_weather(call.message.chat.id, day_weather, None)
                    bot.send_message(call.message.chat.id, "(^._.^)ﾉ")
            else:
                bot.send_message(call.message.chat.id, "🥲Не вдалося отримати дані про погоду.")
        elif call.data == "set_timer":
            if call.message.chat.id in user_timers:
                bot.send_message(call.message.chat.id, "🥲У вас вже є активна розсилка. Спочатку відмініть її.")
                return
            markup = types.InlineKeyboardMarkup(row_width=4)
            for hour in range(24):
                markup.add(types.InlineKeyboardButton(f"{hour:02d}:00", callback_data=f"timer_{hour:02d}:00"))
            markup.add(types.InlineKeyboardButton("🚪Повернутися назад", callback_data="back_to_main"))
            bot.send_message(call.message.chat.id, "⌚Виберіть час для щоденної розсилки:", reply_markup=markup)
        elif call.data == "back_to_main":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("🌞Погода сьогодні", callback_data="weather_today"))
            markup.add(types.InlineKeyboardButton("❄️Погода на тиждень", callback_data="weather_week"))
            markup.add(types.InlineKeyboardButton("📨Розсилка", callback_data="set_timer"))
            markup.add(types.InlineKeyboardButton("🔕Вимкнути розсилку", callback_data="cancel_timer"))
            bot.send_message(call.message.chat.id, "🚪Повернулися до головного меню:", reply_markup=markup)
        elif call.data.startswith("timer_"):
            time_str = call.data.split("_")[1]
            user_timers[call.message.chat.id] = time_str
            save_user_data()
            schedule_daily_weather(call.message.chat.id, time_str)
            bot.send_message(call.message.chat.id, f"📩Щоденну розсилку налаштовано на {time_str}.")
        elif call.data == "cancel_timer":
            if call.message.chat.id in user_timers:
                del user_timers[call.message.chat.id]
                save_user_data()
                bot.send_message(call.message.chat.id, "🫡Щоденну розсилку вимкнено.")
            else:
                bot.send_message(call.message.chat.id, "🥲Розсилка не була налаштована.")

# Функція для щоденної розсилки погоди
def schedule_daily_weather(chat_id, time_str):
    def job():
        city = user_city.get(chat_id, None)
        if city:
            weather_data = get_weather(city)
            if weather_data:
                detailed_info = get_detailed_weather(city)
                send_daily_weather(chat_id, weather_data[0], detailed_info)

    schedule.every().day.at(time_str).do(job)

# Функція для запуску шедулера у окремому потоці
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Запуск шедулера у окремому потоці
scheduler_thread = threading.Thread(target=run_scheduler)
scheduler_thread.start()

# Запуск бота
bot.polling(none_stop=True)
