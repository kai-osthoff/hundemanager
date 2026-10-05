# Hundemanager

Flask-App (SQLite) zur Verwaltung von Hunden, Impfungen und Haftpflicht.
Entwickelt wird von Kai, genutzt von Saskia.

## ⚠️ OBERSTE PROJEKTREGEL: Es muss IMMER auf Windows 11 funktionieren

**Keine Ausnahme.** Saskia nutzt Windows 11 – das ist die einzige Plattform, die zählt.
Entwickelt wird auf macOS, aber „läuft auf dem Mac“ heißt **nicht** fertig.

- Jede Änderung, jede Datei, jedes Release wird zuerst danach beurteilt, ob sie
  unter Windows 11 funktioniert. Im Zweifel die Windows-sichere Lösung wählen,
  auch wenn sie auf dem Mac umständlicher ist.
- Ein Update kommt per Button direkt bei Saskia an. **Kein Release, solange nicht
  sicher ist, dass es unter Windows 11 läuft.**
- Kann etwas nicht unter Windows geprüft werden, das **ausdrücklich** sagen – nie als
  „getestet“ oder „fertig“ melden, wenn nur macOS getestet wurde.

## Windows-Fallstricke – bei jeder Änderung prüfen

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
- Keine Unix-Annahmen: kein `os.fork`, keine Signale außer Strg+C, kein `chmod`,
  Groß-/Kleinschreibung von Dateinamen nicht unterscheiden (Windows tut es nicht),
  keine Dateinamen mit `: * ? " < > |`.

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
