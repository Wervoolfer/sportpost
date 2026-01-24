import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import telebot
import schedule
import time
import json
import os
import logging
import html
from datetime import datetime
BOT_TOKEN = os.getenv("BOT_TOKEN")
CONFIG = {
    "CHANNEL_ID": "@HighLihgt_Sport",
    "ADMIN_IDS": [1069952782, 7932270010, 5893713874], 
    "MAX_POSTS": 1,          
    "POSTED_FILE": "posted_news.json",
    "LOG_FILE": "bot_log.txt"
}

KEYWORDS = [
    "футбол", "матч", "гол", "трансфер", "лига", "кубок", "чемпионат", 
    "рпл", "апл", "лч", "реал", "бавария", "барселона", "спартак", "зенит",
    "тренер", "состав", "сборная", "турнир", "хоккей", "теннис"
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(CONFIG["LOG_FILE"], encoding='utf-8'),
        logging.StreamHandler()
    ]
)

bot = telebot.TeleBot(BOT_TOKEN)

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================

def load_posted():
    if os.path.exists(CONFIG["POSTED_FILE"]):
        try:
            with open(CONFIG["POSTED_FILE"], "r", encoding="utf-8") as f:
                return json.load(f)
        except: return []
    return []

def save_posted(posted):
    with open(CONFIG["POSTED_FILE"], "w", encoding="utf-8") as f:
        json.dump(posted[-200:], f, ensure_ascii=False, indent=2)

def is_sport_related(text):
    text = text.lower()
    return any(word in text for word in KEYWORDS)

# ===================== УМНЫЙ ПАРСИНГ КОНТЕНТА =====================

def get_full_article_data(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        
        description = ""
        # Исправлено склеивание (separator=' ')
        intro_tag = soup.find("div", class_="article-content__intro") or soup.find("p")
        if intro_tag:
            description = intro_tag.get_text(separator=' ', strip=True)

        image = None
        og_image = soup.find("meta", property="og:image")
        if og_image:
            image = og_image["content"]
            
        return description[:400], image
    except Exception as e:
        logging.error(f"Ошибка парсинга статьи {url}: {e}")
        return "", None

def get_news():
    news_list = []
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get("https://www.championat.com/football/", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("article.news-item a, a.news-item__title, .post-item__title")
        
        for item in items:
            title = item.get_text(separator=' ', strip=True)
            href = item.get("href")
            if not href or len(title) < 15: continue
            full_url = href if href.startswith("http") else "https://www.championat.com" + href
            if is_sport_related(title):
                news_list.append({"title": title, "url": full_url})
    except Exception as e:
        logging.error(f"Ошибка сбора списка: {e}")
    return news_list

# ===================== ОСНОВНАЯ РАБОТА =====================

def job():
    logging.info("=== ЗАПУСК ЦИКЛА ПАРСИНГА ===")
    posted = load_posted()
    all_news = get_news()
    
    new_posts_count = 0
    for item in all_news:
        if item["title"] in posted or new_posts_count >= CONFIG["MAX_POSTS"]:
            continue

        logging.info(f"Обработка: {item['title']}")
        desc, img = get_full_article_data(item["url"])
        
        if not img:
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.images(item["title"] + " футбол", max_results=1))
                    if results: img = results[0]["image"]
            except: pass

        # Форматирование (HTML стиль везде одинаковый)
        safe_title = html.escape(item["title"].strip("!").upper() + "!")
        safe_desc = html.escape(desc) if desc else ""
        
        caption = (
            f"<b>🔥 {safe_title}</b>\n\n"
            f"{safe_desc}\n\n"
            f"⚽️ <b><a href='https://t.me/HighLihgt_Sport'>ХайЛайт Спорт — Подписаться</a></b>"
        )

        try:
            if img:
                bot.send_photo(CONFIG["CHANNEL_ID"], img, caption=caption, parse_mode="HTML")
            else:
                bot.send_message(CONFIG["CHANNEL_ID"], caption, parse_mode="HTML")
            
            posted.append(item["title"])
            new_posts_count += 1
            time.sleep(5) 
        except Exception as e:
            logging.error(f"Ошибка отправки поста: {e}")

    save_posted(posted)
    logging.info(f"=== ЦИКЛ ЗАВЕРШЕН ===")

# ===================== КОМАНДЫ ДЛЯ АДМИНА =====================

# ===================== КОМАНДЫ ДЛЯ АДМИНОВ =====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Теперь проверяем, входит ли ID в список админов
    if message.from_user.id in CONFIG["ADMIN_IDS"]:
        help_text = (
            "<b>👋 Привет, Админ! Я бот канала ХайЛайт Спорт.</b>\n\n"
            "<b>Доступные команды:</b>\n"
            "🚀 /run — Запустить парсинг прямо сейчас\n"
            "📊 /status — Состояние бота и базы\n"
            "⚙️ /set_limit 3 — Изменить кол-во постов\n"
        )
        bot.send_message(message.chat.id, help_text, parse_mode="HTML")
    else:
        bot.reply_to(message, "У вас нет прав администратора.")

@bot.message_handler(commands=['run'])
def manual_run(message):
    if message.from_user.id in CONFIG["ADMIN_IDS"]:
        bot.send_message(message.chat.id, "🚀 <b>Начинаю поиск свежих новостей...</b>", parse_mode="HTML")
        job()

@bot.message_handler(commands=['status'])
def status(message):
    if message.from_user.id in CONFIG["ADMIN_IDS"]:
        posted_list = load_posted()
        msg = (
            f"<b>📊 Статус бота:</b>\n"
            f"✅ Работает\n"
            f"📈 Лимит за раз: {CONFIG['MAX_POSTS']}\n"
            f"🗂 База (уникальных новостей): {len(posted_list)}"
        )
        bot.send_message(message.chat.id, msg, parse_mode="HTML")

@bot.message_handler(commands=['set_limit'])
def set_limit(message):
    if message.from_user.id in CONFIG["ADMIN_IDS"]:
        try:
            new_limit = int(message.text.split()[1])
            CONFIG["MAX_POSTS"] = new_limit
            bot.send_message(message.chat.id, f"✅ <b>Лимит обновлен:</b> {new_limit} постов.", parse_mode="HTML")
        except:
            bot.send_message(message.chat.id, "⚠️ Ошибка. Пример: <code>/set_limit 3</code>", parse_mode="HTML")
# ===================== ЗАПУСК =====================

import threading
threading.Thread(target=bot.infinity_polling).start()

schedule.every().day.at("08:30").do(job)
schedule.every().day.at("20:00").do(job)

logging.info("Бот ХайЛайт Спорт запущен!")

while True:
    schedule.run_pending()
    time.sleep(1)