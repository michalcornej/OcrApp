# OCR Uploader – Cloud-Based Extraction Tool

Webová aplikace pro automatizované rozpoznávání a evidenci šestimístných kódů z fotografií štítků. Projekt demonstruje integraci cloudových služeb do firemních procesů a důraz na bezpečné nakládání s credentials.

## Funkcionalita
* **AI Recognition:** Automatické rozpoznávání textu pomocí Google Cloud Vision API.
* **Manual Correction:** Rozhraní pro ověření a ruční korekci rozpoznaných dat uživatelem.
* **Evidence dat:** Ukládání zpracovaných údajů do CSV formátu pro další analýzu.
* **Moderní Web UI:** Responzivní rozhraní postavené na Flask a HTML/CSS/JS.

## Technologie
* **Backend:** Python (Flask)
* **Cloud AI:** Google Cloud Vision API
* **Zabezpečení:** Service Account klíč mimo repozitář (proměnná `GOOGLE_APPLICATION_CREDENTIALS`), volitelné HTTP Basic přihlášení

## Instalace a konfigurace
1. **Prerekvizity:** Python 3.9+ a Google Cloud projekt se zapnutým Cloud Vision API.
2. **Instalace závislostí:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Přihlašovací údaje ke Google Cloud:** stáhněte JSON klíč Service Accountu, uložte ho **mimo repozitář**
   (nebo jako `credentials.json`, který je v `.gitignore`) a nastavte cestu:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=/cesta/ke/credentials.json
   ```
4. **Spuštění:**
   ```bash
   export APP_PASSWORD=silne-heslo   # zapne přihlášení (uživatel dle APP_USERNAME, výchozí "admin")
   python app.py
   ```
   Aplikace běží na `http://127.0.0.1:5000`. Pro přístup z telefonu v lokální síti nastavte `HOST=0.0.0.0`
   (vždy společně s `APP_PASSWORD`).

## Proměnné prostředí
| Proměnná | Výchozí | Popis |
|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | – | Cesta k JSON klíči Service Accountu (povinné) |
| `APP_USERNAME` | `admin` | Uživatelské jméno pro přihlášení |
| `APP_PASSWORD` | – | Heslo; bez něj aplikace běží bez přihlášení |
| `HOST` | `127.0.0.1` | Adresa, na které server naslouchá |
| `PORT` | `5000` | Port serveru |
| `FLASK_DEBUG` | – | `1` zapne debug režim (nikdy ne na síti) |
| `OUTPUT_CSV` | `output.csv` | Soubor s evidencí |
| `MAX_UPLOAD_MB` | `10` | Maximální velikost nahrané fotky |

## Výstup
Záznamy se ukládají do CSV se sloupci `timestamp` (UTC, ISO 8601), `number`, `source_file`, `user`.
Fotky se zpracovávají pouze v paměti a na disk se neukládají.

## Bezpečnostní poznámky
* Vestavěný Flask server je určen pro vývoj; pro trvalý provoz použijte WSGI server (např. `gunicorn`) za HTTPS proxy.
* HTTP Basic přihlášení posílá heslo v každém požadavku – mimo localhost jej používejte jen přes HTTPS.
