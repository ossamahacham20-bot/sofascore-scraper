import json
import time
import logging
from datetime import datetime, timedelta
import requests
from playwright.sync_api import sync_playwright
import os

# --- CONFIGURAZIONE ---
API_ENDPOINT = "https://xklcbytyjyxckuorxxal.supabase.co/functions/v1/receive-matches"
LOG_FILE = "sofascore_scraper.log"
DUMP_DIR = "./dumps"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

# --- FUNZIONI UTILI ---
def save_dump(payload):
    os.makedirs(DUMP_DIR, exist_ok=True)
    
    # Dump storico con timestamp
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fname_historical = f"{DUMP_DIR}/sofascore_dump_{ts}.json"
    with open(fname_historical, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logging.info(f"Dump storico salvato: {fname_historical}")
    
    # Dump "latest" per il sito principale
    fname_latest = f"{DUMP_DIR}/sofascore_latest.json"
    with open(fname_latest, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logging.info(f"Dump LATEST salvato: {fname_latest}")

def post_payload(payload):
    try:
        resp = requests.post(API_ENDPOINT, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
        logging.info(f"POST {API_ENDPOINT} -> status {resp.status_code}")
        return 200 <= resp.status_code < 300
    except Exception as e:
        logging.error(f"Errore invio payload: {e}")
        return False

# --- SCRAPING FUNZIONE ---
def scrape_day(date_obj):
    """Scrape partite di un giorno specifico (oggi o futuro)"""
    date_str = date_obj.strftime("%Y-%m-%d")
    url = f"https://www.sofascore.com/football/{date_str}"
    matches = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        time.sleep(5)  # attendi caricamento JS

        # seleziona tutte le partite
        rows = page.query_selector_all("div.js-list-cell-target")
        for r in rows:
            try:
                # orario
                time_el = r.query_selector("div[title] bdi")
                time_start = time_el.inner_text() if time_el else None

                # squadre
                teams = r.query_selector_all("div.ov_hidden bdi")
                home = teams[0].inner_text() if len(teams) > 0 else None
                away = teams[1].inner_text() if len(teams) > 1 else None

                # punteggio
                score_el = r.query_selector("span.currentScore bdi")
                score = score_el.inner_text() if score_el else "-"

                # lega / torneo
                league_el = r.query_selector("bdi.textStyle_display.micro")
                league = league_el.inner_text() if league_el else None

                # paese
                country_el = r.query_selector("bdi.textStyle_assistive.default")
                country = country_el.inner_text() if country_el else None

                matches.append({
                    "date": date_str,
                    "time_start": time_start,
                    "home": home,
                    "away": away,
                    "score": score,
                    "league": league,
                    "country": country
                })
            except Exception:
                continue

        browser.close()
    return matches

def scrape_sofascore():
    payload = {
        "scrape_time_utc": datetime.now().isoformat(),
        "today": [],
        "next_7_days": []
    }

    today = datetime.now()
    # partite di oggi
    payload["today"] = scrape_day(today)
    logging.info(f"Partite oggi: {len(payload['today'])}")

    # prossimi 7 giorni
    for delta in range(1, 8):
        d = today + timedelta(days=delta)
        matches = scrape_day(d)
        payload["next_7_days"].append({
            "date": d.strftime("%Y-%m-%d"),
            "matches": matches
        })
        logging.info(f"Partite {d.strftime('%Y-%m-%d')}: {len(matches)}")

    return payload

# --- MAIN ---
if __name__ == "__main__":
    logging.info("Inizio scraping SofaScore")
    data = scrape_sofascore()
    save_dump(data)
    post_payload(data)
    logging.info("Fine scraping")


