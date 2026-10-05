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

- Port 5000 ist auf dem Mac von AirPlay belegt, und die zweite Backup-Kopie soll nicht
  in Kais Dokumente-Ordner landen:
  `HUNDEMANAGER_PORT=5050 HUNDEMANAGER_BACKUP_ZWEITER_ORT=/tmp/hm-doku .venv/bin/python start.py`
- Saskia läuft immer auf Port 5000.
- Tests: `.venv/bin/python -m unittest discover -s tests -v` – laufen bei jedem Push
  zusätzlich auf Windows (GitHub Actions, Python 3.11–3.14).

## ⚠️ Daten und Backups – nicht verhandelbar

Saskias Daten liegen ausschließlich in `instance/hundemanager.db` – nie im Repo
(`.gitignore`), vom Updater nie angefasst. **Jede Änderung an Daten, Schema oder
Programm passiert erst nach einer geprüften Sicherung.**

- Sicherungen nur über `backup.erstelle_backup()` – nie Dateien von Hand kopieren.
  Es nutzt die SQLite-Backup-API, prüft Integrität, Datensatzzahl und Prüfsummen
  und spiegelt nach `Dokumente\Hundemanager-Backups`.
- Schlägt die Sicherung fehl, wird **nicht** weitergemacht (kein Update, keine
  Migration, keine Wiederherstellung).
- Update-Ablauf (`updater.py`): Sicherung → Download prüfen → Marker
  `update_laeuft.json` → Dateien tauschen (bei Fehler sofort zurück) → Neustart →
  Selbsttest in `app.py` → bei Fehlstart nimmt `start.py` Programm **und** Datenbank
  aus der Sicherung zurück.
- **Der alte Prozess rendert nach dem Kopieren die NEUEN Templates.**
  `update_fertig.html` bleibt deshalb eigenständig (kein `extends`) und darf nur
  `url_for('index')`, `url_for('api_version')`, `meldung`, `alte_version` nutzen.
- Formate von `manifest.json` und `update_laeuft.json` stabil halten: ein älteres
  `start.py` im Speicher muss Sicherungen neuerer Versionen zurückspielen können.
- Neue Spalten: `migriere_datenbank()` ergänzt sie beim Start (mit Sicherung).
  Nur nullable oder mit Default; Umbenennen/Löschen braucht eine eigene Migration.
- Jeder neue Ernstfall bekommt einen Test in `tests/` – vor allem Update-Übergänge.

## Haftpflicht-Nachweise

- Dateien liegen unveränderlich in `instance/nachweise/<sha256>.<pdf|jpg|png>` –
  nie überschreiben, nie löschen. Ein neuer Nachweis kommt *dazu*, alte bleiben als
  Historie. Korrigiert werden nur die Angaben in der Datenbank, nie die Datei.
- Sicherungen legen Nachweise in einer gemeinsamen Ablage `backup/nachweise/` ab
  (einmal pro Inhalt), das Manifest listet sie, `pruefe_backup()` prüft jede Datei.
  Diese Ablage wird nie aufgeräumt.
- Dateityp wird am Inhalt erkannt, nicht an der Endung.
- **Datenschutz:** Echte Nachweise enthalten Namen, Adressen, Vertragsnummern.
  Nie ins Repo (`.gitignore` sperrt PDFs/Bilder), nie in Tests, nie in Commits,
  Release-Notizen oder Issues zitieren. Tests nutzen erfundene Daten (`test_pdf()`).
- Erkennung (`nachweise.angaben_vorschlagen`) liefert nur Vorschläge; pypdf gibt
  Textblöcke in beliebiger Reihenfolge aus – Muster nie an der Reihenfolge festmachen.

## Releases

- **Versionen: nur 5.1.x, nur die letzte Stelle hochzählen** (5.1.1, 5.1.2, …).
  Viele kleine Schritte statt großer Sprünge.
- `./release.sh "Notizen"` – ermittelt die nächste Nummer selbst, testet lokal,
  pusht und veröffentlicht **nur, wenn der Windows-Test grün ist**.
- Die Notizen sieht Saskia im Update-Hinweis: verständlich und auf Deutsch.
- Saskias App prüft `releases/latest` von `kai-osthoff/hundemanager` und installiert
  per Button. Ein kaputtes Release landet direkt bei ihr.
