# tests/test_hundemanager.py - Sicherung, Update und Rücknahme
#
# Läuft bei jedem Push auf Windows (GitHub Actions) - die App muss IMMER auf
# Windows 11 funktionieren. Lokal:  python -m unittest discover -s tests -v
#
# Jeder Test baut eine eigene Installation in einem Temp-Ordner und spielt
# Updates über einen nachgebauten GitHub-Server ein - echte Releases und der
# echte Dokumente-Ordner werden nie angefasst.

import http.cookiejar
import importlib.util
import io
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRAMM = ['app.py', 'updater.py', 'backup.py', 'start.py', 'requirements.txt',
            'README.txt', 'START.bat', 'templates']
WINDOWS = os.name == 'nt'


# --- Hilfsfunktionen ---

def installation_anlegen(ziel, version):
    os.makedirs(ziel)
    for eintrag in PROGRAMM:
        quelle = os.path.join(REPO, eintrag)
        if os.path.isdir(quelle):
            shutil.copytree(quelle, os.path.join(ziel, eintrag))
        else:
            shutil.copy2(quelle, ziel)
    with open(os.path.join(ziel, 'VERSION'), 'w', encoding='utf-8') as f:
        f.write(version + '\n')
    os.makedirs(os.path.join(ziel, 'instance'))
    return ziel


def db_anlegen(pfad, alt=False):
    """alt=True: Schema wie in v3 (ohne aktiv/fotofreigabe) - testet die Migration mit."""
    person_spalten = '' if alt else ', aktiv BOOLEAN DEFAULT 1, fotofreigabe BOOLEAN DEFAULT 0'
    with closing(sqlite3.connect(pfad)) as v:
        v.executescript(f'''
            CREATE TABLE person (id INTEGER PRIMARY KEY, vorname VARCHAR(100) NOT NULL,
                                 nachname VARCHAR(100) NOT NULL{person_spalten});
            CREATE TABLE hund (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, geburtstag DATE,
                gueltig_shp_dap_dhp DATE, gueltig_l DATE, gueltig_bbpi DATE, gueltig_t DATE,
                haftpflicht_gueltig BOOLEAN, bemerkung TEXT,
                person_id INTEGER NOT NULL REFERENCES person(id));
            INSERT INTO person (id, vorname, nachname) VALUES
                (1, 'Jürgen', 'Müller'), (2, 'Saskia', 'Test'), (3, 'Zoë', 'Weiß');
            INSERT INTO hund VALUES
                (1, 'Bello', '2020-01-01', '2027-01-01', NULL, NULL, NULL, 1, 'Grüße – „Spezial“', 1),
                (2, 'Luna', NULL, NULL, NULL, NULL, NULL, 0, NULL, 1),
                (3, 'Rex', NULL, NULL, NULL, NULL, NULL, 1, NULL, 2),
                (4, 'Fiete', NULL, NULL, NULL, NULL, NULL, 1, NULL, 3);
        ''')
        v.commit()


def zaehle(pfad):
    with closing(sqlite3.connect(pfad)) as v:
        return {t: v.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('person', 'hund')}


def lies_bytes(pfad):
    with open(pfad, 'rb') as f:
        return f.read()


def lade_modul(pfad, name):
    spec = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def freier_port():
    with closing(socket.socket()) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def release_zip(version, aenderungen=None):
    """ZIP wie von GitHub: alles in einem Unterordner. aenderungen: {pfad: inhalt oder None}"""
    puffer = io.BytesIO()
    praefix = 'kai-osthoff-hundemanager-abc1234/'
    aenderungen = dict(aenderungen or {})
    with zipfile.ZipFile(puffer, 'w') as zf:
        for eintrag in PROGRAMM:
            quelle = os.path.join(REPO, eintrag)
            dateien = [quelle] if os.path.isfile(quelle) else [
                os.path.join(w, d) for w, _, ds in os.walk(quelle) for d in ds if not d.endswith('.pyc')]
            for pfad in dateien:
                rel = os.path.relpath(pfad, REPO).replace(os.sep, '/')
                if rel in aenderungen:
                    inhalt = aenderungen.pop(rel)
                    if inhalt is not None:
                        zf.writestr(praefix + rel, inhalt)
                else:
                    zf.write(pfad, praefix + rel)
        zf.writestr(praefix + 'VERSION', version + '\n')
        for rel, inhalt in aenderungen.items():
            if inhalt is not None:
                zf.writestr(praefix + rel, inhalt)
    return puffer.getvalue()


