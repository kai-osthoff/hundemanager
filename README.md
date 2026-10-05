# 🐕 Hundemanager

## Einmalig: Update-Funktion einrichten

Ab Version 5.1.0 kann sich der Hundemanager **per Knopfdruck selbst aktualisieren**.
Damit das klappt, musst du die neue Version **ein einziges Mal von Hand** einspielen.
Das dauert etwa 5 Minuten. **Deine Daten bleiben dabei vollständig erhalten.**

### 1. Hundemanager schließen

Schließ das schwarze Fenster, in dem der Hundemanager läuft (falls er gerade offen ist).

### 2. Sicherheitskopie anlegen

1. Öffne den **Ordner, in dem dein Hundemanager liegt**: Das ist der Ordner mit der Datei `START.bat`
   und einem Unterordner `instance`.
2. Geh im Explorer **eine Ebene höher**, sodass du den Hundemanager-Ordner selbst siehst.
3. Rechtsklick auf den Ordner → **Kopieren**, dann auf dem **Desktop** Rechtsklick → **Einfügen**.

Jetzt hast du eine komplette Sicherung auf dem Desktop. Falls irgendetwas schiefgeht, ist nichts verloren.

### 3. Neue Version herunterladen

👉 **[Hundemanager 5.1.0 herunterladen (ZIP)](https://github.com/kai-osthoff/hundemanager/archive/refs/tags/v5.1.0.zip)**

Die Datei `hundemanager-5.1.0.zip` landet in deinem **Downloads**-Ordner.

### 4. ZIP entpacken

1. Öffne den Ordner **Downloads**.
2. Rechtsklick auf `hundemanager-5.1.0.zip` → **Alle extrahieren…** → **Extrahieren**.
3. Es öffnet sich ein Ordner. Darin liegt noch ein Ordner `hundemanager-5.1.0`. **Öffne ihn.**
   Du siehst jetzt Dateien wie `app.py`, `START.bat`, `start.py` und den Ordner `templates`.

### 5. Dateien in deinen Hundemanager-Ordner kopieren

1. Drück **Strg + A** (alles markieren), dann **Strg + C** (kopieren).
2. Öffne deinen **Hundemanager-Ordner** (der mit dem Unterordner `instance`).
3. Drück **Strg + V** (einfügen).
4. Windows fragt, ob Dateien ersetzt werden sollen → **„Dateien im Ziel ersetzen“** wählen.

> Der Ordner `instance` mit deinen Daten ist im Download **nicht** enthalten und wird deshalb nicht überschrieben.

### 6. Starten

Doppelklick auf **`START.bat`**.

- Falls Windows meldet **„Der Computer wurde durch Windows geschützt“**: auf **Weitere Informationen**
  klicken, dann auf **Trotzdem ausführen**. Das passiert nur, weil die Datei aus dem Internet kommt.
- Beim ersten Start installiert der Hundemanager ggf. noch fehlende Programmteile. Das kann **1–2 Minuten**
  dauern (Internet nötig).
- Danach **öffnet sich der Browser von selbst** mit deinem Hundemanager.

### 7. Prüfen

- Ganz **unten auf der Seite** steht jetzt **„Version 5.1.0“** und daneben **„Nach Updates suchen“**.
- Alle deine Personen und Hunde sind wie gewohnt da.

**Fertig!** 🎉 Die ZIP-Datei und den entpackten Ordner in Downloads kannst du jetzt löschen.
Die Sicherung auf dem Desktop würde ich ein paar Wochen aufheben.

---

## Künftige Updates

Gibt es eine neue Version, erscheint oben im Hundemanager ein **blauer Hinweis**.
Unter „Was ist neu?“ steht, was sich geändert hat. Ein Klick auf **„Jetzt aktualisieren“**, kurz warten, fertig.

Vor jedem Update sichert der Hundemanager automatisch deine Daten im Ordner `instance\backup`.

## Wenn etwas nicht klappt

- **Der Hundemanager startet nicht oder Daten fehlen:** Schwarzes Fenster schließen, deinen Hundemanager-Ordner
  löschen und die Sicherung vom Desktop an seine Stelle kopieren. Dann ist alles wieder wie vorher.
- **Bitte Bescheid geben**, am besten mit einem Foto vom schwarzen Fenster.

---

<sub>Für Entwickler: siehe `CLAUDE.md` und `release.sh`.</sub>
