#!/usr/bin/env python3
"""
Scraper cours Bourse de Casablanca — CDG Capital Bourse
Récupère les cours depuis cdgcapitalbourse.ma/Bourse/market
et génère un fichier cours.json consommable par le tableau de bord.
"""

import json
import sys
import time
import re
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Installation de playwright...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"], check=True)
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


URL = "https://www.cdgcapitalbourse.ma/Bourse/market"
OUTPUT = Path(__file__).parent / "data" / "cours.json"


def scrape_cours():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Ouverture de {URL}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        # Intercepter les requêtes réseau pour trouver l'API JSON
        api_data = {}

        def handle_response(response):
            url = response.url
            if any(kw in url.lower() for kw in ["market", "cours", "quote", "instrument", "action"]):
                if response.status == 200:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        try:
                            body = response.json()
                            api_data[url] = body
                            print(f"  → API JSON interceptée: {url[:80]}")
                        except:
                            pass

        page.on("response", handle_response)

        try:
            page.goto(URL, wait_until="networkidle", timeout=60000)
        except PlaywrightTimeout:
            print("Timeout networkidle, on continue...")

        # Attendre que le tableau se charge
        time.sleep(5)

        # Si on a intercepté des données API, les utiliser
        cours = {}
        if api_data:
            for url, data in api_data.items():
                print(f"  Analyse de: {url[:60]}")
                extracted = extract_from_api(data)
                if extracted:
                    cours.update(extracted)
                    print(f"  {len(extracted)} cours extraits depuis l'API")

        # Sinon, scraper le DOM
        if not cours:
            print("  Pas d'API JSON, scraping du DOM...")
            cours = scrape_dom(page)

        browser.close()
        return cours


def extract_from_api(data):
    """Tente d'extraire les cours d'une réponse API JSON."""
    cours = {}
    
    # Chercher récursivement les structures avec ticker/cours
    def search(obj, depth=0):
        if depth > 5:
            return
        if isinstance(obj, list):
            for item in obj:
                search(item, depth + 1)
        elif isinstance(obj, dict):
            # Chercher des clés typiques
            name_keys = ["ticker", "symbol", "code", "libelle", "name", "valeur", "instrument"]
            price_keys = ["cours", "price", "lastPrice", "dernier", "last", "close", "cloture"]
            
            name = None
            price = None
            
            for k in name_keys:
                for key in obj.keys():
                    if k.lower() in key.lower() and obj[key]:
                        name = str(obj[key]).strip().upper()
                        break
            
            for k in price_keys:
                for key in obj.keys():
                    if k.lower() in key.lower() and obj[key]:
                        try:
                            price = float(str(obj[key]).replace(",", ".").replace(" ", ""))
                            break
                        except:
                            pass
            
            if name and price and price > 0:
                cours[name] = price
            
            for v in obj.values():
                search(v, depth + 1)
    
    search(data)
    return cours


def scrape_dom(page):
    """Scrape les cours directement depuis le DOM."""
    cours = {}
    
    try:
        # Attendre qu'un tableau apparaisse
        page.wait_for_selector("table, .market-table, [class*='table'], [class*='grid']", timeout=15000)
    except:
        print("  Aucun tableau trouvé")

    # Extraire tout le texte de la page et chercher les patterns NOM + COURS
    content = page.content()
    
    # Pattern: nom d'action suivi d'un cours en MAD
    # Ex: "ATTIJARIWAFA BANK 690,00 MAD" ou "ATW 690.00"
    patterns = [
        r'([A-Z][A-Z\s&\-\.]{2,30})\s+(\d{1,6}[,\.]\d{2})\s*(?:MAD)?',
        r'"(?:libelle|name|ticker|symbol)"\s*:\s*"([^"]+)"\s*[^}]*"(?:cours|price|lastPrice|dernier)"\s*:\s*([\d,\.]+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for name, price_str in matches:
            name = name.strip().upper()
            if len(name) < 2 or len(name) > 40:
                continue
            try:
                price = float(price_str.replace(",", ".").replace(" ", ""))
                if 1 <= price <= 100000:
                    cours[name] = price
            except:
                pass

    # Essayer aussi via JavaScript d'extraire les données du tableau
    try:
        js_cours = page.evaluate("""
        () => {
            const result = {};
            const rows = document.querySelectorAll('tr, [class*="row"]');
            rows.forEach(row => {
                const cells = row.querySelectorAll('td, [class*="cell"]');
                if (cells.length >= 2) {
                    const name = cells[0]?.textContent?.trim().toUpperCase();
                    const priceText = cells[1]?.textContent?.trim().replace(/[, ]/g, (m) => m === ',' ? '.' : '');
                    const price = parseFloat(priceText);
                    if (name && price > 0 && name.length > 1 && name.length < 40) {
                        result[name] = price;
                    }
                }
            });
            return result;
        }
        """)
        if js_cours:
            cours.update(js_cours)
            print(f"  {len(js_cours)} cours via JS DOM")
    except Exception as e:
        print(f"  JS DOM error: {e}")

    return cours


def save_cours(cours):
    """Sauvegarde les cours en JSON."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    
    output = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M"),
        "source": "CDG Capital Bourse",
        "count": len(cours),
        "cours": cours
    }
    
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ {len(cours)} cours sauvegardés dans {OUTPUT}")
    return output


def main():
    try:
        cours = scrape_cours()
        
        if not cours:
            print("⚠ Aucun cours récupéré — marché fermé ou site inaccessible")
            # Créer un fichier vide pour signaler l'échec
            save_cours({})
            sys.exit(0)
        
        print(f"\n{len(cours)} cours récupérés:")
        for name, price in list(cours.items())[:10]:
            print(f"  {name}: {price}")
        if len(cours) > 10:
            print(f"  ... et {len(cours)-10} autres")
        
        save_cours(cours)
        
    except Exception as e:
        print(f"✗ Erreur: {e}")
        import traceback
        traceback.print_exc()
        save_cours({})
        sys.exit(1)


if __name__ == "__main__":
    main()
