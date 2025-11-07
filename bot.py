import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime
import random
import pytz  # для работы с часовыми поясами

BOT_TOKEN = os.environ.get('BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.message.from_user
    await update.message.reply_text(
        f"🎉 Привет {user.first_name}!\n"
        "Я ваш телеграм бот!\n"
        "Доступные команды:\n"
        "/start - начать работу\n"
        "/help - помощь\n" 
        "/hello - приветствие\n"
        "/time - текущее время (Москва)\n"
        "/random - случайное число\n"
        "/info - информация о вас"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(
        "📋 Помощь по командам:\n"
        "/start - начать работу\n"
        "/help - помощь\n"
        "/hello - приветствие\n"
        "/time - текущее время (Москва)\n"
        "/random - случайное число\n"
        "/info - информация о вас"
    )

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /hello"""
    await update.message.reply_text(f"👋 Привет, {update.message.from_user.first_name}!")

async def time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущее время МОСКВЫ"""
    # Устанавливаем московский часовой пояс
    moscow_tz = pytz.timezone('Europe/Moscow')
    moscow_time = datetime.now(moscow_tz)
    
    current_time = moscow_time.strftime("%H:%M:%S")
    current_date = moscow_time.strftime("%d.%m.%Y")
    current_day = moscow_time.strftime("%A")
    
    # Перевод дня недели на русский
    days = {
        'Monday': 'Понедельник',
        'Tuesday': 'Вторник', 
        'Wednesday': 'Среда',
        'Thursday': 'Четверг',
        'Friday': 'Пятница',
        'Saturday': 'Суббота',
        'Sunday': 'Воскресенье'
    }
    
    await update.message.reply_text(
        f"🕐 Московское время:\n"
        f"📅 {current_date} ({days[current_day]})\n"
        f"⏰ {current_time}"
    )

async def random_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует случайное число"""
    number = random.randint(1, 100)
    await update.message.reply_text(f"🎲 Случайное число: {number}")

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о пользователе"""
    user = update.message.from_user
    await update.message.reply_text(
        f"👤 Информация о вас:\n"
        f"Имя: {user.first_name}\n"
        f"Фамилия: {user.last_name or 'не указана'}\n"
        f"Username: @{user.username or 'не указан'}\n"
        f"ID: {user.id}"
    )

def main():
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не установлен!")
        return
    
    print("🚀 Запуск бота на Render...")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("hello", hello))
    application.add_handler(CommandHandler("time", time))
    application.add_handler(CommandHandler("random", random_number))
    application.add_handler(CommandHandler("info", user_info))
    
    print("✅ Бот запущен и готов к работе!")
    print("🤖 Отправьте /start вашему боту в Telegram")
    
    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()
