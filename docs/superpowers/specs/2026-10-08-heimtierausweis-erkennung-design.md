# Heimtierausweis: Passnummer, Impfstoff-Zuordnung, Erkennung, optimierte Ansicht

Stand: 2026-10-08 · Entscheidungen von Kai im Brainstorming

## Ziel

Saskia liest heute alle Daten aus Fotos des EU-Heimtierausweises selbst ab. Künftig:

- die **Passnummer** ist am Hund hinterlegt (Zuordnung Pass ↔ Hund),
- die App **schlägt** erkannte Werte vor (Passnummer, Chip, Geburtsdatum, Impfungen mit
  Impfdatum/gültig bis) – Saskia bestätigt oder überschreibt, nie automatisch übernommen,
- Impfstoffe auf den Aufklebern werden **Impfungen zugeordnet** (mit Beschreibung statt nur „L“),
- Fotos werden in der Anzeige **gerade gezogen und zugeschnitten**, das Original bleibt
  unverändert archiviert,
- unbrauchbare Fotos (angeschnitten, Seite nicht lesbar) lösen eine **vorausgefüllte
  Nachfrage** an den Halter aus.

## Entscheidungen

- **Nur lokal, keine Cloud.** Keine Fotos an externe Dienste (Datenschutz: Pässe enthalten
  Namen, Adressen, Telefonnummern).
- **Texterkennung: RapidOCR** (`rapidocr==3.9.2` + `onnxruntime==1.30.0`), plattformübergreifend.
  Modelle sind im Wheel enthalten – kein Download beim ersten Start.
  - Geprüft: Windows-Wheels (win_amd64) für CPython 3.11–3.14 vorhanden (onnxruntime,
    opencv-python abi3, numpy; numpy 2.5 nur ab 3.12 → numpy nicht pinnen bzw. mit Marker).
    Zusätzliche Abhängigkeiten (pyclipper, shapely, omegaconf …) im Plan auf Windows-Wheels
    für 3.14 prüfen. Download bei Saskia einmalig ca. 70 MB.
  - Fehlt RapidOCR/OpenCV (Installation nicht nachgezogen), läuft alles wie heute – ohne
    Vorschläge und ohne Entzerrung. Gleiches Muster wie Pillow in `bilder.py`.
- **Reihenfolge der Releases:** 1 → 2 → 5 → 3 → 4 (je eigener Worktree, Commit, Release).

## Machbarkeit (Messlauf mit Kais Pass, lokal, nicht im Repo)

RapidOCR 3.9.2 auf 4 Fotos, ~1 s/Seite (macOS):

- Passnummer `DE12 3456789`: auf jeder Seite gelesen. Chipnummer (Aufkleber): gelesen.
- Geburtsdatum (Handschrift): gelesen.
- Aufkleber: `Nobivac SHP`, `Nobivac® L4`, `NobivacBbPi`, `VERSICAN Plus L4`, `Virbagen canis L`,
  `NobivacT` gelesen.
- Handschriftliche Daten Seite IX: die meisten richtig; Seite V: 4 von 7 richtig, Rest Müll
  („tr“, „necOte“) oder fehlend.
- **Gefahr:** durchgestrichenes `17.01.23` wird als gültig gelesen, „1“ als „A“, die Korrektur
  `07.11.2022`→`07.12.2022` als `07.122022`. → Plausibilitätsprüfung ist Pflicht.

## Fachliche Fallen

- **„verw. bis“ / „Exp.“ auf dem Aufkleber ist das Verfallsdatum des Impfstoffs, nicht die
  Gültigkeit der Impfung.** Nie als „gültig bis“ verwenden (Format `MM-JJJJ`/`MM/JJJJ` → ignorieren).
- Eine Zeile kann mehrere Impfstoffe tragen (SHP + L4 + BbPi) – ein Datum gilt dann für alle.
- Ein Foto zeigt oft eine Doppelseite (z. B. 22/32 und 23/32).
- Tollwut (Seite V) hat zusätzlich „Gültig ab“; Gültigkeit bis zu 3 Jahre.

