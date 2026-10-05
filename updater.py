# updater.py - Updates von GitHub prüfen und installieren
#
# Ablauf beim Update:
#   1. Datenbank und aktuellen Code nach instance/backup/ sichern
#   2. Neue Version (GitHub Release) als ZIP herunterladen
#   3. Code-Dateien überschreiben - instance/ (Daten) wird NIE angefasst
#   4. Python-Pakete aus requirements.txt nachinstallieren
#   5. App neu starten (übernimmt app.py)

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from datetime import datetime

GITHUB_REPO = 'kai-osthoff/hundemanager'
RELEASES_URL = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
PRUEF_INTERVALL = 6 * 60 * 60  # alle 6 Stunden automatisch nachsehen
MAX_BACKUPS = 20

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(APP_DIR, 'instance', 'backup')

# Diese Pfade werden beim Update nie überschrieben.
# START.bat läuft während des Updates noch - Windows liest Batch-Dateien
# zeilenweise von der Platte, ein Überschreiben würde sie durcheinanderbringen.
GESCHUETZT = {'instance', '.venv', '.git', 'START.bat'}

_status = {
    'geprueft_um': 0,
    'verfuegbar': False,
    'version': None,
    'notizen': '',
    'zip_url': None,
    'fehler': None,
}
_status_lock = threading.Lock()
_install_lock = threading.Lock()


def aktuelle_version():
    try:
        with open(os.path.join(APP_DIR, 'VERSION'), encoding='utf-8') as f:
            return f.read().strip()
    except OSError:
        return '0.0.0'


def _versions_tupel(version):
    """'v5.1.0' -> (5, 1, 0)"""
    teile = []
    for teil in version.strip().lstrip('vV').split('.'):
        ziffern = ''.join(z for z in teil if z.isdigit())
        teile.append(int(ziffern) if ziffern else 0)
    return tuple(teile)


def update_status():
    with _status_lock:
        return dict(_status)


def pruefe_auf_update(erzwingen=False):
    """Fragt GitHub nach dem neuesten Release. Ohne Internet passiert einfach nichts."""
    with _status_lock:
        if not erzwingen and time.time() - _status['geprueft_um'] < PRUEF_INTERVALL:
            return dict(_status)

    try:
        anfrage = urllib.request.Request(RELEASES_URL, headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'hundemanager-updater',
        })
        with urllib.request.urlopen(anfrage, timeout=8) as antwort:
            release = json.load(antwort)

        neueste = release['tag_name']
        ergebnis = {
            'verfuegbar': _versions_tupel(neueste) > _versions_tupel(aktuelle_version()),
            'version': neueste.lstrip('vV'),
            'notizen': release.get('body') or '',
            'zip_url': release['zipball_url'],
            'fehler': None,
        }
    except Exception as e:
        ergebnis = {'fehler': f'Update-Prüfung nicht möglich ({e.__class__.__name__})'}

    with _status_lock:
        _status.update(ergebnis)
        _status['geprueft_um'] = time.time()
        return dict(_status)


def starte_hintergrund_pruefung():
    """Prüft beim Start und danach regelmäßig, ohne die Seite zu bremsen."""
    def schleife():
        while True:
            pruefe_auf_update(erzwingen=True)
            time.sleep(PRUEF_INTERVALL)

    threading.Thread(target=schleife, daemon=True).start()


def _zeitstempel():
    return datetime.now().strftime('%Y-%m-%d_%H%M%S')


def _alte_backups_aufraeumen():
    dateien = sorted(
        (os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)),
        key=os.path.getmtime,
    )
    for pfad in dateien[:-MAX_BACKUPS]:
        os.remove(pfad)


def sichere_datenbank(db_pfad, anlass):
    """Kopiert die Datenbank nach instance/backup/. Gibt den Backup-Pfad zurück."""
    if not db_pfad or not os.path.exists(db_pfad):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ziel = os.path.join(
        BACKUP_DIR, f'hundemanager_{_zeitstempel()}_v{aktuelle_version()}_{anlass}.db')
    shutil.copy2(db_pfad, ziel)
    _alte_backups_aufraeumen()
    return ziel


