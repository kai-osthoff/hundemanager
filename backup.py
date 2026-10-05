# backup.py - Sicherungen von Datenbank und Programm
#
# Grundsätze:
#   - Die Datenbank wird über die SQLite-Backup-API kopiert - das ergibt auch
#     bei laufender App eine konsistente Kopie (eine einfache Dateikopie nicht).
#   - Jede Sicherung wird nach dem Schreiben geprüft (Integrität, Anzahl
#     Datensätze, Prüfsummen). Erst dann gilt sie als fertig.
#   - Unfertige Sicherungen liegen in Ordnern mit Endung ".unvollstaendig"
#     und werden nie zum Wiederherstellen angeboten.
#   - Jede Sicherung wird zusätzlich in den Dokumente-Ordner gespiegelt, damit
#     sie auch dann noch da ist, wenn der Programmordner verloren geht.
#
# Nur Standardbibliothek: start.py braucht dieses Wissen auch, wenn Flask
# oder die neue Programmversion kaputt sind.

import hashlib
import json
import os
import shutil
import sqlite3
import time
import zipfile
from contextlib import closing
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(APP_DIR, 'instance')
DB_PFAD = os.path.join(INSTANCE_DIR, 'hundemanager.db')
BACKUP_DIR = os.path.join(INSTANCE_DIR, 'backup')
UPDATE_MARKER = os.path.join(INSTANCE_DIR, 'update_laeuft.json')
UPDATE_FEHLGESCHLAGEN = os.path.join(INSTANCE_DIR, 'update_fehlgeschlagen.json')

DB_DATEI = 'hundemanager.db'
CODE_DATEI = 'code.zip'
MANIFEST_DATEI = 'manifest.json'
UNVOLLSTAENDIG = '.unvollstaendig'

# Wie viele Sicherungen je Art aufbewahrt werden
AUFBEWAHRUNG = {
    'vor-update': 10,
    'taeglich': 30,
    'manuell': 20,
    'vor-wiederherstellung': 10,
    'vor-migration': 10,
}
ARTEN_TEXT = {
    'vor-update': 'Vor Update',
    'taeglich': 'Täglich',
    'manuell': 'Manuell',
    'vor-wiederherstellung': 'Vor Wiederherstellung',
    'vor-migration': 'Vor Datenbank-Anpassung',
}

# Nie in die Code-Sicherung und beim Zurückspielen nie überschreiben
NICHT_IM_CODE = {'instance', '.venv', '.git', '__pycache__'}
NIE_UEBERSCHREIBEN = NICHT_IM_CODE | {'START.bat'}


class BackupFehler(Exception):
    pass


# --- Orte ---

def zweiter_ort():
    """Dokumente\\Hundemanager-Backups - unter Windows auch, wenn OneDrive den Ordner umgeleitet hat."""
    eigener = os.environ.get('HUNDEMANAGER_BACKUP_ZWEITER_ORT')
    if eigener:
        return eigener
    if os.name == 'nt':
        try:
            import ctypes
            puffer = ctypes.create_unicode_buffer(260)
            CSIDL_PERSONAL = 5  # "Dokumente", folgt Umleitungen (OneDrive)
            if ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, 0, puffer) == 0:
                return os.path.join(puffer.value, 'Hundemanager-Backups')
        except Exception:
            pass
    return os.path.join(os.path.expanduser('~'), 'Documents', 'Hundemanager-Backups')


# --- Hilfsfunktionen ---

def _mit_wiederholung(funktion, *args, versuche=6):
    """Windows sperrt frisch geschriebene Dateien manchmal kurz (Virenscanner, OneDrive)."""
    for versuch in range(versuche):
        try:
            return funktion(*args)
        except PermissionError:
            if versuch == versuche - 1:
                raise
            time.sleep(0.5 * (versuch + 1))


