# start.py - Startet den Hundemanager (wird von START.bat aufgerufen)
#
# - installiert fehlende Python-Pakete automatisch
# - öffnet den Browser
# - startet die App nach einem Update automatisch neu

import os
import subprocess
import sys
import threading
import webbrowser

APP_DIR = os.path.dirname(os.path.abspath(__file__))
NEUSTART_CODE = 3  # app.py beendet sich mit diesem Code, wenn ein Update installiert wurde
URL = f"http://127.0.0.1:{os.environ.get('HUNDEMANAGER_PORT', 5000)}"


def pakete_vorhanden():
    try:
        import flask, flask_sqlalchemy, dateutil, openpyxl  # noqa: F401
        return True
    except ImportError:
        return False


def main():
    if not pakete_vorhanden():
        print('Installiere benötigte Python-Pakete (einmalig) ...')
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                               '-r', os.path.join(APP_DIR, 'requirements.txt')])

    env = dict(os.environ, HUNDEMANAGER_LAUNCHER='1')
    threading.Timer(2.5, webbrowser.open, args=[URL]).start()

    while True:
        rc = subprocess.call([sys.executable, os.path.join(APP_DIR, 'app.py')], cwd=APP_DIR, env=env)
        if rc != NEUSTART_CODE:
            return rc
        print('\nUpdate installiert - Hundemanager startet neu ...\n')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