def _sichere_code():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ziel = os.path.join(BACKUP_DIR, f'code_{_zeitstempel()}_v{aktuelle_version()}.zip')
    with zipfile.ZipFile(ziel, 'w', zipfile.ZIP_DEFLATED) as zf:
        for wurzel, ordner, dateien in os.walk(APP_DIR):
            rel_wurzel = os.path.relpath(wurzel, APP_DIR)
            if rel_wurzel == '.':
                ordner[:] = [o for o in ordner if o not in GESCHUETZT and o != '__pycache__']
            else:
                ordner[:] = [o for o in ordner if o != '__pycache__']
            for datei in dateien:
                pfad = os.path.join(wurzel, datei)
                zf.write(pfad, os.path.relpath(pfad, APP_DIR))
    return ziel


def _kopiere_neue_dateien(quelle):
    for wurzel, ordner, dateien in os.walk(quelle):
        rel_wurzel = os.path.relpath(wurzel, quelle)
        if rel_wurzel == '.':
            ordner[:] = [o for o in ordner if o not in GESCHUETZT]
            dateien = [d for d in dateien if d not in GESCHUETZT]
        ziel_ordner = os.path.join(APP_DIR, rel_wurzel)
        os.makedirs(ziel_ordner, exist_ok=True)
        for datei in dateien:
            ziel = os.path.join(ziel_ordner, datei)
            tmp = ziel + '.update-tmp'
            shutil.copy2(os.path.join(wurzel, datei), tmp)
            os.replace(tmp, ziel)


def _installiere_pakete():
    anforderungen = os.path.join(APP_DIR, 'requirements.txt')
    if not os.path.exists(anforderungen):
        return
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '-q',
         '-r', anforderungen],
        check=True, timeout=600,
    )


def installiere_update(db_pfad):
    """Installiert das neueste Release. Gibt (erfolg, meldung) zurück."""
    if not _install_lock.acquire(blocking=False):
        return False, 'Ein Update läuft bereits.'
    try:
        info = pruefe_auf_update(erzwingen=True)
        if info.get('fehler'):
            return False, info['fehler']
        if not info['verfuegbar']:
            return False, 'Es ist bereits die neueste Version installiert.'

        sichere_datenbank(db_pfad, 'vor-update')
        _sichere_code()

        with tempfile.TemporaryDirectory() as tmp:
            zip_pfad = os.path.join(tmp, 'update.zip')
            anfrage = urllib.request.Request(
                info['zip_url'], headers={'User-Agent': 'hundemanager-updater'})
            with urllib.request.urlopen(anfrage, timeout=60) as antwort, \
                    open(zip_pfad, 'wb') as f:
                shutil.copyfileobj(antwort, f)

            entpackt = os.path.join(tmp, 'neu')
            with zipfile.ZipFile(zip_pfad) as zf:
                zf.extractall(entpackt)

            # GitHub packt alles in einen Unterordner "kai-osthoff-hundemanager-<hash>/"
            inhalt = os.listdir(entpackt)
            quelle = os.path.join(entpackt, inhalt[0]) if len(inhalt) == 1 else entpackt
            if not os.path.exists(os.path.join(quelle, 'app.py')):
                return False, 'Das Update-Paket ist unvollständig - nichts wurde verändert.'

            _kopiere_neue_dateien(quelle)

        try:
            _installiere_pakete()
        except Exception as e:
            return True, (f'Version {info["version"]} installiert, aber Python-Pakete konnten '
                          f'nicht aktualisiert werden ({e.__class__.__name__}).')

        return True, f'Version {info["version"]} wurde installiert.'
    except Exception as e:
        return False, f'Update fehlgeschlagen ({e.__class__.__name__}: {e})'
    finally:
        _install_lock.release()
