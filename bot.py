import os
from telegram.ext import Application, CommandHandler

BOT_TOKEN = os.environ.get('BOT_TOKEN')

async def start(update, context):
    await update.message.reply_text("✅ Бот работает!")

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.run_polling()
