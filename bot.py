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

def get_wave_height_description(wave_height_m):
    """Получить описание высоты волн"""
    if wave_height_m < 0.3:
        return "🟢 Спокойное море"
    elif wave_height_m < 0.6:
        return "🟡 Легкое волнение"
    elif wave_height_m < 1.2:
        return "🟠 Умеренное волнение"
    elif wave_height_m < 2.5:
        return "🟣 Сильное волнение"
    else:
        return "🔴 Очень сильное волнение"

def should_show_marine_data(marine_data, city_name):
    """Определяет, нужно ли показывать данные о волнах"""
    try:
        # Для отладки выведем что приходит
        print(f"Marine data for {city_name}: {marine_data}")
        
        if 'error' in marine_data:
            print(f"Marine API error: {marine_data['error']}")
            return False
            
        if 'forecast' not in marine_data:
            print("No forecast in marine data")
            return False
            
        marine_forecast = marine_data['forecast']['forecastday'][0]
        if 'hour' not in marine_forecast or len(marine_forecast['hour']) == 0:
            print("No hour data in marine forecast")
            return False
        
        current_hour = marine_forecast['hour'][0]
        wave_height = current_hour.get('sig_ht_mt', 0)
        wave_period = current_hour.get('swell_period_secs', 0)
        wave_direction = current_hour.get('swell_direction_deg', 0)
        
        print(f"Wave data - height: {wave_height}m, period: {wave_period}s, direction: {wave_direction}°")
        
        # ОЧЕНЬ ПРОСТАЯ ПРОВЕРКА: только для Москвы не показываем
        inland_cities = ['москва', 'moscow']
        
        if city_name.lower() in inland_cities:
            print(f"{city_name} is inland city - skipping marine data")
            return False
            
        # Для всех остальных городов показываем волны если есть какие-то данные
        # (даже если они маленькие - возможно это реальные данные для спокойного моря)
        has_wave_data = wave_height > 0 or wave_period > 0
        
        print(f"Should show marine data for {city_name}: {has_wave_data}")
        return has_wave_data
        
    except Exception as e:
        print(f"Error in should_show_marine_data: {e}")
        return False

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
            'dt': 'today'
        }
        
        # Делаем основные запросы
        current_response = requests.get(current_url, params=current_params, timeout=10)
        astronomy_response = requests.get(astronomy_url, params=astronomy_params, timeout=10)
        
        current_data = current_response.json()
        astronomy_data = astronomy_response.json()
        
        if 'error' in current_data:
            error_message = current_data['error']['message']
            await update.message.reply_text(f"❌ {error_message}")
            return
        
        if 'error' in astronomy_data:
            error_message = astronomy_data['error']['message']
            await update.message.reply_text(f"❌ {error_message}")
            return
        
        # Парсим данные о текущей погоде
        location = current_data['location']
        current = current_data['current']
        
        # Парсим астрономические данные
        astronomy = astronomy_data['astronomy']['astro']
        
        # Формируем базовый текст с погодой
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
        
        # Пытаемся получить marine данные
        try:
            marine_url = "http://api.weatherapi.com/v1/marine.json"
            marine_params = {
                'key': WEATHER_API_KEY,
                'q': city,
                'days': 1
            }
            
            print(f"Requesting marine data for: {city}")
            marine_response = requests.get(marine_url, params=marine_params, timeout=5)
            marine_data = marine_response.json()
            
            # Проверяем, нужно ли показывать данные о волнах
            if should_show_marine_data(marine_data, city):
                marine_forecast = marine_data['forecast']['forecastday'][0]
                current_hour_data = marine_forecast['hour'][0]
                wave_height_m = current_hour_data.get('sig_ht_mt', 0)
                wave_period = current_hour_data.get('swell_period_secs', 0)
                wave_direction = current_hour_data.get('swell_direction_deg', 0)
                
                wave_info = (
                    f"\n\n🌊 **Морские условия:**\n"
                    f"📏 Высота волн: {wave_height_m:.1f} м\n"
                    f"⏱️ Период волн: {wave_period:.1f} сек\n"
                    f"🧭 Направление: {wave_direction}°\n"
                    f"📋 {get_wave_height_description(wave_height_m)}"
                )
                weather_text += wave_info
            else:
                print(f"Not showing marine data for {city}")
            
        except requests.exceptions.Timeout:
            print(f"Marine API timeout for {city}")
        except Exception as e:
            print(f"Marine API error for {city}: {e}")
        
        await update.message.reply_text(weather_text)
            
    except requests.exceptions.Timeout:
        await update.message.reply_text("❌ Превышено время ожидания ответа от сервера погоды")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text("❌ Ошибка соединения с сервером погоды")
    except Exception as e:
        print(f"Ошибка: {e}")  # Для отладки
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