## Grundsatz: Wir wissen nie, was wir bekommen

Die Fotos schicken Vereinsmitglieder – wir können weder Auswahl, Ausschnitt, Licht, Winkel
noch Pass-Ausgabe beeinflussen. Das ist die größte Schwierigkeit. Die Erkennung entscheidet
deshalb **anhand von Merkmalen, was auf dem Foto zu sehen ist**, und verlässt sich nie auf
Aufbau, Reihenfolge oder feste Positionen. Dies ist der **erste Entwurf**; weitere Iterationen
folgen, deshalb Merkmale als Daten (Tabelle) statt im Code verstreut.

- **Mögliche Inhalte eines Fotos:** eine oder zwei Passseiten (Doppelseite), nur ein Teil einer
  Seite, mehrere Seiten schräg übereinander, ein anderes Dokument (Haftpflicht, Rechnung,
  Impfbescheinigung des Tierarztes), ein Hundefoto, Screenshot, ein Pass aus einem anderen Land.
- **Seitenart über Merkmal-Punkte, nicht über eine einzelne Überschrift:** je Seitenart eine
  Liste von Merkmalen mit Gewicht (`MERKMALE` in `erkennung.py`), z. B. Tollwut:
  „Tollwut“, „Rabies“, „Gültig ab“/„Valid from“, Aufkleber eines Tollwut-Impfstoffs;
  Sonstige Impfungen: „Sonstige Impfungen“, „Other Vaccinations“, Aufkleber SHP/L4/BbPi.
  Vergleich tolerant (Groß/klein, Akzente, OCR-Vertipper per Ähnlichkeit, nicht exakt).
- **Englisch als Anker:** Der EU-Heimtierausweis ist in jedem Mitgliedstaat zweisprachig
  (Landessprache + Englisch). Englische Merkmale („Vaccination against Rabies“, „Valid until“,
  „Vaccination Date“, „Transponder alphanumeric code“, „Date of birth“) tragen deshalb das
  meiste Gewicht – so funktionieren auch Pässe aus anderen EU-Ländern.
- **Mehrere Seiten auf einem Foto:** Merkmale und Werte werden Bildbereichen zugeordnet
  (Überschrift + die Werte darunter bis zur nächsten Überschrift / „Seite x/32“). Ein Foto kann
  so z. B. II und III gleichzeitig liefern.
- **Nichts Passendes erkannt:** kein Vorschlag, kein Fehler – Saskia trägt wie bisher selbst ein.
  Die App sagt ehrlich „Seite nicht erkannt“ statt zu raten.
- **Jeder Wert braucht ein Merkmal in seiner Nähe:** ein Datum ist nur dann „gültig bis“, wenn
  die Beschriftung („Gültig bis“/„Valid until“) dazu gehört; ein freistehendes Datum wird nie
  verwendet. Zahlen in Stempeln (Telefon, PLZ) werden nicht als Werte gelesen.
- **Sammlung zum Verbessern:** Wie gut die Erkennung ist, zeigt erst der Alltag. Speichern,
  ob Saskia einen Vorschlag übernommen oder geändert hat (nur ja/nein je Feld, keine
  Inhalte), damit die nächsten Iterationen gezielt nachbessern können.

## Teilprojekte

### 1. Passnummer am Hund

- `Hund.passnummer` (String, nullable) über `migriere_datenbank()` (mit Sicherung).
- Normalisiert gespeichert (Großbuchstaben, ohne Leerzeichen: `DE123456789`), angezeigt
  gruppiert (`DE12 3456789`). Format nicht erzwingen (ausländische Pässe), nur trimmen.
- Im Hundeformular, auf der Hundekarte, im Excel-Export (neue Spalte am Ende).
- Tests: Migration einer bestehenden DB ohne Spalte, Normalisierung, Excel-Spalte.

### 2. Impfstoff-Zuordnung

