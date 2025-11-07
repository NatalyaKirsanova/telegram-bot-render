import os
from telegram.ext import Application, CommandHandler

BOT_TOKEN = os.environ.get('BOT_TOKEN')

async def start(update, context):
    await update.message.reply_text("🎉 Бот создан прямо в GitHub!")

async def help(update, context):
    await update.message.reply_text("Помощь: /start, /help")


async def time(update, context):
    from datetime import datetime
    current_time = datetime.now().strftime("%H:%:%S")
    await update.message.reply_text(f"🕐 Текущее время: {current_time}")

if __name__ == '__main__':
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("time", time))
    print("🚀 Бот запускается...")
    app.run_polling()
