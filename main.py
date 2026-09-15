import os, re, csv, asyncio, random
from datetime import datetime
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import aiohttp
from googlesearch import search
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
APOLLO_KEY = os.getenv("APOLLO_API_KEY")
HUNTER_KEY = os.getenv("HUNTER_API_KEY")

TARGET_LOCATIONS = ["United States","United Kingdom","Germany","France","Netherlands","Switzerland","Spain","Italy","Sweden","Norway","Denmark","Ireland","Belgium","Poland","Portugal","Austria","Singapore","Hong Kong","United Arab Emirates","Japan","South Korea","Australia","Israel","Qatar","India","Malaysia","Thailand"]
EXCLUDED_KEYWORDS = ['nigeria','ghana','kenya','south africa','africa','egypt','morocco','ethiopia','uganda','tanzania']
NICHE_KEYWORDS = {"crypto": ["cryptocurrency","blockchain"],"forex": ["forex broker","fx trading"],"construction": ["construction company","general contractor"]}
EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
GOOD_EMAIL_PREFIXES = ['info@','contact@','sales@','support@','hello@','admin@']

def extract_emails_from_website(domain):
    headers = {"User-Agent": "Mozilla/5.0"}
    found = set()
    for path in ["/","/contact","/contact-us","/about"]:
        try:
            url = f"https://{domain}{path}"
            r = requests.get(url, headers=headers, timeout=6)
            emails = re.findall(EMAIL_REGEX, r.text)
            for e in emails:
                e = e.lower().strip()
                if any(e.startswith(p) for p in GOOD_EMAIL_PREFIXES):
                    if not any(x in e for x in EXCLUDED_KEYWORDS):
                        found.add(e)
            if found: break
        except: continue
    return list(found)

def get_free_leads(niche, country, limit=30):
    query = f'"{niche}" company official site {country} email contact'
    leads = []
    try:
        for url in search(query, num_results=limit*2, lang='en', sleep_interval=2):
            try:
                domain = url.split('/')[2].replace('www.','')
                if any(x in domain for x in ['facebook.com','linkedin.com']): continue
                emails = extract_emails_from_website(domain)
                for email in emails:
                    leads.append({"company":domain.split('.')[0].capitalize(),"domain":domain,"country":country,"email":email,"niche":niche,"source":"free"})
                    if len(leads) >= limit: return leads
            except: continue
    except: pass
    return leads

async def fetch_apollo_batch(keyword, location, page, session):
    if not APOLLO_KEY: return []
    url = "https://api.apollo.io/v1/mixed_companies/search"
    headers = {"x-api-key": APOLLO_KEY, "Content-Type": "application/json"}
    payload = {"q_organization_keyword_tags": [keyword],"organization_locations": [location],"page": page,"per_page": 30}
    try:
        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()
            return data.get('organizations', [])
    except: return []

async def build_500_leads_async():
    all_leads = []
    if not APOLLO_KEY:
        for niche_type, kws in NICHE_KEYWORDS.items():
            for country in random.sample(TARGET_LOCATIONS, 5):
                leads = get_free_leads(kws[0], country, 15)
                all_leads.extend(leads)
                if len(all_leads) >= 150: return all_leads
        return all_leads
    async with aiohttp.ClientSession() as session:
        for niche_type, keywords in NICHE_KEYWORDS.items():
            for location in TARGET_LOCATIONS:
                for kw in keywords:
                    for page in [1,2]:
                        orgs = await fetch_apollo_batch(kw, location, page, session)
                        for comp in orgs:
                            country = (comp.get('country') or "").lower()
                            if any(bad in country for bad in EXCLUDED_KEYWORDS): continue
                            domain = comp.get('primary_domain')
                            if not domain: continue
                            email = f"info@{domain}"
                            all_leads.append({"company":comp.get('name'),"domain":domain,"country":comp.get('country'),"email":email,"niche":niche_type,"source":"apollo"})
                            if len(all_leads) >= 500: return all_leads
                        await asyncio.sleep(0.3)
    return all_leads

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🚀 *Lead Bot Perfect - USA + EU + ASIA*\nAfrica excluded ✅\n\n*Commands:*\n/freeleads - 50 FREE leads now\n/leads crypto - Crypto leads\n/leads construction USA - Contractors\n/leads forex Singapore - Forex\n/daily on 08:00 - Daily 500 leads\n/daily off - Stop\n/status - Show mode"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def freeleads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Free mode scraping... 2-3 mins for 50 leads...")
    loop = asyncio.get_event_loop()
    leads = await loop.run_in_executor(None, lambda: get_free_leads("construction company","USA",20) + get_free_leads("crypto company","Singapore",15) + get_free_leads("forex broker","United Kingdom",15))
    if not leads:
        await update.message.reply_text("No leads found, try again.")
        return
    filename = f"/tmp/free_leads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["company","domain","country","email","niche"])
        writer.writeheader()
        writer.writerows(leads)
    await update.message.reply_document(document=open(filename,'rb'), caption=f"✅ {len(leads)} FREE leads | USA + EU + ASIA")

