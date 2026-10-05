# nachweise.py - Haftpflicht-Nachweise (PDF/Foto) speichern und auslesen
#
# Ablage: instance/nachweise/<sha256>.<endung>
#   - Der Dateiname ist die Prüfsumme des Inhalts. Eine Datei wird nie
#     überschrieben oder gelöscht - ein Nachweis bleibt als Nachweis erhalten.
#   - Gleicher Inhalt = gleiche Datei (doppeltes Hochladen kostet keinen Platz).
#   - backup.py sichert den Ordner mit und prüft jede Datei anhand ihres Namens.

import hashlib
import io
import os
import re
from datetime import date

from dateutil.relativedelta import relativedelta

import backup

NACHWEIS_DIR = backup.NACHWEIS_DIR  # eine Quelle der Wahrheit für den Ablageort
MAX_GROESSE = 25 * 1024 * 1024

# Erkannt wird am Inhalt, nicht an der Dateiendung
DATEITYPEN = {
    'pdf': (b'%PDF-', 'application/pdf'),
    'jpg': (b'\xff\xd8\xff', 'image/jpeg'),
    'png': (b'\x89PNG\r\n\x1a\n', 'image/png'),
}


class NachweisFehler(Exception):
    pass


def dateityp(daten):
    for endung, (kennung, _) in DATEITYPEN.items():
        if daten.startswith(kennung):
            return endung
    return None


def mimetype(endung):
    return DATEITYPEN[endung][1]


def dateiname(sha256, endung):
    return f'{sha256}.{endung}'


def pfad(sha256, endung):
    if not re.fullmatch(r'[0-9a-f]{64}', sha256 or '') or endung not in DATEITYPEN:
        raise NachweisFehler('Ungültiger Nachweis.')
    return os.path.join(NACHWEIS_DIR, dateiname(sha256, endung))


def speichern(daten):
    """Legt die Datei unveränderlich ab. Gibt (sha256, endung) zurück."""
    if not daten:
        raise NachweisFehler('Die Datei ist leer.')
    if len(daten) > MAX_GROESSE:
        raise NachweisFehler('Die Datei ist größer als 25 MB.')
    endung = dateityp(daten)
    if not endung:
        raise NachweisFehler('Bitte ein PDF oder ein Foto (JPG/PNG) hochladen.')

    sha256 = hashlib.sha256(daten).hexdigest()
    ziel = pfad(sha256, endung)
    if not os.path.exists(ziel):
        os.makedirs(NACHWEIS_DIR, exist_ok=True)
        tmp = ziel + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(daten)
            f.flush()
            os.fsync(f.fileno())
        backup._mit_wiederholung(os.replace, tmp, ziel)
    # Nachprüfen, was wirklich auf der Platte liegt
    if backup._sha256(ziel) != sha256:
        raise NachweisFehler('Die Datei wurde nicht korrekt gespeichert.')
    return sha256, endung


# --- Angaben aus dem PDF vorschlagen ---

MONATE = {
    'januar': 1, 'jänner': 1, 'februar': 2, 'märz': 3, 'maerz': 3, 'april': 4, 'mai': 5,
    'juni': 6, 'juli': 7, 'august': 8, 'september': 9, 'oktober': 10, 'november': 11,
    'dezember': 12,
}
_DATUM_ZAHL = r'(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})'
_DATUM_TEXT = r'(\d{1,2})\.\s*(' + '|'.join(MONATE) + r')\s+(\d{4})'


def _alle_daten(text):
    """Alle Daten im Text als (position, date) - als Zahl (05.10.2026) oder ausgeschrieben."""
    treffer = []
    for m in re.finditer(_DATUM_ZAHL, text):
        treffer.append((m.start(), int(m.group(3)), int(m.group(2)), int(m.group(1))))
    for m in re.finditer(_DATUM_TEXT, text, re.IGNORECASE):
        treffer.append((m.start(), int(m.group(3)), MONATE[m.group(2).lower()], int(m.group(1))))
    ergebnis = []
    for pos, jahr, monat, tag in sorted(treffer):
        try:
            ergebnis.append((pos, date(jahr, monat, tag)))
        except ValueError:
            continue
    return ergebnis