def _sha256(pfad):
    h = hashlib.sha256()
    with open(pfad, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _db_zaehler(pfad):
    """Anzahl Datensätze je Tabelle - zum Vergleich von Original und Kopie."""
    with closing(sqlite3.connect(pfad)) as verbindung:
        tabellen = [z[0] for z in verbindung.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t: verbindung.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tabellen}


def _db_integritaet(pfad):
    with closing(sqlite3.connect(pfad)) as verbindung:
        return verbindung.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def _db_kopieren(quelle, ziel):
    """Konsistente Kopie über die SQLite-Backup-API (funktioniert auch bei geöffneter Datenbank)."""
    with closing(sqlite3.connect(quelle, timeout=30)) as q, closing(sqlite3.connect(ziel, timeout=30)) as z:
        q.backup(z)


def _code_dateien():
    for wurzel, ordner, dateien in os.walk(APP_DIR):
        ordner[:] = [o for o in ordner if o not in NICHT_IM_CODE]
        for datei in dateien:
            if datei.endswith('.pyc') or datei.endswith('.update-tmp'):
                continue
            pfad = os.path.join(wurzel, datei)
            yield pfad, os.path.relpath(pfad, APP_DIR).replace(os.sep, '/')


def _zeitstempel():
    return datetime.now().strftime('%Y-%m-%d_%H%M%S')


# --- Sicherung erstellen ---

def erstelle_backup(art, version, mit_code=True):
    """Erstellt und prüft eine Sicherung. Gibt den Ordner zurück oder wirft BackupFehler.

    Ist eine Sicherung nicht nachweislich vollständig, gibt es keinen Ordner ohne
    ".unvollstaendig" - wer das Ergebnis nutzt, kann sich also darauf verlassen.
    """
    if art not in AUFBEWAHRUNG:
        raise ValueError(f'Unbekannte Sicherungsart: {art}')
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        name = f'{_zeitstempel()}_v{version}_{art}'
        ziel = os.path.join(BACKUP_DIR, name)
        while os.path.exists(ziel) or os.path.exists(ziel + UNVOLLSTAENDIG):  # gleiche Sekunde
            time.sleep(1)
            name = f'{_zeitstempel()}_v{version}_{art}'
            ziel = os.path.join(BACKUP_DIR, name)
        arbeit = ziel + UNVOLLSTAENDIG
        os.makedirs(arbeit)
    except OSError as e:
        raise BackupFehler(f'Sicherungsordner nicht beschreibbar ({e.__class__.__name__}: {e})') from e

    try:
        manifest = {
            'art': art,
            'version': version,
            'erstellt': datetime.now().isoformat(timespec='seconds'),
            'dateien': {},
            'datensaetze': None,
        }

        if os.path.exists(DB_PFAD):
            db_kopie = os.path.join(arbeit, DB_DATEI)
            # Bei gleichzeitigem Schreiben kann die Zählung abweichen - dann erneut sichern
            for versuch in range(3):
                _db_kopieren(DB_PFAD, db_kopie)
                if not _db_integritaet(db_kopie):
                    raise BackupFehler('Die Kopie der Datenbank ist beschädigt.')
                zaehler_kopie = _db_zaehler(db_kopie)
                if zaehler_kopie == _db_zaehler(DB_PFAD):
                    break
                time.sleep(0.5)
            else:
                raise BackupFehler('Die Datenbank-Kopie stimmt nicht mit dem Original überein.')
            manifest['datensaetze'] = zaehler_kopie

        if mit_code:
            code_zip = os.path.join(arbeit, CODE_DATEI)
            with zipfile.ZipFile(code_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for pfad, rel in _code_dateien():
                    zf.write(pfad, rel)

        for datei in os.listdir(arbeit):
            manifest['dateien'][datei] = _sha256(os.path.join(arbeit, datei))
        with open(os.path.join(arbeit, MANIFEST_DATEI), 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        pruefe_backup(arbeit)
        _mit_wiederholung(os.replace, arbeit, ziel)
    except BackupFehler:
        shutil.rmtree(arbeit, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(arbeit, ignore_errors=True)
        raise BackupFehler(f'Sicherung fehlgeschlagen ({e.__class__.__name__}: {e})') from e

    spiegel_fehler = _spiegeln(ziel)
    aufraeumen()
    return ziel, spiegel_fehler


def _spiegeln(ordner):
    """Kopie in den Dokumente-Ordner. Ein Fehler hier blockiert nichts, wird aber gemeldet."""
    try:
        basis = zweiter_ort()
        os.makedirs(basis, exist_ok=True)
        ziel = os.path.join(basis, os.path.basename(ordner))
        arbeit = ziel + UNVOLLSTAENDIG
        shutil.rmtree(arbeit, ignore_errors=True)
        shutil.copytree(ordner, arbeit)
        pruefe_backup(arbeit)
        _mit_wiederholung(os.replace, arbeit, ziel)
        return None
    except Exception as e:
        return f'Zweite Kopie im Dokumente-Ordner fehlgeschlagen ({e.__class__.__name__})'


# --- Sicherung prüfen ---

def lies_manifest(ordner):
    with open(os.path.join(ordner, MANIFEST_DATEI), encoding='utf-8') as f:
        return json.load(f)


def pruefe_backup(ordner):
    """Prüft eine Sicherung vollständig. Wirft BackupFehler, wenn etwas nicht stimmt."""
    try:
        manifest = lies_manifest(ordner)
    except (OSError, ValueError) as e:
        raise BackupFehler(f'Sicherung ohne lesbares Manifest ({e.__class__.__name__})')

    for datei, pruefsumme in manifest['dateien'].items():
        pfad = os.path.join(ordner, datei)
        if not os.path.exists(pfad):
            raise BackupFehler(f'In der Sicherung fehlt {datei}.')
        if _sha256(pfad) != pruefsumme:
            raise BackupFehler(f'{datei} in der Sicherung ist verändert oder beschädigt.')

    if manifest['datensaetze'] is not None:
        db_kopie = os.path.join(ordner, DB_DATEI)
        if not _db_integritaet(db_kopie):
            raise BackupFehler('Die gesicherte Datenbank ist beschädigt.')
        if _db_zaehler(db_kopie) != manifest['datensaetze']:
            raise BackupFehler('Die gesicherte Datenbank ist unvollständig.')

    if CODE_DATEI in manifest['dateien']:
        with zipfile.ZipFile(os.path.join(ordner, CODE_DATEI)) as zf:
            if zf.testzip() is not None:
                raise BackupFehler('Die Programm-Sicherung ist beschädigt.')
    return manifest


# --- Auflisten und Aufräumen ---

def _backups_in(basis):
    if not os.path.isdir(basis):
        return []
    ergebnis = []
    for name in os.listdir(basis):
        ordner = os.path.join(basis, name)
        if name.endswith(UNVOLLSTAENDIG) or not os.path.isdir(ordner):
            continue
        try:
            manifest = lies_manifest(ordner)
        except (OSError, ValueError):
            continue
        ergebnis.append({'name': name, 'ordner': ordner, **manifest})
    return sorted(ergebnis, key=lambda b: b['name'], reverse=True)


def liste_backups():
    """Alle Sicherungen im Programmordner, neueste zuerst."""
    gespiegelt = {b['name'] for b in _backups_in(zweiter_ort())}
    backups = _backups_in(BACKUP_DIR)
    for b in backups:
        b['art_text'] = ARTEN_TEXT.get(b['art'], b['art'])
        b['gespiegelt'] = b['name'] in gespiegelt
    return backups


def finde_backup(name):
    """Sucht eine Sicherung über ihren Namen - nur aus der Liste, nie über freie Pfade."""
    for basis in (BACKUP_DIR, zweiter_ort()):
        for b in _backups_in(basis):
            if b['name'] == name:
                return b['ordner']
    raise BackupFehler('Diese Sicherung gibt es nicht.')


def aufraeumen():
    """Alte Sicherungen löschen - je Art getrennt, die neueste Sicherung bleibt immer."""
    geschuetzt = set()
    marker = lies_update_marker()
    if marker:
        geschuetzt.add(marker['backup'])

    for basis in (BACKUP_DIR, zweiter_ort()):
        backups = _backups_in(basis)
        if backups:
            geschuetzt.add(backups[0]['name'])
        for art, anzahl in AUFBEWAHRUNG.items():
            dieser_art = [b for b in backups if b['art'] == art]
            for b in dieser_art[anzahl:]:
                if b['name'] not in geschuetzt:
                    shutil.rmtree(b['ordner'], ignore_errors=True)
        # Reste abgebrochener Sicherungen (älter als 1 Tag)
        if os.path.isdir(basis):
            for name in os.listdir(basis):
                pfad = os.path.join(basis, name)
                if name.endswith(UNVOLLSTAENDIG) and time.time() - os.path.getmtime(pfad) > 86400:
                    shutil.rmtree(pfad, ignore_errors=True)


def taegliches_backup_faellig():
    heute = datetime.now().strftime('%Y-%m-%d')
    return not any(b['art'] == 'taeglich' and b['name'].startswith(heute)
                   for b in _backups_in(BACKUP_DIR))


# --- Wiederherstellen ---

def datenbank_wiederherstellen(ordner, version):
    """Spielt die Datenbank einer Sicherung zurück. Der aktuelle Stand wird vorher selbst gesichert."""
    manifest = pruefe_backup(ordner)
    if manifest['datensaetze'] is None:
        raise BackupFehler('Diese Sicherung enthält keine Datenbank.')

    if os.path.exists(DB_PFAD):
        erstelle_backup('vor-wiederherstellung', version)

    os.makedirs(INSTANCE_DIR, exist_ok=True)
    _db_kopieren(os.path.join(ordner, DB_DATEI), DB_PFAD)
    if not _db_integritaet(DB_PFAD) or _db_zaehler(DB_PFAD) != manifest['datensaetze']:
        raise BackupFehler('Wiederherstellung konnte nicht bestätigt werden.')
    return manifest


def code_wiederherstellen(ordner, neue_dateien=()):
    """Spielt die Programmdateien einer Sicherung zurück (Daten in instance/ bleiben unberührt)."""
    manifest = pruefe_backup(ordner)
    if CODE_DATEI not in manifest['dateien']:
        raise BackupFehler('Diese Sicherung enthält kein Programm.')

    with zipfile.ZipFile(os.path.join(ordner, CODE_DATEI)) as zf:
        vorhanden = set(zf.namelist())
        for rel in vorhanden:
            if rel.endswith('/') or rel.split('/')[0] in NIE_UEBERSCHREIBEN:
                continue
            ziel = os.path.join(APP_DIR, *rel.split('/'))
            os.makedirs(os.path.dirname(ziel), exist_ok=True)
            tmp = ziel + '.update-tmp'
            with zf.open(rel) as q, open(tmp, 'wb') as z:
                shutil.copyfileobj(q, z)
            _mit_wiederholung(os.replace, tmp, ziel)

    # Dateien, die erst mit dem fehlgeschlagenen Update dazukamen, wieder entfernen
    for rel in neue_dateien:
        if rel not in vorhanden and rel.split('/')[0] not in NIE_UEBERSCHREIBEN:
            pfad = os.path.join(APP_DIR, *rel.split('/'))
            if os.path.isfile(pfad):
                os.remove(pfad)


# --- Update-Marker: zeigt an, dass ein Update noch nicht bestätigt ist ---

def schreibe_update_marker(daten):
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    tmp = UPDATE_MARKER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)
    _mit_wiederholung(os.replace, tmp, UPDATE_MARKER)


def lies_update_marker():
    try:
        with open(UPDATE_MARKER, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def entferne_update_marker():
    if os.path.exists(UPDATE_MARKER):
        os.remove(UPDATE_MARKER)


def update_zuruecknehmen(grund):
    """Stellt Programm und Datenbank aus der Sicherung vor dem Update wieder her."""
    marker = lies_update_marker()
    if not marker:
        return False
    ordner = os.path.join(BACKUP_DIR, marker['backup'])
    pruefe_backup(ordner)
    try:
        # Den kaputten Zustand zur Analyse festhalten - darf die Rücknahme aber nie verhindern
        erstelle_backup('vor-wiederherstellung', marker.get('neue_version', 'unbekannt'))
    except Exception:
        pass
    code_wiederherstellen(ordner, marker.get('neue_dateien', []))
    if lies_manifest(ordner)['datensaetze'] is not None:
        _db_kopieren(os.path.join(ordner, DB_DATEI), DB_PFAD)
    with open(UPDATE_FEHLGESCHLAGEN, 'w', encoding='utf-8') as f:
        json.dump({
            'version': marker.get('neue_version'),
            'zurueck_auf': marker.get('alte_version'),
            'grund': grund,
            'zeit': datetime.now().isoformat(timespec='seconds'),
        }, f, ensure_ascii=False, indent=2)
    entferne_update_marker()
    return True
