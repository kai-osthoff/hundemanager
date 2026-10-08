# Hundemanager

Flask-App (SQLite) zur Verwaltung von Hunden, Impfungen und Haftpflicht.
Entwickelt wird von Kai, genutzt von Saskia.

> **Einzige Quelle der Projektregeln** – gilt für Codex, Claude Code und alle anderen
> Agenten. `CLAUDE.md` importiert diese Datei nur (`@AGENTS.md`). Regeln immer **hier**
> ändern, nie in `CLAUDE.md`, damit nie zwei Fassungen im Umlauf sind.

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
- **Python starten über `py`, nicht `python`:** Unter Windows 11 kann `python` auf den
  Microsoft-Store-Platzhalter (`WindowsApps\python.exe`) zeigen, wenn der im PATH vor
  dem echten Python steht – in der VM passiert. `START.bat` nimmt daher `py` (kommt mit
  python.org) und fällt nur ohne `py` auf `python` zurück. Kein `python3`, keine
  Shell-Skripte, keine macOS-/Unix-only-Tools in der App.
- `START.bat` wird bei Updates nie ausgetauscht – Verbesserungen daran erreichen nur
  neue Installationen. Logik deshalb immer in `start.py`.
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
- **Echtes Windows 11 lokal:** `./windows-test.sh` (optional `-k Muster`) testet in der
  Parallels-VM „Windows 11“ (ARM64, Python 3.13 x64 wie bei Saskia) – Ergebnis in ~1 Min.
  Erst hier testen, dann pushen. Die VM hat Defender aktiv: frisch geschriebene Dateien
  sind kurz gesperrt – Löschen/Ersetzen immer mit Wiederholung (`_mit_wiederholung`).
  In der VM gibt es kein git; Befehle laufen über `prlctl exec "Windows 11" --current-user`.

## Arbeitsweise: ein Worktree pro Aufgabe, danach atomar committen und mergen

- **Jede Aufgabe bekommt einen eigenen Git-Worktree mit eigenem Branch** – nie direkt
  auf `main` im Hauptordner (`~/githubrepos/hundemanager`) arbeiten. Die Worktrees legt
  Shepherd an (unter `~/githubrepos/.shepherd-worktrees/`). Ohne Shepherd:
  `git worktree add ../.shepherd-worktrees/hundemanager-<aufgabe> -b <typ>/<aufgabe>`
  (z. B. `fix/impfdatum`). Worktrees liegen **nie** innerhalb des Repo-Ordners, sonst
  kopiert `windows-test.sh` (robocopy `/MIR`) sie mit in die VM.
- Im Worktree gibt es kein `.venv` und kein `instance/`: Python aus dem Hauptordner
  nehmen (`~/githubrepos/hundemanager/.venv/bin/python …`); die App nie mit Saskias
  Daten aus einem Worktree heraus starten.
- **Abschluss jeder Aufgabe:** Tests grün (lokal + `./windows-test.sh`) → **ein
  atomarer Commit** (genau eine logische Änderung, Commit-Nachricht auf Deutsch) →
  ohne Rückfrage nach `main` mergen (`git merge --ff-only`, sonst vorher auf `main`
  rebasen) → Worktree und Branch löschen
  (`git worktree remove …` und `git branch -d …`) → **sofort `./release.sh`**
  (siehe Releases). Erst mit dem Release ist die Aufgabe fertig.
- Mehrere Aufgaben = mehrere Worktrees und mehrere Commits, nie gebündelt.
- **Jeder fertige Worktree wird IMMER sofort released – ohne Rückfrage.** Wir sind in
  einer frühen Phase und wollen schnell vorwärtskommen: lieber viele kleine Releases
  als liegengebliebene Commits auf `main`. Veröffentlicht wird nur über `./release.sh`
  (nie von Hand taggen), der Windows-Test bleibt die Sperre.

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

## Nachweise (Haftpflicht, Impfpass, …)