- Neues Modul `impfstoffe.py`:
  - `IMPFUNG_BESCHREIBUNG`: je Feld Kurzname + Beschreibung, z. B.
    `gueltig_l` → „L – Leptospirose“, `gueltig_shp_dap_dhp` → „SHP/DAP/DHP – Staupe, Hepatitis,
    Parvovirose“, `gueltig_bbpi` → „BbPi – Zwingerhusten (Bordetella, Parainfluenza)“,
    `gueltig_t` → „T – Tollwut“.
  - `IMPFSTOFFE`: Liste (Muster, Felder, Anzeigename). Ein Impfstoff kann mehrere Impfungen
    abdecken (z. B. Kombi-Impfstoffe mit L). Startbestand: Nobivac SHP/DHP/DHPPi, Nobivac L4,
    Nobivac BbPi/KC, Nobivac T, Versican Plus DHPPi, Versican Plus L4, Versican Plus Pi,
    Virbagen canis L, Eurican DAPPi, Eurican L4, Canigen, Rabisin, Rabikal.
  - `zuordnen(text) -> [feld, ...]`: tolerant gegen OCR-Fehler (Groß/klein, ®, fehlende
    Leerzeichen: `NobivacT`, `Nobivoc SHP`).
- `IMPF_ERKENNEN` in app.py geht darin auf; Oberfläche zeigt Kurzname + Beschreibung und im
  Impfpass-Dialog eine aufklappbare Liste „Welcher Aufkleber gehört zu welcher Impfung?“.
- Tests: Zuordnung aller Muster inkl. OCR-Varianten aus dem Messlauf.

### 5. Erkennung als Vorschlag

- Neues Modul `erkennung.py`, optional importiert (RapidOCR fehlt → `verfuegbar() == False`).
- Ablauf beim Hochladen eines Impfpass-Fotos (nur Bilder; PDFs wie bisher):
  1. OCR auf der Ansicht mit angewandter `drehung` (bilder.py), Ergebnis: Textblöcke mit Box.
  2. **Seitenart(en)** über Merkmal-Punkte (siehe „Grundsatz“), je Bildbereich: II Beschreibung,
     III Kennzeichnung, V Tollwut, IX Sonstige Impfungen. **Seite I (Besitzer) und VII werden verworfen**, nichts davon
     wird gespeichert oder angezeigt (Datenschutz).
  3. **Passnummer**: Muster `[A-Z]{2}\d{2}\s?\d{6,9}` (ggf. mehrfach auf der Seite → Mehrheit).
  4. **Seite II**: Geburtsdatum = Datum rechts neben/nahe „Geburtsdatum“.
     **Seite III**: Chip = 15 Ziffern.
  5. **Seite V/IX**: Zeilen über die Beschriftungen „Impfdatum“ und „Gültig bis“ (Position,
     nicht Reihenfolge der Textblöcke). Wert = Datum direkt unter/neben der Beschriftung.
     Aufkleber = Textblöcke links davon im selben Zeilenband → `impfstoffe.zuordnen()`.
     Seite V ohne erkannten Aufkleber → T (die Seite ist ausschließlich Tollwut).
  6. **Plausibilität je Zeile**: gültig bis > Impfdatum; Abstand 11–13 Monate (IX) bzw.
     1–3 Jahre (V, ± 1 Monat); Datum nicht vor 2000 und nicht > 5 Jahre in der Zukunft
     (bestehende Regel). Sonst Status `unsicher`: angezeigt, aber **nicht vorausgefüllt**.
     Kaputte Datumsformate (`07.122022`) → `unsicher`.
  7. Je Impfung wird das **späteste** plausible „gültig bis“ vorgeschlagen.
- Ergebnis als JSON am Nachweis bzw. an der Seite (`erkennung`, nullable Text): pro Wert
  Feld, Text, Status (`sicher`/`unsicher`), Box (für Ausschnitt). Kein OCR-Volltext speichern.
