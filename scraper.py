#!/usr/bin/env python3
"""
Scraper cours Bourse de Casablanca — CDG Capital Bourse
Strategie : intercepter les requetes reseau pour capturer l'API JSON interne
"""

import json, sys, time, re
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"], check=True)
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

OUTPUT = Path(__file__).parent / "data" / "cours.json"
URL    = "https://www.cdgcapitalbourse.ma/Bourse/market"

NAME_KEYS  = {"ticker","symbol","code","libelle","name","valeur","instrument",
              "shortname","fullname","isin","mnemo","mnemonic"}
PRICE_KEYS = {"cours","price","lastprice","dernier","last","close","cloture",
              "prixdernier","last_price","currentprice","settlementprice",
              "referenceprice","cours_dernier","coursdernier"}

def extract_prices(obj, depth=0):
    found = {}
    if depth > 8: return found
    if isinstance(obj, list):
        for item in obj:
            found.update(extract_prices(item, depth+1))
    elif isinstance(obj, dict):
        low = {k.lower(): v for k, v in obj.items()}
        name = next((str(low[k]).strip().upper()
                     for k in NAME_KEYS if k in low and low[k]), None)
        price = None
        for k in PRICE_KEYS:
            if k in low and low[k] not in (None, "", 0, "0"):
                try:
                    price = float(str(low[k]).replace(",",".").replace(" ",""))
                    if price > 0: break
                except: pass
        if name and price and 1 <= price <= 200000 and 2 <= len(name) <= 50:
            found[name] = price
        for v in obj.values():
            found.update(extract_prices(v, depth+1))
    return found

def scrape():
    print(f"[{datetime.now():%H:%M:%S}] Lancement Playwright -> {URL}")
    captured = {}
    cours    = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-setuid-sandbox",
                  "--disable-dev-shm-usage","--disable-gpu"]
        )
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/120 Safari/537.36"),
            viewport={"width":1440,"height":900},
            extra_http_headers={"Accept-Language":"fr-FR,fr;q=0.9"}
        )
        page = ctx.new_page()

        def on_response(resp):
            url = resp.url
            if any(url.endswith(ext) for ext in
                   [".js",".css",".png",".jpg",".woff",".svg",".ico"]): return
            try:
                ct = resp.headers.get("content-type","")
                if "json" not in ct and "text/plain" not in ct: return
                body = resp.json()
                captured[url] = body
                prices = extract_prices(body)
                if prices:
                    print(f"  OK {len(prices)} cours depuis: {url[:70]}")
                    cours.update(prices)
            except: pass

        page.on("response", on_response)

        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        except PWTimeout:
            print("  timeout domcontentloaded, on continue...")

        print("  Attente chargement React (30s max)...")
        for i in range(30):
            time.sleep(1)
            if cours:
                print(f"  Donnees trouvees apres {i+1}s")
                break
            if i == 5:
                try: page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                except: pass
            if i == 10:
                try:
                    for sel in ["button:has-text('Actions')", "a:has-text('Actions')",
                                "button:has-text('March')", "[href*='market']"]:
                        btn = page.query_selector(sel)
                        if btn:
                            print(f"  Clic sur: {sel}")
                            btn.click()
                            time.sleep(3)
                            break
                except: pass

        if not cours:
            print(f"  Pas d'API JSON. URLs capturees ({len(captured)}):")
            for u in list(captured.keys())[:20]:
                print(f"    {u[:90]}")
            print("  Tentative DOM scraping...")
            cours = dom_scrape(page)

        browser.close()
    return cours

def dom_scrape(page):
    cours = {}
    try:
        result = page.evaluate("""
        () => {
            const result = {};
            document.querySelectorAll('table').forEach(tbl => {
                tbl.querySelectorAll('tr').forEach(row => {
                    const cells = Array.from(row.querySelectorAll('td, th'));
                    if (cells.length < 2) return;
                    const name = cells[0]?.innerText?.trim().toUpperCase();
                    if (!name || name.length < 2 || name.length > 50) return;
                    for (let i = 1; i < cells.length; i++) {
                        const txt = cells[i]?.innerText?.trim()
                            .replace(/\\s/g,'').replace(',','.');
                        const n = parseFloat(txt);
                        if (n > 1 && n < 200000) { result[name] = n; break; }
                    }
                });
            });
            return result;
        }
        """)
        if result:
            cours = {k: v for k, v in result.items() if len(k) >= 2 and v > 0}
            print(f"  DOM: {len(cours)} cours trouves")
    except Exception as e:
        print(f"  DOM error: {e}")
    return cours

def save(cours):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "date":   datetime.now().strftime("%Y-%m-%d"),
        "time":   datetime.now().strftime("%H:%M"),
        "source": "CDG Capital Bourse",
        "count":  len(cours),
        "cours":  cours
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nSauvegarde: {len(cours)} cours -> {OUTPUT}")
    for k, v in list(cours.items())[:8]:
        print(f"   {k}: {v}")
    return out

if __name__ == "__main__":
    try:
        cours = scrape()
        save(cours)
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback; traceback.print_exc()
        save({})
        sys.exit(1)