class GitHubNachbau:
    """Liefert /releases/latest und das ZIP - wie die GitHub-API."""

    def __init__(self, version, zip_daten):
        nachbau = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/latest':
                    daten = json.dumps({
                        'tag_name': 'v' + nachbau.version,
                        'body': 'Testrelease',
                        'zipball_url': f'http://127.0.0.1:{nachbau.port}/zip',
                    }).encode()
                else:
                    daten = nachbau.zip_daten
                self.send_response(200)
                self.send_header('Content-Length', str(len(daten)))
                self.end_headers()
                self.wfile.write(daten)

            def log_message(self, *args):
                pass

        self.version = version
        self.zip_daten = zip_daten
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.port = self.server.server_address[1]
        self.url = f'http://127.0.0.1:{self.port}/latest'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def prozess_beenden(prozess):
    if prozess.poll() is not None:
        return
    if WINDOWS:
        # start.py startet app.py als Kindprozess - den ganzen Baum beenden
        subprocess.call(['taskkill', '/F', '/T', '/PID', str(prozess.pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        import signal
        os.killpg(prozess.pid, signal.SIGKILL)
    prozess.wait(timeout=30)


# --- Sicherungen (direkt im Prozess) ---

class SicherungTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.app_dir = installation_anlegen(os.path.join(self.tmp.name, 'Hundemanager'), '5.2.0')
        self.zweiter_ort = os.path.join(self.tmp.name, 'Dokumente', 'Hundemanager-Backups')
        os.environ['HUNDEMANAGER_BACKUP_ZWEITER_ORT'] = self.zweiter_ort
        self.backup = lade_modul(os.path.join(self.app_dir, 'backup.py'), f'backup_{id(self)}')
        db_anlegen(self.backup.DB_PFAD)

    def tearDown(self):
        os.environ.pop('HUNDEMANAGER_BACKUP_ZWEITER_ORT', None)
        self.tmp.cleanup()

    def test_sicherung_ist_vollstaendig_geprueft_und_gespiegelt(self):
        ordner, spiegel_fehler = self.backup.erstelle_backup('manuell', '5.2.0')
        self.assertIsNone(spiegel_fehler)
        manifest = self.backup.pruefe_backup(ordner)
        self.assertEqual(manifest['datensaetze'], {'hund': 4, 'person': 3})
        self.assertIn('code.zip', manifest['dateien'])
        kopie = os.path.join(self.zweiter_ort, os.path.basename(ordner))
        self.backup.pruefe_backup(kopie)
        with zipfile.ZipFile(os.path.join(ordner, 'code.zip')) as zf:
            namen = zf.namelist()
        self.assertIn('app.py', namen)
        self.assertIn('templates/index.html', namen)
        self.assertFalse(any(n.startswith('instance/') for n in namen))

    def test_sicherung_bei_geoeffneter_datenbank(self):
        # Die App hält die Datenbank offen - unter Windows ist die Datei dann gesperrt
        with closing(sqlite3.connect(self.backup.DB_PFAD)) as offen:
            offen.execute("INSERT INTO person (vorname, nachname) VALUES ('Neu', 'Person')")
            offen.commit()
            ordner, _ = self.backup.erstelle_backup('manuell', '5.2.0')
        self.assertEqual(self.backup.pruefe_backup(ordner)['datensaetze']['person'], 4)

    def test_umlaute_bleiben_erhalten(self):
        ordner, _ = self.backup.erstelle_backup('manuell', '5.2.0')
        with closing(sqlite3.connect(os.path.join(ordner, 'hundemanager.db'))) as v:
            self.assertEqual(v.execute('SELECT bemerkung FROM hund WHERE id=1').fetchone()[0],
                             'Grüße – „Spezial“')

    def test_beschaedigte_sicherung_wird_erkannt(self):
        ordner, _ = self.backup.erstelle_backup('manuell', '5.2.0')
        with open(os.path.join(ordner, 'hundemanager.db'), 'r+b') as f:
            f.seek(200)
            f.write(b'kaputt')
        with self.assertRaises(self.backup.BackupFehler):
            self.backup.pruefe_backup(ordner)

    def test_unvollstaendige_sicherung_wird_nie_angeboten(self):
        ordner, _ = self.backup.erstelle_backup('manuell', '5.2.0')
        shutil.copytree(ordner, ordner + '_2' + self.backup.UNVOLLSTAENDIG)
        self.assertEqual([b['name'] for b in self.backup.liste_backups()], [os.path.basename(ordner)])

    def test_wiederherstellen_sichert_vorher_den_aktuellen_stand(self):
        ordner, _ = self.backup.erstelle_backup('manuell', '5.2.0')
        with closing(sqlite3.connect(self.backup.DB_PFAD)) as v:
            v.execute('DELETE FROM hund')
            v.commit()
        self.backup.datenbank_wiederherstellen(ordner, '5.2.0')
        self.assertEqual(zaehle(self.backup.DB_PFAD), {'person': 3, 'hund': 4})
        vorher = [b for b in self.backup.liste_backups() if b['art'] == 'vor-wiederherstellung']
        self.assertEqual(len(vorher), 1)
        self.assertEqual(vorher[0]['datensaetze']['hund'], 0)

    def test_wiederherstellen_aus_beschaedigter_sicherung_aendert_nichts(self):
        ordner, _ = self.backup.erstelle_backup('manuell', '5.2.0')
        with open(os.path.join(ordner, 'hundemanager.db'), 'r+b') as f:
            f.seek(200)
            f.write(b'kaputt')
        with closing(sqlite3.connect(self.backup.DB_PFAD)) as v:
            v.execute('DELETE FROM hund WHERE id=4')
            v.commit()
        with self.assertRaises(self.backup.BackupFehler):
            self.backup.datenbank_wiederherstellen(ordner, '5.2.0')
        self.assertEqual(zaehle(self.backup.DB_PFAD), {'person': 3, 'hund': 3})

    def test_aufbewahrung_je_art(self):
        zaehler = iter(range(1000))
        self.backup._zeitstempel = lambda: f'2026-01-01_{next(zaehler):06d}'
        for _ in range(12):
            self.backup.erstelle_backup('vor-update', '5.2.0', mit_code=False)
        for _ in range(3):
            self.backup.erstelle_backup('taeglich', '5.2.0', mit_code=False)
        arten = [b['art'] for b in self.backup.liste_backups()]
        self.assertEqual(arten.count('vor-update'), 10)
        self.assertEqual(arten.count('taeglich'), 3)
        gespiegelt = [n for n in os.listdir(self.zweiter_ort) if n.endswith('vor-update')]
        self.assertEqual(len(gespiegelt), 10)

    def test_sicherung_scheitert_sauber(self):
        # Backup-Ordner nicht anlegbar (z.B. Datei im Weg) -> BackupFehler, kein Absturz
        os.makedirs(self.backup.INSTANCE_DIR, exist_ok=True)
        with open(self.backup.BACKUP_DIR, 'w', encoding='utf-8') as f:
            f.write('im Weg')
        with self.assertRaises(self.backup.BackupFehler):
            self.backup.erstelle_backup('manuell', '5.2.0')


# --- Updates von Ende zu Ende (echte Prozesse wie bei Saskia) ---

class UpdateTests(unittest.TestCase):
    ALT = '5.0.0'
    NEU = '9.9.9'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.app_dir = installation_anlegen(os.path.join(self.tmp.name, 'Hundemanager'), self.ALT)
        self.db = os.path.join(self.app_dir, 'instance', 'hundemanager.db')
        self.zweiter_ort = os.path.join(self.tmp.name, 'Dokumente', 'Hundemanager-Backups')
        self.port = freier_port()
        self.log_pfad = os.path.join(self.tmp.name, 'ausgabe.log')
        self.prozess = None
        self.github = None
        # Wie ein Browser: Cookies behalten, sonst gehen Flask-Meldungen verloren
        self.browser = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.app_py_vorher = lies_bytes(os.path.join(self.app_dir, 'app.py'))
        self.start_bat_vorher = lies_bytes(os.path.join(self.app_dir, 'START.bat'))

    def tearDown(self):
        if self.prozess:
            prozess_beenden(self.prozess)
        if self.github:
            self.github.stop()
        if hasattr(self, '_outcome') and self.log_pfad and os.path.exists(self.log_pfad):
            fehler = [f for f in getattr(self._outcome.result, 'failures', []) +
                      getattr(self._outcome.result, 'errors', []) if f[0] is self]
            if fehler:
                with open(self.log_pfad, encoding='utf-8', errors='replace') as f:
                    print(f'\n----- Ausgabe von {self.id()} -----\n{f.read()}')
        self.tmp.cleanup()

    def release(self, zip_daten):
        self.github = GitHubNachbau(self.NEU, zip_daten)

    def starten(self, skript='start.py'):
        env = dict(os.environ,
                   HUNDEMANAGER_PORT=str(self.port),
                   HUNDEMANAGER_RELEASES_URL=self.github.url,
                   HUNDEMANAGER_BACKUP_ZWEITER_ORT=self.zweiter_ort,
                   HUNDEMANAGER_KEIN_BROWSER='1')
        env.pop('HUNDEMANAGER_LAUNCHER', None)
        optionen = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {'start_new_session': True}
        self.log = open(self.log_pfad, 'w', encoding='utf-8')
        self.addCleanup(self.log.close)
        self.prozess = subprocess.Popen([sys.executable, skript], cwd=self.app_dir, env=env,
                                        stdout=self.log, stderr=subprocess.STDOUT, **optionen)
        self.assertEqual(self.warte_auf_version(), self.ALT)

    def url(self, pfad):
        return f'http://127.0.0.1:{self.port}{pfad}'

    def version_abfragen(self):
        with urllib.request.urlopen(self.url('/api/version'), timeout=5) as a:
            return json.load(a)['version']

    def warte_auf_version(self, timeout=90):
        ende = time.time() + timeout
        while time.time() < ende:
            try:
                return self.version_abfragen()
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.5)
        self.fail('Hundemanager antwortet nicht')

    def warte_auf_neustart(self, timeout=180):
        """Wartet, bis der Server weg war und wieder antwortet. Gibt die dann laufende Version zurück."""
        ende = time.time() + timeout
        war_weg = False
        while time.time() < ende:
            try:
                version = self.version_abfragen()
                if war_weg:
                    return version
            except (urllib.error.URLError, ConnectionError, OSError):
                war_weg = True
            time.sleep(0.5)
        self.fail('Kein Neustart nach dem Update')

    def update_klicken(self):
        anfrage = urllib.request.Request(self.url('/update/installieren'), data=b'', method='POST')
        with self.browser.open(anfrage, timeout=600) as a:
            return a.read().decode('utf-8')

    def seite(self, pfad='/'):
        with self.browser.open(self.url(pfad), timeout=10) as a:
            return a.read().decode('utf-8')

    def sicherungen(self, art):
        basis = os.path.join(self.app_dir, 'instance', 'backup')
        return [n for n in os.listdir(basis) if n.endswith('_' + art)]

    def pruefe_daten_unveraendert(self):
        self.assertEqual(zaehle(self.db), {'person': 3, 'hund': 4})
        with closing(sqlite3.connect(self.db)) as v:
            self.assertEqual(v.execute('SELECT nachname FROM person WHERE id=1').fetchone()[0], 'Müller')

    def pruefe_alte_version_wiederhergestellt(self):
        self.assertEqual(lies_bytes(os.path.join(self.app_dir, 'app.py')), self.app_py_vorher)
        with open(os.path.join(self.app_dir, 'VERSION'), encoding='utf-8') as f:
            self.assertEqual(f.read().strip(), self.ALT)
        self.assertFalse(os.path.exists(os.path.join(self.app_dir, 'instance', 'update_laeuft.json')))

    def test_update_mit_geprueftem_backup(self):
        db_anlegen(self.db, alt=True)  # alte Datenbank: Migration läuft beim Update mit
        self.release(release_zip(self.NEU))
        self.starten()

        self.assertIn('Neue Version 9.9.9', self.seite())
        self.update_klicken()
        self.assertEqual(self.warte_auf_neustart(), self.NEU)

        self.pruefe_daten_unveraendert()
        sicherungen = self.sicherungen('vor-update')
        self.assertEqual(len(sicherungen), 1)
        self.assertIn('_v5.0.0_', sicherungen[0])
        backup = lade_modul(os.path.join(self.app_dir, 'backup.py'), f'backup_{id(self)}')
        for basis in (os.path.join(self.app_dir, 'instance', 'backup'), self.zweiter_ort):
            manifest = backup.pruefe_backup(os.path.join(basis, sicherungen[0]))
            self.assertEqual(manifest['datensaetze'], {'hund': 4, 'person': 3})
        self.assertFalse(os.path.exists(os.path.join(self.app_dir, 'instance', 'update_laeuft.json')))
        self.assertEqual(lies_bytes(os.path.join(self.app_dir, 'START.bat')), self.start_bat_vorher)
        self.assertNotIn('hat nicht geklappt', self.seite())

    def test_kaputtes_programm_wird_zurueckgenommen(self):
        db_anlegen(self.db)
        with open(os.path.join(REPO, 'app.py'), encoding='utf-8') as f:
            kaputt = f.read() + '\ndas ist kein python (\n'
        self.release(release_zip(self.NEU, {'app.py': kaputt, 'neue_datei.py': 'x = 1\n'}))
        self.starten()

        self.update_klicken()
        self.assertEqual(self.warte_auf_neustart(), self.ALT)

        self.pruefe_alte_version_wiederhergestellt()
        self.pruefe_daten_unveraendert()
        self.assertFalse(os.path.exists(os.path.join(self.app_dir, 'neue_datei.py')))
        self.assertIn('hat nicht geklappt', self.seite())

    def test_selbsttest_fehler_wird_zurueckgenommen(self):
        db_anlegen(self.db)
        self.release(release_zip(self.NEU, {'templates/index.html': '{% extends "base.html" %}{% block content %}{{ kaputt( }}{% endblock %}'}))
        self.starten()

        self.update_klicken()
        self.assertEqual(self.warte_auf_neustart(), self.ALT)

        self.pruefe_alte_version_wiederhergestellt()
        self.pruefe_daten_unveraendert()
        self.assertIn('hat nicht geklappt', self.seite())

    def test_kopierfehler_wird_sofort_zurueckgenommen(self):
        db_anlegen(self.db)
        # start.py ist ein Ordner -> das Überschreiben schlägt mitten im Update fehl
        os.remove(os.path.join(self.app_dir, 'start.py'))
        os.makedirs(os.path.join(self.app_dir, 'start.py'))
        self.app_py_vorher = lies_bytes(os.path.join(self.app_dir, 'app.py'))
        self.release(release_zip(self.NEU, {'neue_datei.py': 'x = 1\n'}))
        self.starten('app.py')

        antwort = self.update_klicken()
        self.assertIn('wurde wiederhergestellt', antwort)
        self.assertEqual(self.version_abfragen(), self.ALT)
        self.pruefe_alte_version_wiederhergestellt()
        self.pruefe_daten_unveraendert()
        self.assertFalse(os.path.exists(os.path.join(self.app_dir, 'neue_datei.py')))

    def test_kein_update_ohne_backup(self):
        db_anlegen(self.db)
        self.release(release_zip(self.NEU))
        self.starten()
        # Ab jetzt kann keine Sicherung mehr angelegt werden
        backup_dir = os.path.join(self.app_dir, 'instance', 'backup')
        shutil.rmtree(backup_dir)
        with open(backup_dir, 'w', encoding='utf-8') as f:
            f.write('im Weg')

        antwort = self.update_klicken()
        self.assertIn('Sicherung nicht geklappt', antwort)
        self.assertEqual(self.version_abfragen(), self.ALT)
        self.pruefe_alte_version_wiederhergestellt()
        self.pruefe_daten_unveraendert()

    def test_wiederherstellen_ueber_die_oberflaeche(self):
        db_anlegen(self.db)
        self.release(release_zip(self.NEU))
        self.starten()
        name = self.sicherungen('taeglich')[0]  # beim Start automatisch angelegt
        with closing(sqlite3.connect(self.db)) as v:
            v.execute('DELETE FROM hund')
            v.commit()

        anfrage = urllib.request.Request(self.url('/sicherungen/wiederherstellen'),
                                         data=f'name={name}'.encode(), method='POST')
        with self.browser.open(anfrage, timeout=30) as a:
            self.assertIn('wiederhergestellt', a.read().decode('utf-8'))
        self.pruefe_daten_unveraendert()
        self.assertIn('Bello', self.seite())
        self.assertEqual(len(self.sicherungen('vor-wiederherstellung')), 1)


    def test_update_von_saskias_5_1_0(self):
        """Der echte Übergang bei Saskia: alter Updater und alter Starter aus v5.1.0."""
        shutil.rmtree(self.app_dir)
        os.makedirs(self.app_dir)
        archiv = subprocess.run(['git', 'archive', '--format=zip', 'v5.1.0'], cwd=REPO,
                                capture_output=True, check=True).stdout
        with zipfile.ZipFile(io.BytesIO(archiv)) as zf:
            zf.extractall(self.app_dir)
        os.makedirs(os.path.join(self.app_dir, 'instance'))
        db_anlegen(self.db)
        self.release(release_zip(self.NEU))
        # v5.1.0 kennt keine Umgebungsvariable für die Release-Adresse - nur für den Test umbiegen
        updater_py = os.path.join(self.app_dir, 'updater.py')
        with open(updater_py, encoding='utf-8') as f:
            inhalt = f.read()
        with open(updater_py, 'w', encoding='utf-8') as f:
            f.write(inhalt.replace(
                "f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'", repr(self.github.url)))
        self.ALT = '5.1.0'
        self.starten()

        self.update_klicken()
        self.assertEqual(self.warte_auf_neustart(), self.NEU)
        self.pruefe_daten_unveraendert()
        # Der alte Starter läuft noch -> Hinweis, einmal neu zu starten
        self.assertIn('START.bat', self.seite())
        self.assertIn('neu öffnen', self.seite())
        # Die neue Version legt sofort ihre erste geprüfte Sicherung an
        self.assertEqual(len(self.sicherungen('taeglich')), 1)


if __name__ == '__main__':
    unittest.main()