def _datum(text):
    daten = _alle_daten(text)
    return daten[0][1] if daten else None


def pdf_text(daten):
    """Text eines PDFs - leer, wenn das PDF nur ein Scan ist oder pypdf fehlt."""
    try:
        from pypdf import PdfReader
        leser = PdfReader(io.BytesIO(daten))
        return '\n'.join((seite.extract_text() or '') for seite in leser.pages[:5])
    except Exception:
        return ''


def angaben_vorschlagen(text):
    """Liest typische Angaben einer Versicherungsbestätigung aus. Alles nur Vorschläge."""
    vorschlag = {}
    if not text.strip():
        return vorschlag
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]

    # Versicherer: die Zeile mit der Firmenbezeichnung (PDF-Text kommt in beliebiger Reihenfolge)
    firma = re.compile(r'aktiengesellschaft|versicherungs-?\s?ag\b|\bVVaG\b|\ba\.\s?G\.|'
                       r'versicherung(?:s|en)?\s+(?:AG|SE|eG)\b|\b(?:AG|SE)$', re.IGNORECASE)
    kandidaten = [z for z in zeilen if firma.search(z) and '@' not in z
                  and not z.lower().startswith(('ihre', 'ihr ', 'postanschrift')) and len(z) < 120]
    if kandidaten:
        # Ohne Adresszusatz ("..., 10900 Berlin") bevorzugen
        kandidaten.sort(key=lambda z: (bool(re.search(r'\d', z)), len(z)))
        vorschlag['versicherer'] = kandidaten[0]

    # Vertragsnummer
    m = re.search(r'(?:versicherung|vertrag|versicherungsschein|police|vertragsnummer|'
                  r'versicherungsnummer)\D{0,40}?([A-Z]{1,5}[-/ ]?\d[\d\-/. ]{4,}\d)', text, re.IGNORECASE)
    if m:
        vorschlag['vertragsnummer'] = re.sub(r'\s+', '', m.group(1))

    # Ausstellungsdatum: Datum hinter dem Wort "Datum" (nicht "Geburtsdatum"),
    # sonst das jüngste Datum, das kein Geburtsdatum ist (Briefdatum)
    ausgestellt = None
    m = re.search(r'\bDatum\b\s*:?\s*(.{0,60})', text, re.IGNORECASE | re.DOTALL)
    if m:
        ausgestellt = _datum(m.group(1))
    if not ausgestellt:
        kandidaten = [d for pos, d in _alle_daten(text)
                      if 'geburt' not in text[max(0, pos - 30):pos].lower()]
        ausgestellt = max(kandidaten) if kandidaten else None
    if ausgestellt:
        vorschlag['ausgestellt_am'] = ausgestellt

    # Gültigkeit: ausdrückliches "gültig bis", sonst "ein Jahr ab Ausstellung"
    m = re.search(r'(?:gültig|befristet)\s+bis\s*(?:zum\s*)?(.{0,30})', text, re.IGNORECASE)
    bis = _datum(m.group(1)) if m else None
    if not bis and ausgestellt and re.search(r'ein(?:es)?\s+jahr(?:es)?', text, re.IGNORECASE):
        bis = ausgestellt + relativedelta(years=1) - relativedelta(days=1)
    if bis:
        vorschlag['gueltig_bis'] = bis

    # Tier und Chip
    m = re.search(r'Tier:[ \t]*([^,;\n]+)', text)
    if m:
        vorschlag['tier'] = m.group(1).strip()[:100]
    m = re.search(r'Chip\w*\s*(?:nummer|nr\.?)?\s*:?\s*(\d{15})', text, re.IGNORECASE)
    if m:
        vorschlag['chipnummer'] = m.group(1)
    return vorschlag