- EINE Ablage für alle Dokumente: Modell `Nachweis` mit Feld `art`. Die Arten und ihre
  Felder stehen in `NACHWEIS_ARTEN` (app.py) – neue Art = Eintrag dort, keine neue Tabelle.
  Gemeinsam: eingereicht von (Halter beim Hochladen), Quelle/Aussteller, Nummer,
  ausgestellt am, gültig bis, Originaldatei. Haftpflicht: Gültigkeit Pflicht, Tier/Chip.
  Impfpass: belegte Impfungen, Gültigkeit optional.
- `/nachweise` zeigt die Historie aller Nachweise und „Neuen Nachweis anfordern“: der je
  Hund und Art aktuellste Nachweis aktiver Halter, wenn er innerhalb von
  `ERINNERUNG_VORLAUF` (6 Wochen) abläuft – Grundlage für spätere Erinnerungen.
- 5.1.1/5.1.2 hatten die Tabelle `haftpflicht_nachweis`; `migriere_datenbank()` übernimmt
  sie einmalig nach `nachweis` (mit Sicherung, Zählprüfung). Die alte Tabelle bleibt
  bewusst stehen – nie löschen.
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
- Erkennung (`nachweise.angaben_vorschlagen`) liefert nur Vorschläge (bisher nur
  Haftpflicht-PDFs); pypdf gibt Textblöcke in beliebiger Reihenfolge aus – Muster nie
  an der Reihenfolge festmachen.
- **Drag-and-Drop:** Upload-Seiten haben eine Ablagefläche (`label.ablage`, Skript in base.html; `data-senden` lädt
  gleich hoch). In der Übersicht sind Hundekarte und Halter Ablageziele (`data-ablage-*`); der Dialog
  `ablage-dialog` fragt „Was ist das?“ und schickt die Datei an die vorhandenen Hochlade-Routen – keine eigene Route.
- **Mehrere Dateien je Nachweis** (z. B. Tollwut-Seite + Impfseite): die erste steht am
  `Nachweis`, weitere in `nachweis_seite` (`nr` ab 2). `Nachweis.seiten` liefert alle.
- **Drehen nur in der Anzeige:** `drehung` (0/90/180/270, im Uhrzeigersinn) am Nachweis bzw.
  an der Seite. `bilder.py` schätzt beim Hochladen die nötige Drehung am Inhalt
  (Zeilenprofil quer/hoch, Ober- vs. Unterlängen für oben/unten – ohne Texterkennung, nur
  Pillow) und liefert gedrehte Ansichten (`/nachweis/bild/<sha>.<endung>?drehung=`).
  Fehlt Pillow, läuft alles ohne Drehung weiter. Die Datei wird nie umgeschrieben.
- **Impfpass:** Saskia liest die Daten von den Fotos ab und trägt je Impfung „gültig bis“ ein
  (`impf_gueltig` als JSON am Nachweis). Beim Speichern landen sie am Hund
  (`impfungen_uebernehmen`): ein späteres Datum gewinnt – ein altes Foto überschreibt keine
  neuere Impfung; bei einer Korrektur wird nur zurückgesetzt, was aus diesem Nachweis stammt.
  `gueltig_bis` des Nachweises = früheste Impfung darauf. Daten > 5 Jahre in der Zukunft
  oder vor 2000 werden abgelehnt.
- **Impfstoffe:** `impfstoffe.py` ordnet Aufkleber (Nobivac SHP, Versican Plus L4, Nobivac RL …) den vier
  Impfungen zu (`IMPFSTOFFE`, Kombi-Impfstoffe decken mehrere ab) und liefert die Beschreibung („L – Leptospirose“).
  Neuer Impfstoff = Zeile dort. „verw. bis“/„Exp.“ auf dem Aufkleber ist das Verfallsdatum des Impfstoffs, nie die
  Gültigkeit der Impfung. Plan für die Foto-Erkennung: `docs/superpowers/specs/2026-10-08-heimtierausweis-erkennung-design.md`.
