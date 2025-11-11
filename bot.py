import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

# Токены из переменных окружения Render
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "🌤️ Привет! Я бот для прогноза погоды!\n\n"
        "Просто напишите название города и я покажу погоду.\n"
        "Например: Москва, London, Paris\n\n"
        "Команды:\n"
        "/start - начать работу\n"
        "/help - помощь"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await update.message.reply_text(
        "📋 Как пользоваться ботом:\n\n"
        "Напишите название города на русском или английском\n\n"
        "Примеры:\n"
        "• Москва\n"
        "• Лондон\n"
        "• Berlin\n"
        "• Париж"
    )

def format_time(time_str):
    """Форматирование времени из формата API в читаемый вид"""
    try:
        # Преобразуем время из формата "2024-01-15 07:45" в "07:45"
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        return dt.strftime("%H:%M")
    except:
        return time_str

async def handle_city_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений с названием города"""
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
        
        # Получаем астрономические данные (восход, закат)
        astronomy_url = "http://api.weatherapi.com/v1/astronomy.json"
        astronomy_params = {
            'key': WEATHER_API_KEY,
            'q': city,
            'dt': 'today'  # данные на сегодня
        }
        
        # Делаем запросы параллельно
        current_response = requests.get(current_url, params=current_params, timeout=10)
        astronomy_response = requests.get(astronomy_url, params=astronomy_params, timeout=10)
        
        current_data = current_response.json()
        astronomy_data = astronomy_response.json()
        
        if 'error' not in current_data and 'error' not in astronomy_data:
            # Парсим данные о текущей погоде
            location = current_data['location']
            current = current_data['current']
            
            # Парсим астрономические данные
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
            
        else:
            error_message = current_data.get('error', astronomy_data.get('error', {})).get('message', 'Неизвестная ошибка')
            await update.message.reply_text(f"❌ {error_message}")
            
    except requests.exceptions.Timeout:
        await update.message.reply_text("❌ Превышено время ожидания ответа от сервера погоды")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text("❌ Ошибка соединения с сервером погоды")
    except Exception as e:
        await update.message.reply_text("❌ Ошибка при получении погоды. Попробуйте другой город или позже.")

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        return
    
    if not WEATHER_API_KEY:
        print("⚠️ WEATHER_API_KEY не найден. Бот будет работать без погоды.")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Обработчик текстовых сообщений (названия городов)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_city_message))
    
    print("🌤️ Бот погоды запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
