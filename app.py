from flask import Flask, render_template, request, jsonify, Response
from google.cloud import vision
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import os
import re
import csv
import hmac
import logging
import threading


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('ocrapp')

app = Flask(__name__)
# Limit velikosti nahrávaného souboru (výchozí 10 MB)
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_UPLOAD_MB', '10')) * 1024 * 1024

OUTPUT_CSV = os.environ.get('OUTPUT_CSV', 'output.csv')
CSV_HEADER = ['timestamp', 'number', 'source_file', 'user']
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'heic', 'heif', 'tif', 'tiff'}

# Přesně 6 číslic, případně ve tvaru „123 456“ / „123-456“
NUMBER_RE = re.compile(r'(?<![\d\-])(\d{3})[ \-]?(\d{3})(?![\d\-])')
VALID_NUMBER_RE = re.compile(r'^\d{6}$')

# Přihlašovací údaje aplikace (HTTP Basic Auth). Bez APP_PASSWORD je aplikace bez ochrany.
APP_USERNAME = os.environ.get('APP_USERNAME', 'admin')
APP_PASSWORD = os.environ.get('APP_PASSWORD')

csv_lock = threading.Lock()
_vision_client = None


def get_vision_client():
    # Klient se vytváří až při prvním použití. Přihlašovací údaje ke Google Vision API
    # se načítají z proměnné prostředí GOOGLE_APPLICATION_CREDENTIALS.
    global _vision_client
    if _vision_client is None:
        _vision_client = vision.ImageAnnotatorClient()
    return _vision_client


def find_candidates(text):
    candidates = []
    for match in NUMBER_RE.finditer(text):
        number = match.group(1) + match.group(2)
        if number not in candidates:
            candidates.append(number)
    return candidates


def allowed_file(filename, mimetype):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in ALLOWED_EXTENSIONS or (mimetype or '').startswith('image/')


@app.before_request
def require_auth():
    if not APP_PASSWORD:
        return None
    auth = request.authorization
    if (auth and auth.username is not None and auth.password is not None
            and hmac.compare_digest(auth.username, APP_USERNAME)
            and hmac.compare_digest(auth.password, APP_PASSWORD)):
        return None
    return Response('Přihlášení vyžadováno', 401, {'WWW-Authenticate': 'Basic realm="OCR Uploader"'})


@app.errorhandler(413)
def too_large(_):
    limit_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    return jsonify({"error": f"Soubor je příliš velký (max. {limit_mb} MB)."}), 413


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'photo' not in request.files:
        return jsonify({"error": "Chybí soubor."}), 400
    file = request.files['photo']
    if file.filename == '':
        return jsonify({"error": "Nebyl vybrán žádný soubor."}), 400

    filename = secure_filename(file.filename)
    if not allowed_file(filename, file.mimetype):
        return jsonify({"error": "Soubor není podporovaný obrázek."}), 400

    # Obrázek se zpracuje v paměti, na disk se neukládá
    content = file.read()
    if not content:
        return jsonify({"error": "Soubor je prázdný."}), 400

    try:
        response = get_vision_client().text_detection(image=vision.Image(content=content))
    except Exception:
        log.exception('Volání Google Vision API selhalo')
        return jsonify({"error": "Služba pro rozpoznávání textu není dostupná."}), 502

    if response.error.message:
        log.error('Google Vision API vrátilo chybu: %s', response.error.message)
        return jsonify({"error": "Rozpoznání textu selhalo."}), 502

    texts = response.text_annotations
    candidates = find_candidates(texts[0].description) if texts else []

    return jsonify({
        "recognized_number": candidates[0] if candidates else None,
        "candidates": candidates,
        "source_file": filename,
    })


def read_units():
    if not os.path.exists(OUTPUT_CSV):
        return []
    units = []
    with open(OUTPUT_CSV, newline='', encoding='utf-8') as file:
        for row in csv.reader(file):
            if not row or row == CSV_HEADER:
                continue
            if len(row) == 1:
                # Starší formát CSV obsahoval pouze číslo
                units.append({"timestamp": None, "number": row[0]})
            else:
                units.append({"timestamp": row[0], "number": row[1]})
    return units


@app.route('/units', methods=['GET'])
def units():
    with csv_lock:
        try:
            return jsonify({"units": read_units()})
        except OSError:
            log.exception('Čtení %s selhalo', OUTPUT_CSV)
            return jsonify({"error": "Nepodařilo se načíst seznam."}), 500


@app.route('/save', methods=['POST'])
def save():
    number = (request.form.get('number') or '').strip()
    if not VALID_NUMBER_RE.match(number):
        return jsonify({"error": "Číslo musí mít přesně 6 číslic."}), 400

    source_file = secure_filename(request.form.get('source_file') or '')
    user = request.authorization.username if APP_PASSWORD and request.authorization else ''
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')

    with csv_lock:
        try:
            write_header = not os.path.exists(OUTPUT_CSV) or os.path.getsize(OUTPUT_CSV) == 0
            with open(OUTPUT_CSV, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                if write_header:
                    writer.writerow(CSV_HEADER)
                writer.writerow([timestamp, number, source_file, user])
        except OSError:
            log.exception('Zápis do %s selhal', OUTPUT_CSV)
            return jsonify({"error": "Chyba při ukládání čísla."}), 500

    log.info('Uloženo číslo %s', number)
    return jsonify({"saved_number": number, "timestamp": timestamp}), 200


if __name__ == '__main__':
    if not APP_PASSWORD:
        log.warning('APP_PASSWORD není nastaveno – aplikace běží bez přihlášení.')
    app.run(
        debug=os.environ.get('FLASK_DEBUG') == '1',
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', '5000')),
    )
