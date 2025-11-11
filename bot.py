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

def has_real_marine_data(marine_data, city_name):
    """Проверяет, содержит ли marine_data реальные значения"""
    try:
        if 'error' in marine_data or 'forecast' not in marine_data:
            return False
            
        marine_forecast = marine_data['forecast']['forecastday'][0]
        if 'hour' not in marine_forecast or len(marine_forecast['hour']) == 0:
            return False
        
        # Список известных материковых городов, для которых НЕ показывать волны
        inland_cities = [
            'москва', 'moscow', 'киев', 'kyiv', 'минск', 'minsk', 
            'прага', 'prague', 'берлин', 'berlin', 'варшава', 'warsaw',
            'мадрид', 'madrid', 'париж', 'paris', 'рим', 'rome'
        ]
        
        if city_name.lower() in inland_cities:
            return False
            
        # Проверяем данные более строго
        current_hour = marine_forecast['hour'][0]
        wave_height = current_hour.get('sig_ht_mt', 0)
        wave_period = current_hour.get('swell_period_secs', 0)
        wave_direction = current_hour.get('swell_direction_deg', 0)
        
        # Критерии реальных морских данных:
        # 1. Высота волн должна быть реалистичной (обычно от 0.3м для спокойного моря)
        # 2. Период волн должен быть > 2 секунд (реальные волны имеют больший период)
        # 3. Направление не должно быть 0 градусов
        is_real_wave_height = 0.3 <= wave_height <= 10.0  # Реальные значения высоты волн
        is_real_period = wave_period >= 2.0  # Реальный период волн
        is_real_direction = wave_direction != 0  # Настоящее направление
        
        # Дополнительная проверка: смотрим на изменение данных в течение дня
        wave_heights = [hour.get('sig_ht_mt', 0) for hour in marine_forecast['hour'][:12]]
        wave_periods = [hour.get('swell_period_secs', 0) for hour in marine_forecast['hour'][:12]]
        
        # Если все значения одинаковые и очень маленькие - вероятно, это данные по умолчанию
        all_same_height = len(set(round(h, 1) for h in wave_heights)) == 1
        all_same_period = len(set(round(p, 1) for p in wave_periods)) == 1
        
        if all_same_height and all_same_period and wave_height < 0.3:
            return False
        
        return is_real_wave_height and is_real_period and is_real_direction
        
    except Exception:
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
        
        # Пытаемся получить marine данные, но показываем только если они реальные
        try:
            marine_url = "http://api.weatherapi.com/v1/marine.json"
            marine_params = {
                'key': WEATHER_API_KEY,
                'q': city,
                'days': 1
            }
            
            marine_response = requests.get(marine_url, params=marine_params, timeout=5)
            marine_data = marine_response.json()
            
            # Проверяем, есть ли реальные морские данные
            if has_real_marine_data(marine_data, city):
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
            # Если данные нереальные - просто не показываем их
            
        except requests.exceptions.Timeout:
            # Игнорируем таймаут для морских данных
            pass
        except Exception as e:
            # Игнорируем ошибки получения морских данных
            pass
        
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
