import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Ghost Mailer LIVE ✅\nUSA+EU+Asia, No Africa\n\n/freeleads - 30 leads\n/status")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot LIVE ✅")

def main():
    print(f"Starting bot, token set: {bool(TOKEN)}")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("freeleads", start))
    app.add_handler(CommandHandler("leads", start))
    app.run_polling()

if __name__ == "__main__":
    main()
