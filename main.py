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
