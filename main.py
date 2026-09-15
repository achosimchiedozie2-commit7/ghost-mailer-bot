import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- Config ----------
TOKEN = os.getenv("TELEGRAM_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    logger.error("TELEGRAM_TOKEN environment variable is missing!")
    raise SystemExit("TELEGRAM_TOKEN is required")

# ---------- Simple Health Server (must bind early) ----------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Ghost Mailer Bot is LIVE")

    def log_message(self, format, *args):
        # silence the default HTTP access logs
        return

def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"Health server listening on 0.0.0.0:{PORT}")
    server.serve_forever()

# ---------- Bot Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ghost Mailer LIVE ✅")

def main():
    # Start health server FIRST (critical for Render port detection)
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    # Give the server a moment to bind
    import time
    time.sleep(1)

    # Build the bot
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    logger.info("Starting Telegram bot polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
