# Hundemanager

Flask-App (SQLite) zur Verwaltung von Hunden, Impfungen und Haftpflicht.
Entwickelt wird von Kai, genutzt von Saskia.

## Plattformen – immer beachten

**Entwicklung: macOS. Produktiv: Windows 11 (Saskia).**
Alles, was ausgeliefert wird, muss unter Windows 11 funktionieren – auch wenn es
nur auf dem Mac getestet werden kann. Bei jeder Änderung prüfen:

- **Dateien immer mit `encoding='utf-8'` öffnen.** Windows nimmt sonst cp1252
  und Umlaute gehen kaputt.
- **Pfade nur mit `os.path.join`** (oder `pathlib`), nie `/` von Hand zusammensetzen.
- **`.bat`-Dateien brauchen CRLF.** `.gitattributes` erzwingt das; beim Bearbeiten
  auf dem Mac nicht mit LF überschreiben.
- **`START.bat` wird vom Updater nie überschrieben** (Windows liest laufende
  Batch-Dateien zeilenweise). Logik gehört nach `start.py`, nicht in die `.bat`.
- **Geöffnete Dateien sind unter Windows gesperrt.** Die Datenbank nicht ersetzen
  oder verschieben, solange die App läuft; Updates schreiben über Temp-Datei + `os.replace`.
- **Python heißt bei Saskia `python`** (python.org-Installer, „Add to PATH“). Kein
  `python3`, keine Shell-Skripte, keine macOS-/Unix-only-Tools in der App.
- **Nur Python-Standardbibliothek** für Updater und Starter – bei Saskia ist nichts
  außer `requirements.txt` installiert.
- Nicht unter Windows Getestetes in der Antwort an Kai offen als
  „nur auf dem Mac getestet“ benennen.

## Lokal entwickeln (macOS)

- Port 5000 ist auf dem Mac von AirPlay belegt → `HUNDEMANAGER_PORT=5050 .venv/bin/python start.py`
- Saskia läuft immer auf Port 5000.

## Daten

- Saskias Daten liegen ausschließlich in `instance/hundemanager.db` – nie im Repo
  (`.gitignore`), vom Updater nie angefasst.
- Neue Spalten in Modellen: `migriere_datenbank()` in `app.py` ergänzt sie beim
  Start automatisch (mit Backup). Spalten nur nullable oder mit Default anlegen;
  Umbenennen/Löschen von Spalten braucht eine eigene Migration.

## Releases

- `./release.sh X.Y.Z "Notizen"` – setzt `VERSION`, taggt, pusht, legt das
  GitHub-Release an. Die Notizen sieht Saskia im Update-Hinweis, also verständlich
  und auf Deutsch formulieren.
- Saskias App prüft `releases/latest` von `kai-osthoff/hundemanager` und installiert
  per Button. Ein kaputtes Release landet direkt bei ihr – vorher lokal testen.