- **Oberfläche** (Impfpass-Dialog): erkannte Werte vorausgefüllt mit Hinweis „erkannt – bitte
  prüfen“, daneben der Bildausschnitt (`/nachweis/bild/...?ausschnitt=x,y,w,h`).
  Unsichere Werte nur als Hinweis mit Ausschnitt. Saskia speichert wie bisher → die
  vorhandene Logik `impfungen_uebernehmen` (späteres Datum gewinnt) bleibt unverändert.
- **Passnummer-Abgleich**: Hund hat Passnummer und Foto zeigt eine andere → deutliche Warnung
  „Dieses Foto gehört evtl. zu einem anderen Hund (Pass …)“. Hund hat keine → Vorschlag zum
  Übernehmen (Häkchen, nicht automatisch).
- Geburtsdatum/Chip: Vorschlag nur, wenn am Hund leer oder abweichend (dann Hinweis).
- Laufzeit: OCR beim Hochladen synchron (~1–3 s/Seite). Auf Windows in der VM messen; zu
  langsam → Bild für OCR auf ~2000 px Kante verkleinern.
- Tests: Unit-Tests der Auswertung mit **erfundenen OCR-Ergebnissen** (Boxen+Texte nach dem
  Muster des Messlaufs, ohne echte Daten), inkl. durchgestrichen/kaputt/„verw. bis“-Falle;
  ein Integrationstest rendert eine erfundene Seite mit Pillow und lässt RapidOCR laufen
  (übersprungen, wenn RapidOCR fehlt). Echte Fotos nie ins Repo.

### 3. Optimierte Ansicht (Zuschnitt + Entzerrung)

- `bilder.py`: `seite_finden(daten) -> 4 Eckpunkte | None` mit OpenCV (hellste große
  Vierecksfläche vor dunklem Tisch/Teppich; Doppelseiten als ein Viereck).
- Eckpunkte als JSON am Nachweis/an der Seite (`ecken`, nullable). Anzeige: perspektivisch
  entzerrt, dann `drehung`. Die Datei bleibt unverändert (bestehende Regel).
- Im Dialog: Umschalter „Optimiert / Original“. Kein manuelles Eckenziehen in v1.
- Erkennung (5) nutzt danach die entzerrte Ansicht.
- Tests: synthetisches Bild (helles, schräges Viereck auf dunklem Grund) → Ecken gefunden;
  ohne OpenCV → Original.

### 4. Qualitätsprüfung und Nachfrage beim Halter

- Je Foto ein Prüfergebnis: Seite berührt den Bildrand / keine 4 Ecken / Passnummer bzw.
  „Seite x/32“ nicht lesbar / sehr unscharf (Laplace-Varianz) → `unvollstaendig` + Grund.
- WhatsApp- und E-Mail-Knopf (bestehende `whatsapp.py`/`mailto.py`, gleiche Texte mit
  `kanal`), z. B.: „Hallo …, für den Impfnachweis von Bello brauche ich die Seite 22/32
  (Sonstige Impfungen) noch einmal: bitte die ganze Seite gerade von oben fotografieren,
  alle vier Ecken sichtbar, nichts abgeschnitten. Danke!“
- Die Wiedervorlage-Logik (Countdown nach dem Öffnen der Anfrage) gilt wie bei anderen Anfragen.

## Nicht im Umfang

- Cloud-/KI-Dienste, Speichern der Besitzerseite, Wurmkur/Echinococcus, ausländische
  Passlayouts (nur EU-Heimtierausweis; andere Pässe → keine/unsichere Vorschläge),
  automatisches Übernehmen ohne Bestätigung, manuelles Eckenziehen.

## Risiken

- Größerer Download beim Update (~70 MB) – Updater installiert `requirements.txt`; im
  Windows-Test prüfen, dass eine fehlgeschlagene Installation die App nicht blockiert.
- OCR-Qualität schwankt mit Fotoqualität → deshalb Ausschnitt neben jedem Vorschlag und
  Plausibilitätsprüfung; Qualität mit Kais Pass (lokal) vor jedem Release der Stufe 5 messen.
