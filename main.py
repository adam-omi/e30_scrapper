import httpx
import sqlite3
from selectolax.parser import HTMLParser
import re

TARGETS = [
    ("Autoplac", "https://autoplac.pl/oferty/samochody-osobowe/bmw/seria-3?fullTextQuery=e30&yearTo=1995&orderBy=INSERT_TIME&sortOrder=DESC"),
    ("OLX", "https://www.olx.pl/motoryzacja/samochody/bmw/q-bmw-e30/?search%5Border%5D=filter_float_price:asc&search%5Bfilter_enum_model%5D%5B0%5D=3-as-sorozat&search%5Bfilter_float_year:to%5D=1995"),
    ("Sprzedajemy", "https://sprzedajemy.pl/motoryzacja/samochody-osobowe/bmw/seria-3?inp_text%5Bv%5D=e30&inp_attribute_466%5Bto%5D=1995&offset=0&sort=inp_srt_date_d")
]

# --- KONFIGURACJA TELEGRAM ---
USE_TELEGRAM = False  # Zmień na True, żeby aktywować wysyłanie!
TELEGRAM_TOKEN = "TOKEN"  # Wstaw swój token bota
TELEGRAM_CHAT_ID = "ID"  # Wstaw ID swojego czatu

# --- HELPERS TO REDUCE DUPLICATION ---

def clean_text(text):
    """Removes hard spaces and strips whitespace."""
    if not text: return ""
    return text.replace('\xa0', ' ').strip()

def extract_regex(pattern, text, default="?"):
    """Generic regex helper to find years or mileage."""
    match = re.search(pattern, clean_text(text))
    return match.group(1).strip() if match else default

def format_link(base_url, href):
    """Ensures relative links are made absolute."""
    if not href: return ""
    return base_url + href if href.startswith("/") else href

def get_node_text(node):
    """Safely extracts text from a Selectolax node."""
    return clean_text(node.text()) if node else ""

def send_telegram_message(text):
    """Wysyła wiadomość przez API Telegrama."""
    if not USE_TELEGRAM or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML" # Pozwala na pogrubienia w wiadomości
    }
    try:
        httpx.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Błąd wysyłania na Telegram: {e}")

# --- CORE SCRAPING LOGIC ---

def fetch_html(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        return response.text
    except Exception as e:
        print(f"Błąd pobierania: {e}")
        return None

def parse_autoplac(html):
    tree = HTMLParser(html)
    offers = tree.css("a.tile") 
    found_cars = []
    
    for offer in offers:
        params = offer.css("span.parameters__value")
        found_cars.append({
            "title": clean_text(offer.css_first("span.tile__text").text()) if offer.css_first("span.tile__text") else "Brak",
            "price": clean_text(offer.css_first("p.price__main").text()) if offer.css_first("p.price__main") else "Brak",
            "year": params[1].text(strip=True) if len(params) > 1 else "?",
            "mileage": params[2].text(strip=True) if len(params) > 2 else "?",
            "link": format_link("https://autoplac.pl", offer.attributes.get("href", ""))
        })
    return found_cars

def parse_olx(html):
    tree = HTMLParser(html)
    for tag in tree.css('style, script'): tag.decompose()
    
    found_cars = []
    for offer in tree.css('div[data-testid="l-card"]'):
        title_node = offer.css_first('div[data-testid="ad-card-title"] a')
        if not title_node: continue
        
        # Bezpieczne wyciąganie tekstów za pomocą helpera
        p_text = get_node_text(offer.css_first('div[color="text-global-secondary"]'))
        location = get_node_text(offer.css_first('p[data-testid="location-date"]')).split(' - ')[0]
        price = get_node_text(offer.css_first('p[data-testid="ad-price"]')).replace("do negocjacji", "").strip()
        
        found_cars.append({
            "title": f"{get_node_text(title_node)} [{location or 'Brak'}]",
            "price": price or "Brak",
            "year": extract_regex(r'(19\d{2}|20\d{2})', p_text),
            "mileage": extract_regex(r'(\d[\d\s]*km)', p_text),
            "link": format_link("https://www.olx.pl", title_node.attributes.get("href", ""))
        })
    return found_cars

def parse_sprzedajemy(html):
    tree = HTMLParser(html)
    found_cars = []
    
    for offer in tree.css('article.element'):
        title_node = offer.css_first('h2.title a')
        if not title_node: continue
        
        # Bezpieczne wyciąganie tekstów za pomocą helpera
        p_text = get_node_text(offer.css_first('p.attributes'))
        location = get_node_text(offer.css_first('div.company-and-city'))
        price = get_node_text(offer.css_first('span.price'))
        
        found_cars.append({
            "title": f"{get_node_text(title_node)} [{location or 'Brak'}]",
            "price": price or "Brak",
            "year": extract_regex(r'(19\d{2}|20\d{2})', p_text),
            "mileage": extract_regex(r'(\d[\d\s]*km)', p_text),
            "link": format_link("https://sprzedajemy.pl", title_node.attributes.get("href", ""))
        })
    return found_cars

# --- DATABASE & EXECUTION ---

def setup_database():
    conn = sqlite3.connect('e30_baza.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS offers (
                    link TEXT UNIQUE, title TEXT, price TEXT, 
                    year TEXT, mileage TEXT, date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    return conn

def process_offers(conn, offers):
    cursor = conn.cursor()
    new_ones = []
    for car in offers:
        try:
            cursor.execute("INSERT INTO offers (link, title, price, year, mileage) VALUES (?, ?, ?, ?, ?)", 
                           (car['link'], car['title'], car['price'], car['year'], car['mileage']))
            new_ones.append(car)
        except sqlite3.IntegrityError:
            continue # Already in DB
    conn.commit()
    return new_ones

def main():
    db = setup_database()
    parsers = {"Autoplac": parse_autoplac, "OLX": parse_olx, "Sprzedajemy": parse_sprzedajemy}
    
    for name, url in TARGETS:
        print(f"🔍 Skanuję {name}...")
        html = fetch_html(url)
        if not html: continue
        
        results = parsers[name](html)
        new_cars = process_offers(db, results)
        
        if new_cars:
            print(f"🎉 NOWE ({len(new_cars)}) na {name}!")
            for car in new_cars:
                # Formatujemy ładną wiadomość
                msg = f"🚗 <b>{car['title']}</b>\n💰 {car['price']}\n📅 {car['year']} | 📍 {car['mileage']}\n🔗 <a href='{car['link']}'>Link do ogłoszenia</a>"
                
                # Print do konsoli (usuwamy tagi HTML, żeby w terminalu było czysto)
                print(msg.replace('<b>', '').replace('</b>', '').replace('\n', ' | ').split("<a href=")[0] + car['link'])
                
                # Wysłanie na Telegram (jeśli włączone)
                send_telegram_message(msg)
        else:
            print(f"Brak nowych ogłoszeń.")

if __name__ == "__main__":
    main()