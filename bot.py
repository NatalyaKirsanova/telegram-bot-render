import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


async def test_ozon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестирование Ozon API с правильными endpoints"""
    await update.message.reply_text("🔍 Запускаю тест Ozon API с правильными endpoints...")
    
    OZON_API_KEY = os.environ.get('OZON_API_KEY')
    OZON_CLIENT_ID = os.environ.get('OZON_CLIENT_ID')
    
    if not OZON_API_KEY or not OZON_CLIENT_ID:
        await update.message.reply_text("❌ Ключи не найдены!")
        return
    
    headers = {
        "Client-Id": OZON_CLIENT_ID,
        "Api-Key": OZON_API_KEY,
        "Content-Type": "application/json"
    }
    
    results = []
    
    # ТЕСТ 1: Список товаров (v3) - ПРОВЕРЕННЫЙ ENDPOINT
    try:
        response = requests.post(
            "https://api-seller.ozon.ru/v3/product/list",
            headers=headers,
            json={
                "filter": {
                    "visibility": "ALL"
                },
                "limit": 10,
                "sort_dir": "ASC"
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            count = len(data.get('result', {}).get('items', []))
            results.append(f"✅ Товары (v3): {count} шт.")
        else:
            error_msg = response.text[:100] if response.text else "нет деталей"
            results.append(f"❌ Товары (v3): {response.status_code} - {error_msg}")
    except Exception as e:
        results.append(f"❌ Товары (v3): {str(e)}")
    
    # ТЕСТ 2: FBS заказы (v3) - ПРАВИЛЬНЫЙ PAYLOAD
    try:
        from datetime import datetime, timedelta
        date_to = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        response = requests.post(
            "https://api-seller.ozon.ru/v3/posting/fbs/list",
            headers=headers,
            json={
                "filter": {
                    "since": date_from,
                    "to": date_to,
                    "status": ""
                },
                "limit": 10,
                "sort_by": "created_at",
                "sort_dir": "ASC"
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            count = len(data.get('result', {}).get('postings', []))
            results.append(f"✅ FBS заказы (v3): {count} шт.")
        else:
            error_msg = response.text[:100] if response.text else "нет деталей"
            results.append(f"❌ FBS заказы (v3): {response.status_code} - {error_msg}")
    except Exception as e:
        results.append(f"❌ FBS заказы (v3): {str(e)}")
    
    # ТЕСТ 3: Категории (v1) - ПРОСТОЙ ENDPOINT
    try:
        response = requests.post(
            "https://api-seller.ozon.ru/v1/category/tree",
            headers=headers,
            json={},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            results.append(f"✅ Категории (v1)")
        else:
            error_msg = response.text[:100] if response.text else "нет деталей"
            results.append(f"❌ Категории (v1): {response.status_code} - {error_msg}")
    except Exception as e:
        results.append(f"❌ Категории (v1): {str(e)}")
    
    # Отправляем результаты
    result_text = "📊 *Результаты теста Ozon API:*\n\n" + "\n".join(results)
    await update.message.reply_text(result_text, parse_mode='Markdown')










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

async def handle_city_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений с названием города"""
    city = update.message.text.strip()
    
    if not WEATHER_API_KEY:
        await update.message.reply_text("❌ Сервис погоды временно недоступен")
        return
    
    try:
        # WeatherAPI.com - более надежный сервис
        url = "http://api.weatherapi.com/v1/current.json"
        params = {
            'key': WEATHER_API_KEY,
            'q': city,
            'lang': 'ru'
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'error' not in data:
            # Парсим данные о погоде
            location = data['location']
            current = data['current']
            
            weather_text = (
                f"🌍 {location['name']}, {location['country']}\n"
                f"🌡️ Температура: {current['temp_c']}°C\n"
                f"💭 Ощущается как: {current['feelslike_c']}°C\n"
                f"📝 {current['condition']['text']}\n"
                f"💧 Влажность: {current['humidity']}%\n"
                f"🌬️ Ветер: {current['wind_kph']} км/ч\n"
                f"📊 Давление: {current['pressure_mb']} гПа\n"
                f"🌫️ Видимость: {current['vis_km']} км"
            )
            
            await update.message.reply_text(weather_text)
            
        else:
            error_message = data['error']['message']
            await update.message.reply_text(f"❌ {error_message}")
            
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
    application.add_handler(CommandHandler("testozon", test_ozon))
    print("🌤️ Бот погоды запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
