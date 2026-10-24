# Nachrichten-Vorlagen: Erinnerung oder Nachfrage

**Datum:** 2026-10-24 · **Anlass:** Feedback von Saskia (siehe unten) · **Entwurf:** https://claude.ai/artifact/81qoCUYjuHL36FTGA7EnVY

## Problem

Die WhatsApp-/E-Mail-Nachricht von der Hundekarte sagt immer „fehlen mir noch ein paar Angaben“ – auch
wenn nur eine Impfung in drei Wochen abläuft. Saskia möchte dann einen freundlichen Hinweis („friendly
reminder“), eine klare Nachfrage nur, wenn wirklich etwas fehlt oder abgelaufen ist. Ihr Mischfall
(„aber wenn dann noch Haftpflicht fehlt, passt's ja auch wieder nicht … schwierig“) braucht eine Regel.
Kai will, dass Saskia den Wortlaut selbst festlegt, statt vor jedem Versand den Text umzuschreiben.

## Entscheidung

- **Zwei Vorlagen** in den Einstellungen, Abschnitt „Nachrichten an Halter“:
  - **Erinnerung** – nur, wenn alles da ist und etwas bald abläuft.
  - **Nachfrage** – sobald etwas fehlt oder abgelaufen ist, **auch im Mischfall**. Alle Punkte stehen
    in einer Liste; die Zeile selbst sagt, was nur bald fällig ist („läuft am … ab“).
- Beide Vorlagen gelten für die Hundekarte **und** die Impfpass-Nachfrage (Nachweis-Seite, `/nachweise`).
  Dort enthält die Liste nur Impfungen. Vier Vorlagen (2 Töne × 2 Orte) wären Saskia zu viel.
- **Platzhalter:** `{vorname}` (Rufname oder Vorname), `{hund}`, `{punkte}` (eine Zeile je Punkt mit „•“),
  `{antwortweg}` („hier per WhatsApp“ / „als Antwort auf diese E-Mail“). Groß-/Kleinschreibung egal,
  einzelne Klammern bleiben Text. Beim Speichern werden unbekannte Platzhalter (Tippfehler) und Vorlagen
  ohne `{punkte}` abgelehnt – ohne Liste wüsste der Halter nicht, worum es geht.
- **Unverändert fest:** Foto nachfordern, Fotoeinwilligung, Kontaktdaten beim Vorstand.
- **E-Mail-Betreff** je Ton: „Bello: Erinnerung“ bzw. „Bello: fehlende Angaben“ (Impfpass-Seite weiter „Bello: Impfpass“).
- **Hundekarte:** „1 läuft bald ab – erinnern“ statt „1 Angabe fehlt – anfragen“, Knopf-Titel passend.

## Umsetzung

- `whatsapp.py`: `PLATZHALTER`, `VORLAGE_ERINNERUNG`, `VORLAGE_NACHFRAGE`, `vorlage_fehler()`,
  `nachfrage_nachricht(vorlage, vorname, hundename, punkte, kanal)`; ersetzt `fehlende_daten_nachricht`
  und `impfpass_nachricht`.
- `app.py`: Einstellungen `nachricht_erinnerung`/`nachricht_nachfrage` (Art `vorlage`), `nachricht_ton()`,
  `nachfrage_text()`, `BETREFF`; `hund_ansicht()` liefert `ton`. Textfelder: `\r\n` → `\n`.
  Vorschau im Dialog: `vorlagen_beispiel()` + Filter `nachricht_beispiel`.
- `_einstellungen_formular.html`: je Vorlage Karte mit Textfeld, Platzhalter-Chips (fügen an der
  Schreibmarke ein), „Standardtext einsetzen“, WhatsApp-Vorschau mit Beispiel (Max/Bello). Live-Vorschau
  und Chips: Skript in `base.html`; Schließen ohne Speichern setzt zurück (`form.reset()`).
- Tests: `WhatsAppTests` (Vorlage füllen, Fehler), `NachrichtenVorlagenTests` (Ton je Datenlage, Mischfall,
  eigene Vorlage, CRLF, Ablehnung, Standard).

## Saskias Feedback (WhatsApp, 24.10.2026)

> Eine Idee hab ich noch, kann man die WhatsApp-Nachricht dahingehend anpassen, dass wenn es nur eine
> Erinnerung ist, dass etwas bald abläuft, nicht dran steht, das was fehlt, sondern dass es ein friendly
> reminder ist, dass bald was abläuft? […] Hm, aber wenn dann noch Haftpflicht fehlt, passt's ja auch
> wieder nicht … schwierig.
