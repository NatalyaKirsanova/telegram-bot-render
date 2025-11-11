import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import time

BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌤️ Привет! Я бот для прогноза погоды!\n\n"
        "Просто напишите название города и я покажу погоду.\n"
        "Например: Москва, London, Paris"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Просто напишите название города на русском или английском"
    )

def format_time(time_str):
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        return dt.strftime("%H:%M")
    except:
        return time_str

async def handle_city_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    
    if not WEATHER_API_KEY:
        await update.message.reply_text("❌ Сервис погоды временно недоступен")
        return
    
    try:
        # Получаем текущую погоду
        current_url = "http://api.weatherapi.com/v1/current.json"
        current_params = {
            'key': WEATHER_API_KEY,
            'q': city,
            'lang': 'ru'
        }
        
        # Получаем астрономические данные
        astronomy_url = "http://api.weatherapi.com/v1/astronomy.json"
        astronomy_params = {
            'key': WEATHER_API_KEY,
            'q': city,
            'dt': 'today'
        }
        
        current_response = requests.get(current_url, params=current_params, timeout=10)
        astronomy_response = requests.get(astronomy_url, params=astronomy_params, timeout=10)
        
        current_data = current_response.json()
        astronomy_data = astronomy_response.json()
        
        if 'error' in current_data:
            error_message = current_data['error']['message']
            await update.message.reply_text(f"❌ {error_message}")
            return
        
        # Парсим данные
        location = current_data['location']
        current = current_data['current']
        astronomy = astronomy_data['astronomy']['astro']
        
        weather_text = (
            f"🌍 {location['name']}, {location['country']}\n"
            f"🌡️ Температура: {current['temp_c']}°C\n"
            f"💭 Ощущается как: {current['feelslike_c']}°C\n"
            f"📝 {current['condition']['text']}\n"
            f"💧 Влажность: {current['humidity']}%\n"
            f"🌬️ Ветер: {current['wind_kph']} км/ч\n"
            f"📊 Давление: {current['pressure_mb']} гПа\n"
            f"🌫️ Видимость: {current['vis_km']} км\n"
            f"🌅 Восход: {format_time(astronomy['sunrise'])}\n"
            f"🌇 Закат: {format_time(astronomy['sunset'])}"
        )
        
        await update.message.reply_text(weather_text)
            
    except Exception as e:
        await update.message.reply_text("❌ Ошибка при получении погоды. Попробуйте другой город.")

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        return
    
    print("🔄 Запуск бота...")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_city_message))
    
    # Очищаем предыдущие обновления
    try:
        application.bot.delete_webhook(drop_pending_updates=True)
        print("✅ Предыдущие обновления очищены")
    except Exception as e:
        print(f"⚠️ Не удалось очистить обновления: {e}")
    
    print("🌤️ Бот погоды запускается...")
    
    # Запускаем с обработкой ошибок
    try:
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            poll_interval=3.0,  # Увеличиваем интервал
            timeout=30
        )
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("🔄 Перезапуск через 30 секунд...")
        time.sleep(30)
        main()

if __name__ == '__main__':
    main()
