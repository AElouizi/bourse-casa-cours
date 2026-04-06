#!/usr/bin/env python3
"""
Scraper cours Bourse de Casablanca
API directe : https://www.cdgcapitalbourse.ma/api/
"""

import json, sys, time, requests
from datetime import datetime
from pathlib import Path

OUTPUT = Path(__file__).parent / "data" / "cours.json"
API_BASE = "https://www.cdgcapitalbourse.ma/api/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": "https://www.cdgcapitalbourse.ma/Bourse/market",
    "Origin": "https://www.cdgcapitalbourse.ma",
}

NAME_KEYS  = {"ticker","symbol","code","libelle","name","valeur","instrument",
              "shortname","fullname","mnemo","mnemonic","libellevaleur",
              "shortlibelle","nommnemonic"}
PRICE_KEYS = {"cours","price","lastprice","dernier","last","close","cloture",
              "prixdernier","last_price","currentprice","coursdernier",
              "referenceprice","derniercours","prixactuel"}


def extract_prices(obj, depth=0):
    found = {}
    if depth > 8: return found
    if isinstance(obj, list):
        for item in obj:
            found.update(extract_prices(item, depth + 1))
    elif isinstance(obj, dict):
        low = {k.lower().replace("_","").replace(" ",""): v for k, v in obj.items()}
        name = next((str(low[k]).strip().upper()
                     for k in NAME_KEYS if k in low and low[k] and str(low[k]).strip()), None)
        price = None
        for k in PRICE_KEYS:
            if k in low and low[k] not in (None, "", 0, "0", 0.0):
                try:
                    price = float(str(low[k]).replace(",", ".").replace(" ", ""))
                    if price > 0: break
                except: pass
        if name and price and 1 <= price <= 500000 and 2 <= len(name) <= 60:
            if not name.startswith("MA0"):
                found[name] = price
        for v in obj.values():
            if isinstance(v, (dict, list)):
                found.update(extract_prices(v, depth + 1))
    return found


def try_api_direct():
    """Essaie plusieurs endpoints de l'API CDG Capital Bourse."""
    endpoints = [
        "Instrument/GetAllInstruments",
        "Instrument/GetInstruments",
        "Market/GetMarketData",
        "Market/GetAllMarket",
        "Quote/GetAllQuotes",
        "Quote/GetQuotes",
        "Bourse/GetMarket",
        "Cotation/GetAll",
        "",
    ]
    cours = {}
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get("https://www.cdgcapitalbourse.ma/Bourse/market", timeout=10)
    except: pass

    for endpoint in endpoints:
        url = API_BASE + endpoint
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code != 200: continue
            ct = resp.headers.get("content-type", "")
            if "json" not in ct and "plain" not in ct: continue
            data = resp.json()
            prices = extract_prices(data)
            if prices:
                print(f"  OK {len(prices)} cours depuis: {url}")
                cours.update(prices)
                if len(cours) >= 50: break
        except: pass
    return cours


def scrape_playwright():
    """Fallback Playwright."""
    print("  Utilisation Playwright...")
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"], check=True)
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    cours = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
            args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"])
        ctx = browser.new_context(user_agent=HEADERS["User-Agent"], viewport={"width":1440,"height":900})
        page = ctx.new_page()

        def on_response(resp):
            url = resp.url
            if any(url.endswith(e) for e in [".js",".css",".png",".jpg",".woff",".svg"]): return
            try:
                ct = resp.headers.get("content-type","")
                if "json" not in ct: return
                data = resp.json()
                prices = extract_prices(data)
                if prices:
                    print(f"  OK {len(prices)} cours: {url[:70]}")
                    cours.update(prices)
                    if len(prices) > 10:
                        api_file = Path(__file__).parent / "data" / "api_url.txt"
                        api_file.parent.mkdir(exist_ok=True)
                        api_file.write_text(url)
            except: pass

        page.on("response", on_response)
        try:
            page.goto("https://www.cdgcapitalbourse.ma/Bourse/market",
                     wait_until="domcontentloaded", timeout=45000)
        except PWTimeout: pass

        for i in range(30):
            time.sleep(1)
            if len(cours) >= 50:
                print(f"  Trouve apres {i+1}s")
                break
            if i == 8:
                try:
                    for sel in ["button:has-text('Actions')", "a:has-text('Actions')"]:
                        btn = page.query_selector(sel)
                        if btn: btn.click(); break
                except: pass
        browser.close()
    return cours


def save(cours):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out = {"date": datetime.now().strftime("%Y-%m-%d"),
           "time": datetime.now().strftime("%H:%M"),
           "source": "CDG Capital Bourse",
           "count": len(cours), "cours": cours}
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nSauvegarde: {len(cours)} cours")
    for k, v in list(cours.items())[:10]:
        print(f"   {k}: {v}")


if __name__ == "__main__":
    print(f"[{datetime.now():%H:%M:%S}] Scraper Bourse de Casablanca")
    cours = try_api_direct()
    if len(cours) < 10:
        print(f"  API directe: {len(cours)} cours seulement -> Playwright")
        cours = scrape_playwright()
    if not cours:
        print("Aucun cours recupere")
    save(cours)