- **Erkennung von Impfpass-Fotos** (`erkennung.py`, erster Entwurf): RapidOCR lokal (kein Cloud-Dienst), optional –
  fehlt es, läuft alles ohne Vorschläge. Wir können nicht beeinflussen, was Halter fotografieren: deshalb nur über
  **Merkmale** (Überschriften/Beschriftungen in `SEITEN`/`FELDER`, Englisch zählt überall), nie über feste Positionen.
  Werte nur im Feld unter ihrer Beschriftung; Plausibilität (gültig bis passend nach Impfdatum) entscheidet
  sicher/unsicher; unsichere Zeilen werden nie vorausgefüllt, nur mit Bildausschnitt gezeigt (Knopf „Übernehmen“).
  Ein späteres unsicheres Datum verhindert einen veralteten Vorschlag (`offen`). Von der Besitzerseite wird nichts
  übernommen. `Nachweis.erkennung` speichert nur je Feld übernommen/geändert/geleert – Grundlage für weitere Iterationen.
  Tests: `auswerten()` mit erfundenen Textblöcken; echte Pass-Fotos nur lokal messen, nie ins Repo.
- Fällige Impfungen (abgelaufen oder innerhalb `ERINNERUNG_VORLAUF`) stehen in `/nachweise`
  mit WhatsApp-Nachfrage (`whatsapp.impfpass_nachricht`), Grundlage sind die Daten am Hund.

## WhatsApp an Halter

- Kein externer Dienst, keine API: `whatsapp.py` baut nur Click-to-Chat-Links
  (`https://web.whatsapp.com/send?phone=<international>&text=<URL-codiert>`), die WhatsApp Web
  im Browser öffnen. Saskia schickt selbst ab – die App versendet nie etwas.
- Halter haben `mobil` (so wie eingegeben gespeichert, `whatsapp.nummer()` macht daraus
  `49171…`; deutsche Nummern ohne Vorwahl gelten als +49) und `email`.
- Hundekarten mit fehlenden/abgelaufenen/bald fälligen Angaben bekommen eine vorausgefüllte
  Nachfrage (`fehlende_angaben()` in app.py). Datenschutz: echte Nummern nie in Tests.
- Halter ohne Handynummer **und** E-Mail (`Person.kontaktdaten_fehlen`): Knopf „Kontaktdaten bei … anfragen“
  schickt per WhatsApp eine Bitte an den Ansprechpartner im Vorstand (`kontaktdaten_name`/`kontaktdaten_mobil`
  in `EINSTELLUNGEN`, nur beide zusammen). Ist keiner eingetragen, öffnet der Knopf den Einstellungsdialog.

## E-Mail an Halter

- Neben jedem WhatsApp-Knopf ein E-Mail-Knopf, wenn eine Adresse hinterlegt ist – gleiche Texte
  (`kanal='email'` in den `whatsapp.*_nachricht`-Funktionen), dazu ein Betreff.
- `mailto.py` baut nur normale `mailto:`-Links (Betreff/Text URL-codiert, `%20` statt `+`,
  Zeilen mit `%0D%0A`). GMX hat **keinen** Verfassen-Link mit URL-Parametern (recherchiert: alte
  Links hängen an der Sitzung, selbst die GMX-Erweiterung nutzt eine interne Schnittstelle).
  GMX öffnet sich über die Erweiterung **GMX MailCheck** mit der Einstellung „E-Mail Links in
  Webseiten mit MailCheck öffnen“; ohne sie öffnet Windows sein Standard-Mailprogramm.
- Hilfe dazu: Dialog `mail-hilfe` in base.html (immer über „Hilfe: E-Mail“ im Fuß erreichbar).
  Der Knopf „? GMX-Hilfe“ neben den E-Mail-Knöpfen verschwindet nach `MAIL_HILFE_BIS_KLICKS`
  geklickten E-Mail-Links; der Zähler steht als `mail_klicks` in der Tabelle `einstellung`
  (bewusst nicht in `EINSTELLUNGEN`). Datenschutz: echte Adressen nie in Tests.

## Wiedervorlage je Hund

- Eine Wiedervorlage gilt gemeinsam für die nachzufragenden Angaben des Hundes.
  Nach dem Öffnen einer WhatsApp-/E-Mail-Anfrage wird sie nach dem abbrechbaren
  Countdown mit der eingestellten Standardfrist gespeichert (Standard: 14 Tage).
- Saskia kann den aktuellen Termin löschen oder ein eigenes Datum setzen/ändern.
  Löschen schaltet spätere automatische Wiedervorlagen nicht ab. Öffnen des
  Datumseditors oder Löschen beendet einen noch wartenden Countdown dieses Hundes.
