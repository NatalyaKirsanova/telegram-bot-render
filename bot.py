import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Токены из переменных окружения Render
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')  # Добавьте этот ключ в Render

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "🌤️ Привет! Я бот для прогноза погоды!\n\n"
        "Просто напишите название города и я покажу погоду.\n"
        "Например: Москва, London, Paris\n\n"
        "Команды:\n"
        "/start - начать работу\n"
        "/help - помощь\n"
        "/weather - узнать погоду"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await update.message.reply_text(
        "📋 Как пользоваться ботом:\n\n"
        "1. Напишите название города на русском или английском\n"
        "2. Или используйте команду /weather Москва\n"
        "3. Бот покажет текущую погоду и прогноз\n\n"
        "Примеры:\n"
        "• Москва\n"
        "• London\n"
        "• /weather Paris"
    )

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /weather [город]"""
    if not context.args:
        await update.message.reply_text("⚠️ Укажите город: /weather Москва")
        return
    
    city = ' '.join(context.args)
    await get_weather(update, city)

async def handle_city_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений с названием города"""
    city = update.message.text
    await get_weather(update, city)

async def get_weather(update: Update, city: str):
    """Получение погоды по API"""
    if not WEATHER_API_KEY:
        await update.message.reply_text("❌ Сервис погоды временно недоступен")
        return
    
    try:
        # Запрос к OpenWeatherMap API
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': city,
            'appid': WEATHER_API_KEY,
            'units': 'metric',  # градусы Цельсия
            'lang': 'ru'
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if response.status_code == 200:
            # Парсим данные о погоде
            temperature = data['main']['temp']
            feels_like = data['main']['feels_like']
            humidity = data['main']['humidity']
            pressure = data['main']['pressure']
            description = data['weather'][0]['description']
            wind_speed = data['wind']['speed']
            city_name = data['name']
            country = data['sys']['country']
            
            # Формируем ответ
            weather_text = (
                f"🌍 {city_name}, {country}\n"
                f"🌡️ Температура: {temperature}°C\n"
                f"💭 Ощущается как: {feels_like}°C\n"
                f"📝 {description.capitalize()}\n"
                f"💧 Влажность: {humidity}%\n"
                f"🌬️ Ветер: {wind_speed} м/с\n"
                f"📊 Давление: {pressure} гПа"
            )
            
            await update.message.reply_text(weather_text)
            
        else:
            await update.message.reply_text(f"❌ Город '{city}' не найден. Попробуйте другой город.")
            
    except Exception as e:
        await update.message.reply_text("❌ Ошибка при получении погоды. Попробуйте позже.")

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
    application.add_handler(CommandHandler("weather", weather_command))
    
    # Обработчик текстовых сообщений (названия городов)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_city_message))
    
    print("🌤️ Бот погоды запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
