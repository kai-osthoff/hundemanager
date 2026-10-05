# start.py - Startet den Hundemanager (wird von START.bat aufgerufen)
#
# - installiert fehlende Python-Pakete automatisch
# - öffnet den Browser
# - startet die App nach einem Update neu
# - Sicherheitsnetz: Startet die App nach einem Update nicht sauber, werden
#   Programm und Datenbank automatisch aus der Sicherung wiederhergestellt.

import os
import subprocess
import sys
import threading
import webbrowser

# Wird beim Start einmal geladen und bleibt im Speicher - so funktioniert die
# Wiederherstellung auch dann, wenn ein Update backup.py auf der Platte kaputt macht.
import backup

APP_DIR = os.path.dirname(os.path.abspath(__file__))
NEUSTART_CODE = 3  # app.py beendet sich mit diesem Code, wenn ein Update installiert wurde
# Version des Start-Protokolls - app.py erkennt daran, ob dieser Starter Updates absichern kann
LAUNCHER_PROTOKOLL = '2'
URL = f"http://127.0.0.1:{os.environ.get('HUNDEMANAGER_PORT', 5000)}"


def pakete_vorhanden():
    try:
        import flask, flask_sqlalchemy, dateutil, openpyxl  # noqa: F401
        return True
    except ImportError:
        return False


def update_zuruecknehmen(rc):
    print(f'\nDie neue Version startet nicht (Fehlercode {rc}).')
    print('Stelle die vorherige Version und die Daten aus der Sicherung wieder her ...')
    try:
        backup.update_zuruecknehmen(f'Die neue Version ist nicht gestartet (Fehlercode {rc}).')
        print('Wiederhergestellt. Der Hundemanager startet mit der vorherigen Version.\n')
        return True
    except Exception as e:
        print(f'\nWIEDERHERSTELLUNG FEHLGESCHLAGEN: {e}')
        print(f'Die Sicherung liegt in {backup.BACKUP_DIR} - bitte Kai Bescheid geben.')
        return False


def main(nach_update=False):
    if not pakete_vorhanden():
        print('Installiere benötigte Python-Pakete (einmalig) ...')
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                               '-r', os.path.join(APP_DIR, 'requirements.txt')])

    env = dict(os.environ, HUNDEMANAGER_LAUNCHER=LAUNCHER_PROTOKOLL)
    if not nach_update and not os.environ.get('HUNDEMANAGER_KEIN_BROWSER'):
        threading.Timer(2.5, webbrowser.open, args=[URL]).start()

    while True:
        rc = subprocess.call([sys.executable, os.path.join(APP_DIR, 'app.py')], cwd=APP_DIR, env=env)

        if rc == NEUSTART_CODE:
            print('\nUpdate installiert - Hundemanager startet neu ...\n')
            # Die neue start.py übernehmen lassen, damit auch deren Verbesserungen greifen
            rc = subprocess.call([sys.executable, os.path.join(APP_DIR, 'start.py'), '--nach-update'],
                                 cwd=APP_DIR)
            if rc in (0, NEUSTART_CODE) or backup.lies_update_marker() is None:
                return rc

        if rc != 0 and backup.lies_update_marker() is not None:
            if update_zuruecknehmen(rc):
                continue
        return rc


if __name__ == '__main__':
    try:
        sys.exit(main(nach_update='--nach-update' in sys.argv))
    except KeyboardInterrupt:
        sys.exit(0)