- Jeder zukünftige Termin nimmt den Hund bis zum Vortag aus „Handlungsbedarf“ und
  dessen Zähler. Am Termin ist er wieder fällig. Die übrigen Ansichten und
  Kennzahlfilter zeigen die Angaben weiterhin. Ohne Termin gilt die normale
  Handlungsbedarfsregel; Löschen erledigt keine fehlenden Angaben.
- Sobald alle nachzufragenden Angaben vollständig sind (einschließlich Geburtstag
  und erforderlichen Nachweisen), entfernt die App den Termin automatisch.

## Fotoeinwilligung (je Halter) und Einstellungen

- Die Einwilligung zu Fotoaufnahmen gilt für die **Person**, nicht für einen Hund – deshalb
  eigene Tabelle `fotoeinwilligung` (nicht `Nachweis`, das hängt am Hund). Die Datei liegt
  trotzdem über `nachweise.speichern()` in derselben unveränderlichen Ablage und wird so
  automatisch mitgesichert.
- `Person.foto_status`: `nachgewiesen` (Dokument da), `ohne-nachweis` (nur Häkchen
  `fotofreigabe`, Altbestand), `widerrufen`, `fehlt`. Bei `fehlt`/`ohne-nachweis` gibt es eine
  WhatsApp-Anfrage mit Link zum Formular. Nach einem Widerruf wird **nicht** erneut gefragt.
- Widerruf wird nur vermerkt (`widerrufen_am`), Eintrag und Datei bleiben als Nachweis.
  `fotofreigabe` wird beim Hochladen/Widerruf mitgeführt (Excel und Altcode lesen es).
- Einstellungen: Tabelle `einstellung` (Schlüssel/Wert), bekannte Einträge mit Standard in
  `EINSTELLUNGEN` (app.py). Leerer/Standardwert wird nicht gespeichert. Bearbeitet wird im
  Einstellungsdialog (`<dialog>` im Kopf jeder Seite), `/einstellungen` ist die Rückfallseite.
  Der Formular-Link (`fotoeinwilligung_link`) muss mit http(s):// beginnen.
- Farbschema (`theme`, Art `auswahl`): Standard „Türkis“ (Farben/Formen von hsv-grossbottwar.de),
  wählbar „Grün (bisher)“. `base.html` setzt `<html data-theme="…">`; der Grundstil dort ist Grün,
  `_theme_tuerkis.html` legt Türkis per `[data-theme="tuerkis"]` darüber. Kein Tailwind/CDN:
  die App läuft offline, ohne Build-Schritt. Schrift Poppins nur, wenn installiert (sonst
  Century Gothic/Segoe UI). Neues Schema = Eintrag in `optionen` und `vorschau` + eigene Stil-Datei.
- Einstellungsdialog (`_einstellungen_formular.html`) ist von Hand in Abschnitte gegliedert (Aussehen als
  Karten mit Vorschau, Formular-Link als Dokument-Karte, Ansprechpartner mit Vorschau der WhatsApp-Anfrage) –
  eine neue Einstellung braucht dort einen eigenen Abschnitt. Farbschema und WhatsApp-Vorschau wirken live
  (Skript in base.html); Schließen ohne Speichern setzt Formular und Schema zurück.

## Releases

- **Versionen: nur 5.1.x, nur die letzte Stelle hochzählen** (5.1.1, 5.1.2, …).
  Viele kleine Schritte statt großer Sprünge.
- **Nach jedem fertigen Worktree wird released** (siehe Arbeitsweise) – nicht sammeln,
  nicht auf Rückfrage warten. Ist `release.sh` rot, ist die Aufgabe nicht fertig:
  Fehler beheben (neuer Worktree) und erneut releasen.
- `./release.sh "Notizen"` – ermittelt die nächste Nummer selbst, testet lokal,
  pusht und veröffentlicht **nur, wenn der Windows-Test grün ist**.
- Die Notizen sieht Saskia im Update-Hinweis: verständlich und auf Deutsch.
- Saskias App prüft `releases/latest` von `kai-osthoff/hundemanager` und installiert
  per Button. Ein kaputtes Release landet direkt bei ihr.
