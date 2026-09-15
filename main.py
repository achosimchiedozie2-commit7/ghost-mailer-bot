import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
PORT = int(os.getenv("PORT", 10000))

# Fake web server so Render doesn't kill it
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Ghost Mailer Bot is LIVE")

def run_web():
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"Web server on {PORT}")
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Ghost Mailer LIVE ✅\nUSA+EU+Asia, No Africa\n\n/freeleads - 30 leads\n/status - check bot")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is LIVE and running ✅")

def main():
    print(f"Starting... Token OK: {bool(TOKEN)} Port: {PORT}")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("freeleads", start))
    app.add_handler(CommandHandler("leads", start))
    app.run_polling()

if __name__ == "__main__":
    main()
