import os
import logging
import threading
import asyncio
import re
import time
import csv
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup
from googlesearch import search
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, ContextTypes

# -------------------- LOGGING --------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- CONFIG --------------------
TOKEN = os.getenv("TELEGRAM_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise SystemExit("TELEGRAM_TOKEN is required")

TARGET_LOCATIONS = [
    "United States", "United Kingdom", "Germany", "France", "Netherlands",
    "Switzerland", "Spain", "Italy", "Sweden", "Singapore", "Hong Kong",
    "United Arab Emirates", "Japan", "Australia", "Canada", "India"
]

EXCLUDED = {"nigeria", "ghana", "kenya", "south africa", "egypt", "morocco",
            "ethiopia", "uganda", "tanzania", "africa", "african"}

NICHES = {
    "crypto": ["crypto company", "bitcoin company", "cryptocurrency exchange", "blockchain company"],
    "forex": ["forex broker", "forex company"],
    "construction": ["construction company", "building contractor"]
}

# -------------------- HEALTH SERVER --------------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Ghost Mailer Bot is LIVE")

    def log_message(self, format, *args):
        return

def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"Health server on 0.0.0.0:{PORT}")
    server.serve_forever()

# -------------------- FREE SCRAPER --------------------
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@(?:info|contact|sales|support|hello|office|admin|team|business)[a-zA-Z0-9.-]*\.[a-zA-Z]{2,}",
    re.I
)
GENERIC_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def is_excluded(text: str) -> bool:
    text = (text or "").lower()
    return any(x in text for x in EXCLUDED)

def scrape_emails(url: str) -> List[str]:
    emails = set()
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        for m in EMAIL_RE.findall(text):
            emails.add(m.lower())
        for m in GENERIC_EMAIL.findall(text):
            if not any(x in m.lower() for x in ["example", "domain", "email.com", "sentry", "wix"]):
                emails.add(m.lower())
    except Exception:
        pass
    return list(emails)

def get_free_leads(niche: str = "crypto", country: Optional[str] = None, max_leads: int = 45) -> List[Dict]:
    leads = []
    seen = set()
    locations = [country] if country else TARGET_LOCATIONS[:8]
    terms = NICHES.get(niche, ["crypto company"])

    for loc in locations:
        if is_excluded(loc):
            continue
        for term in terms[:2]:
            query = f'"{term}" "{loc}" official site contact email -africa -nigeria -ghana'
            try:
                results = list(search(query, num_results=15, lang="en", unique=True))
            except Exception as e:
                logger.warning(f"Search failed: {e}")
                continue

            for url in results:
                if len(leads) >= max_leads:
                    return leads
                if is_excluded(url):
                    continue
                domain = urlparse(url).netloc.lower()
                if not domain or domain in seen:
                    continue
                seen.add(domain)

                emails = scrape_emails(url)
                # also try /contact
                if not emails:
                    emails = scrape_emails(urljoin(url, "/contact")) or scrape_emails(urljoin(url, "/contact-us"))

                for email in emails:
                    if email in seen or is_excluded(email):
                        continue
                    seen.add(email)
                    leads.append({
                        "company": domain.replace("www.", "").split(".")[0].title(),
                        "website": f"https://{domain}",
                        "email": email,
                        "country": loc,
                        "niche": niche,
                        "source": "free"
                    })
                    if len(leads) >= max_leads:
                        return leads
                time.sleep(1.2)
    return leads

def save_csv(leads: List[Dict], prefix: str = "crypto_leads") -> str:
    os.makedirs("data", exist_ok=True)
    path = f"data/{prefix}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "website", "email", "country", "niche", "source"])
        writer.writeheader()
        writer.writerows(leads)
    return path

# -------------------- BOT HANDLERS --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Ghost Mailer LIVE ✅\n\n"
        "Commands:\n"
        "/start – this message\n"
        "/freeleads – get 40-50 free crypto company leads (CSV)\n"
        "/leads crypto – crypto leads\n"
        "/leads crypto USA – crypto leads in USA\n"
        "/status – current status\n\n"
        "Markets: USA + Europe + Asia only\n"
        "Africa is completely excluded."
    )
    await update.message.reply_text(text)

async def freeleads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Scraping free crypto leads (this can take 1–3 minutes)...")
    loop = asyncio.get_event_loop()
    leads = await loop.run_in_executor(None, lambda: get_free_leads("crypto", max_leads=45))

    if not leads:
        await update.message.reply_text("❌ No leads found right now. Try again in a few minutes.")
        return

    path = save_csv(leads, "free_crypto")
    with open(path, "rb") as f:
        await update.message.reply_document(
            document=InputFile(f, filename=os.path.basename(path)),
            caption=f"✅ {len(leads)} free crypto company leads"
        )

async def leads_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    niche = "crypto"
    country = None
    if args:
        niche = args[0].lower()
        if len(args) > 1:
            country = " ".join(args[1:])

    await update.message.reply_text(f"🔍 Searching {niche} leads" + (f" in {country}" if country else "") + "...")
    loop = asyncio.get_event_loop()
    leads = await loop.run_in_executor(None, lambda: get_free_leads(niche, country, max_leads=40))

    if not leads:
        await update.message.reply_text("❌ No leads found. Try a different country or wait a bit.")
        return

    path = save_csv(leads, f"leads_{niche}")
    with open(path, "rb") as f:
        await update.message.reply_document(
            document=InputFile(f, filename=os.path.basename(path)),
            caption=f"✅ {len(leads)} {niche} leads"
        )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📊 *Bot Status*\n\n"
        "Mode: FREE (no API keys)\n"
        "Markets: USA + Europe + Asia\n"
        "Excluded: All African countries\n"
        "Niches: crypto, forex, construction\n"
        "Commands: /freeleads, /leads, /status"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# -------------------- MAIN --------------------
def main():
    # Fix for Python 3.12+ event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Health server
    t = threading.Thread(target=start_health_server, daemon=True)
    t.start()

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("freeleads", freeleads))
    application.add_handler(CommandHandler("leads", leads_cmd))
    application.add_handler(CommandHandler("status", status))

    logger.info("Bot starting with lead features...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
