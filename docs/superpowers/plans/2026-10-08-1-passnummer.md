# Teilprojekt 1: Passnummer am Hund – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jeder Hund kann die Nummer seines EU-Heimtierausweises tragen (Grundlage für die spätere Zuordnung von Pass-Fotos).

**Architecture:** Neue nullable Spalte `Hund.passnummer`; `migriere_datenbank()` ergänzt sie automatisch (mit Sicherung). Normalisierung/Anzeige als zwei kleine Funktionen in app.py. Formular, Hundekarte und Excel zeigen sie.

**Tech Stack:** Flask, Flask-SQLAlchemy, SQLite, openpyxl, unittest (Integrationstests starten die echte App).

## Global Constraints

- Muss unter Windows 11 laufen; Tests lokal + `./windows-test.sh`.
- Neue Spalten nur nullable; Migration nur über `migriere_datenbank()` (sichert vorher).
- Datenschutz: keine echten Passnummern in Tests/Commits – erfundene Werte (`DE12 3456789`).
- Format nicht erzwingen (ausländische Pässe): nur Leerzeichen/Bindestriche entfernen, Großbuchstaben.
- Ein atomarer Commit, Nachricht auf Deutsch, danach merge `--ff-only`, Worktree weg, `./release.sh`.

---

### Task 1: Passnummer speichern, anzeigen, exportieren

**Files:**
- Modify: `app.py` (Modell `Hund`, `hund_neu`, `hund_bearbeiten`, Excel-Export, Jinja-Filter)
- Modify: `templates/hund_form.html` (Feld nach Geburtstag)
- Modify: `templates/index.html` (Zeile unter dem Hundenamen)
- Test: `tests/test_hundemanager.py` (neue Klasse `PassnummerTests`)

**Interfaces:**
- Produces: `Hund.passnummer: str | None` (normalisiert, z. B. `'DE123456789'`),
  `passnummer_normalisieren(text) -> str | None`, Jinja-Filter `passnummer` (Anzeige `'DE12 3456789'`).
  Spätere Teilprojekte (Erkennung) vergleichen gegen `Hund.passnummer` mit `passnummer_normalisieren`.

- [ ] **Step 1: Failing test** – Klasse `PassnummerTests` (setUp/tearDown/oeffne von
  `HaftpflichtOberflaecheTests`): Hund 1 mit `passnummer=' de12 345-6789 '` speichern →
  DB enthält `DE123456789`; Bearbeiten-Seite zeigt `value="DE12 3456789"`; Übersicht zeigt
  `Pass DE12 3456789`; Excel-Kopfzeile Spalte 14 = `Passnummer`, Zeile Bello = `DE12 3456789`;
  leeres Feld → NULL. Die Test-DB aus `db_anlegen()` hat keine Spalte → prüft die Migration mit.
- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_hundemanager.PassnummerTests -v` → FAIL.
- [ ] **Step 3: Implementierung**
  - `Hund`: `passnummer = db.Column(db.String(30), nullable=True)  # EU-Heimtierausweis, normalisiert`
  - ```python
    def passnummer_normalisieren(text):
        """'de12 345-6789' -> 'DE123456789'; leer -> None. Format bewusst nicht erzwungen (Ausland)."""
        wert = re.sub(r'[\s\-./]', '', text or '').upper()
        return wert[:30] or None

    def passnummer_anzeige(wert):
        """'DE123456789' -> 'DE12 3456789' (so steht sie im Pass)."""
        return f'{wert[:4]} {wert[4:]}' if wert and len(wert) > 4 else (wert or '')
    ```
    Filter registrieren: `app.jinja_env.filters['passnummer'] = passnummer_anzeige`.
  - `hund_neu`/`hund_bearbeiten`: `passnummer=passnummer_normalisieren(request.form.get('passnummer'))`.
  - Formular: `<input type="text" id="passnummer" name="passnummer" placeholder="z. B. DE12 3456789" value="{{ hund.passnummer|passnummer if hund else '' }}">` mit Hinweis „steht unten auf jeder Seite des Heimtierausweises“.
  - Karte: `{% if hund.passnummer %} · Pass {{ hund.passnummer|passnummer }}{% endif %}` in der Geburtstagszeile.
  - Excel: Kopf `'Passnummer'` als Spalte 14, Wert `passnummer_anzeige(hund.passnummer)`, Breite 16.
- [ ] **Step 4:** Test erneut → PASS; komplette Suite lokal grün; `./windows-test.sh` grün.
- [ ] **Step 5: Commit** „Passnummer des Heimtierausweises am Hund hinterlegen“ (zusammen mit Spec und Plan),
  merge nach main, Worktree entfernen, `./release.sh "…"`.