async def leads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /leads crypto OR /leads construction USA")
        return
    niche_arg = context.args[0].lower()
    country_arg = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    keyword = NICHE_KEYWORDS.get(niche_arg, [niche_arg])[0]
    target_country = country_arg if country_arg else random.choice(TARGET_LOCATIONS)
    await update.message.reply_text(f"⏳ Fetching {niche_arg.upper()} from {target_country}...")
    loop = asyncio.get_event_loop()
    leads = await loop.run_in_executor(None, lambda: get_free_leads(keyword, target_country or "USA", 30))
    filename = f"/tmp/leads_{niche_arg}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["company","domain","country","email","niche"])
        writer.writeheader()
        writer.writerows(leads)
    await update.message.reply_document(document=open(filename,'rb'), caption=f"✅ {len(leads)} {niche_arg} leads")

async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    await context.bot.send_message(chat_id=chat_id, text="🚀 Starting daily 500 leads build...")
    leads = await build_500_leads_async()
    chunk_size = 170
    for i in range(0, len(leads), chunk_size):
        chunk = leads[i:i+chunk_size]
        filename = f"/tmp/DAILY_{i//chunk_size+1}_{datetime.now().strftime('%Y%m%d')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["company","domain","country","email","niche"])
            writer.writeheader()
            writer.writerows(chunk)
        await context.bot.send_document(chat_id=chat_id, document=open(filename,'rb'), caption=f"📦 Daily Part {i//chunk_size+1} - {len(chunk)} leads")

async def set_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() == 'off':
        jobs = context.job_queue.get_jobs_by_name(str(update.effective_chat.id))
        for job in jobs: job.schedule_removal()
        await update.message.reply_text("❌ Daily OFF")
        return
    time_str = context.args[1] if context.args[0].lower() == 'on' and len(context.args) > 1 else context.args[0]
    try:
        for job in context.job_queue.get_jobs_by_name(str(update.effective_chat.id)): job.schedule_removal()
        context.job_queue.run_daily(daily_job, time=datetime.strptime(time_str, "%H:%M").time(), chat_id=update.effective_chat.id, name=str(update.effective_chat.id))
        await update.message.reply_text(f"✅ Daily ON at {time_str} WAT - 500 leads daily")
    except:
        await update.message.reply_text("Use: /daily on 08:00 or /daily off")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = "💰 PAID (500/day)" if APOLLO_KEY else "🆓 FREE (50-200/day)"
    await update.message.reply_text(f"Mode: {mode}\nMarkets: USA + EU + Asia\nExcluded: Africa\nApollo: {'Set' if APOLLO_KEY else 'Not set'}")

def main():
    if not TELEGRAM_TOKEN:
        print("ERROR: Set TELEGRAM_TOKEN")
        return
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("freeleads", freeleads))
    app.add_handler(CommandHandler("leads", leads_command))
    app.add_handler(CommandHandler("daily", set_daily))
    app.add_handler(CommandHandler("status", status))
    print("Bot running... USA + EU + ASIA, No Africa")
    app.run_polling()
if __name__ == "__main__":
    main()
