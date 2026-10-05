# updater.py - Updates von GitHub prüfen und installieren
#
# Ablauf beim Update - bricht ein Schritt ab, wird nichts verändert bzw. zurückgenommen:
#   1. Sicherung von Datenbank und Programm erstellen und prüfen (backup.py)
#      -> schlägt das fehl, gibt es KEIN Update
#   2. Neue Version (GitHub Release) herunterladen und auf Vollständigkeit prüfen
#   3. Update-Marker schreiben (update_laeuft.json)
#   4. Programmdateien austauschen - instance/ (Daten) wird NIE angefasst
#      -> Fehler beim Kopieren: Programm sofort aus der Sicherung zurückspielen
#   5. Python-Pakete nachinstallieren, App neu starten
#   6. Die neue Version prüft sich beim Start selbst (app.py). Klappt das nicht,
#      stellt start.py Programm und Datenbank aus der Sicherung wieder her.

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

import backup

GITHUB_REPO = 'kai-osthoff/hundemanager'
RELEASES_URL = os.environ.get(
    'HUNDEMANAGER_RELEASES_URL', f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest')
PRUEF_INTERVALL = 6 * 60 * 60  # alle 6 Stunden automatisch nachsehen

APP_DIR = backup.APP_DIR
# Pflichtdateien - fehlt eine im Download, wird das Update gar nicht erst begonnen
PFLICHTDATEIEN = ['app.py', 'updater.py', 'backup.py', 'nachweise.py', 'start.py', 'VERSION', 'requirements.txt']

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


def starte_hintergrund_pruefung(taeglich_sichern=None):
    """Prüft beim Start und danach regelmäßig, ohne die Seite zu bremsen."""
    def schleife():
        while True:
            pruefe_auf_update(erzwingen=True)
            if taeglich_sichern:
                taeglich_sichern()
            time.sleep(PRUEF_INTERVALL)

    threading.Thread(target=schleife, daemon=True).start()


def _lade_herunter(url, ziel):
    anfrage = urllib.request.Request(url, headers={'User-Agent': 'hundemanager-updater'})
    with urllib.request.urlopen(anfrage, timeout=60) as antwort, open(ziel, 'wb') as f:
        shutil.copyfileobj(antwort, f)


def _kopiere_neue_dateien(quelle, neue_dateien):
    """Überschreibt die Programmdateien. Merkt sich, welche Dateien neu dazukommen."""
    for wurzel, ordner, dateien in os.walk(quelle):
        rel_wurzel = os.path.relpath(wurzel, quelle)
        if rel_wurzel == '.':
            ordner[:] = [o for o in ordner if o not in backup.NIE_UEBERSCHREIBEN]
            dateien = [d for d in dateien if d not in backup.NIE_UEBERSCHREIBEN]
        ziel_ordner = os.path.normpath(os.path.join(APP_DIR, rel_wurzel))
        os.makedirs(ziel_ordner, exist_ok=True)
        for datei in dateien:
            ziel = os.path.join(ziel_ordner, datei)
            if not os.path.exists(ziel):
                neue_dateien.append(os.path.relpath(ziel, APP_DIR).replace(os.sep, '/'))
            tmp = ziel + '.update-tmp'
            shutil.copy2(os.path.join(wurzel, datei), tmp)
            backup._mit_wiederholung(os.replace, tmp, ziel)


def _installiere_pakete():
    anforderungen = os.path.join(APP_DIR, 'requirements.txt')
    if not os.path.exists(anforderungen):
        return
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '-q',
         '-r', anforderungen],
        check=True, timeout=600,
    )


def installiere_update():
    """Installiert das neueste Release. Gibt (erfolg, meldung) zurück."""
    if not _install_lock.acquire(blocking=False):
        return False, 'Ein Update läuft bereits.'
    try:
        info = pruefe_auf_update(erzwingen=True)
        if info.get('fehler'):
            return False, info['fehler']
        if not info['verfuegbar']:
            return False, 'Es ist bereits die neueste Version installiert.'

        alte_version = aktuelle_version()

        # 1. Sicherung - ohne geprüfte Sicherung kein Update
        try:
            sicherung, _ = backup.erstelle_backup('vor-update', alte_version)
        except backup.BackupFehler as e:
            return False, f'Update abgebrochen, weil die Sicherung nicht geklappt hat: {e} Es wurde nichts verändert.'

        with tempfile.TemporaryDirectory() as tmp:
            # 2. Herunterladen und prüfen
            try:
                zip_pfad = os.path.join(tmp, 'update.zip')
                _lade_herunter(info['zip_url'], zip_pfad)
                entpackt = os.path.join(tmp, 'neu')
                with zipfile.ZipFile(zip_pfad) as zf:
                    if zf.testzip() is not None:
                        raise ValueError('ZIP beschädigt')
                    zf.extractall(entpackt)
            except Exception as e:
                return False, f'Download fehlgeschlagen ({e.__class__.__name__}) - es wurde nichts verändert.'

            # GitHub packt alles in einen Unterordner "kai-osthoff-hundemanager-<hash>/"
            inhalt = os.listdir(entpackt)
            quelle = os.path.join(entpackt, inhalt[0]) if len(inhalt) == 1 else entpackt
            fehlend = [d for d in PFLICHTDATEIEN if not os.path.isfile(os.path.join(quelle, d))]
            if fehlend:
                return False, f'Das Update-Paket ist unvollständig ({", ".join(fehlend)} fehlt) - es wurde nichts verändert.'

            # 3. Marker - ab hier gilt das Update als "unbestätigt"
            marker = {
                'backup': os.path.basename(sicherung),
                'alte_version': alte_version,
                'neue_version': info['version'],
                'neue_dateien': [],
            }
            backup.schreibe_update_marker(marker)

            # 4. Dateien austauschen
            try:
                _kopiere_neue_dateien(quelle, marker['neue_dateien'])
                backup.schreibe_update_marker(marker)
            except Exception as e:
                backup.code_wiederherstellen(sicherung, marker['neue_dateien'])
                backup.entferne_update_marker()
                return False, (f'Update fehlgeschlagen beim Kopieren ({e.__class__.__name__}). '
                               f'Version {alte_version} wurde wiederhergestellt, deine Daten sind unverändert.')

        # 5. Pakete - schlägt das fehl, fängt der Selbsttest beim Neustart es ab
        try:
            _installiere_pakete()
        except Exception as e:
            print(f'Warnung: Python-Pakete konnten nicht aktualisiert werden ({e})')

        return True, f'Version {info["version"]} wurde installiert.'
    except Exception as e:
        return False, f'Update fehlgeschlagen ({e.__class__.__name__}: {e})'
    finally:
        _install_lock.release()
