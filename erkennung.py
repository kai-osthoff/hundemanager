# erkennung.py - Vorschläge aus Fotos des EU-Heimtierausweises (erster Entwurf)
#
# Wir können nicht beeinflussen, was Halter fotografieren: eine Seite, eine Doppelseite,
# nur einen Teil, schräg, quer, ein ganz anderes Dokument oder einen Pass aus dem Ausland.
# Deshalb hängt hier NICHTS an festen Positionen oder an der Reihenfolge der Textblöcke:
#
#   1. Texterkennung (RapidOCR, läuft lokal, nichts geht ins Internet) liefert Textblöcke
#      mit ihrer Lage im Bild.
#   2. Merkmale entscheiden, was zu sehen ist: Überschriften der Passseiten und
#      Beschriftungen der Felder. Der EU-Heimtierausweis ist in jedem Land zweisprachig
#      (Landessprache + Englisch) - die englischen Merkmale gelten deshalb überall.
#   3. Ein Wert gehört zu einer Beschriftung, wenn er im Bereich darunter steht (bis zur
#      nächsten Beschriftung). Freistehende Daten werden nie verwendet.
#   4. Handschrift zerfällt oft in Stücke ("27.02." + "26") - die werden zusammengesetzt.
#      Ist ein Feld leer geblieben, wird es vergrößert ein zweites Mal gelesen.
#   5. Plausibilität: "gültig bis" muss passend nach dem Impfdatum liegen. Sonst gilt die
#      Zeile als unsicher (durchgestrichen, überschrieben, unlesbar) und wird NICHT
#      vorausgefüllt - Saskia sieht sie nur als Hinweis mit Bildausschnitt.
#
# Alles sind nur Vorschläge, Saskia bestätigt. Gespeichert wird kein erkannter Volltext.
# Von der Besitzerseite (Namen, Adressen, Telefon) wird nichts übernommen.
#
# Fehlt RapidOCR (Installation nicht nachgezogen), liefert verfuegbar() False und die App
# läuft wie bisher ohne Vorschläge.

import difflib
import importlib.util
import io
import re
import threading
from collections import Counter, namedtuple
from datetime import date

from dateutil.relativedelta import relativedelta

import bilder
import impfstoffe

Block = namedtuple('Block', 'text x0 y0 x1 y1')

ANALYSE_KANTE = 2600     # gemessen: kleiner verliert handschriftliche Daten, größer bringt nichts
NACHLESEN_FAKTOR = 2     # leere Felder werden so stark vergrößert ein zweites Mal gelesen
_AEHNLICH = 0.85         # so ähnlich muss ein Merkmal sein (OCR verliest einzelne Buchstaben)

# Beschriftungen der Felder (kompakt: klein, ohne Umlaute, Leerzeichen und Satzzeichen)
FELDER = {
    'impfdatum': ['impfdatum', 'vaccinationdate'],
    'gueltig_ab': ['gultigab', 'validfrom'],
    'gueltig_bis': ['gultigbis', 'validuntil'],
    'geburtsdatum': ['geburtsdatum', 'dateofbirth'],
}

# Überschriften der Passseiten mit Gewicht - Englisch zählt am meisten
SEITEN = {
    'besitzer': [('angabenzumbesitzer', 2), ('detailsofownership', 3)],
    'beschreibung': [('beschreibungdestieres', 2), ('descriptionofanimal', 3)],
    'kennzeichnung': [('kennzeichnungdestieres', 2), ('markingofanimal', 3)],
    'ausstellung': [('ausstellungdesausweises', 2), ('issuingofthepassport', 3)],
    'tollwut': [('tollwutimpfung', 2), ('vaccinationagainstrabies', 3)],
    'titer': [('antikorper', 2), ('antibody', 3), ('serological', 3)],
    'parasiten': [('echinococcus', 3), ('parasitenbehandlung', 2), ('antiparasite', 3)],
    'impfungen': [('sonstigeimpfungen', 2), ('othervaccinations', 3)],
    'untersuchung': [('klinischeuntersuchung', 2), ('clinicalexamination', 3)],
}
IMPF_SEITEN = (None, 'tollwut', 'impfungen')       # nur hier stehen Impfzeilen
GEBURT_SEITEN = (None, 'beschreibung')             # nie von der Besitzerseite

# Abstand Impfdatum -> gültig bis: Grundimmunisierung ab ca. 4 Wochen, Tollwut bis 3 Jahre
_MIN_GUELTIG = relativedelta(days=28)
_MAX_GUELTIG = relativedelta(years=3, days=31)
_MAX_ZUKUNFT = relativedelta(years=5)

_PASS_GANZ = re.compile(r'^([A-Z]{2}\d{2})(\d{6,9})$')
_PASS_LAND = re.compile(r'^[A-Z]{2}\d{2}$')
_PASS_ZAHL = re.compile(r'^\d{6,9}$')
_DATUM = re.compile(r'(?<!\d)(\d{1,2})(?:\s*[./-]\s*|\s+)(\d{1,2})(?:\s*[./-]\s*|\s+)(\d{4}|\d{2})(?!\d)')


# --- Texte vergleichen ---

def _kompakt(text):
    text = (text or '').lower()
    for alt, neu in (('ä', 'a'), ('ö', 'o'), ('ü', 'u'), ('ß', 'ss'), ('à', 'a'), ('é', 'e')):
        text = text.replace(alt, neu)
    return re.sub(r'[^a-z0-9]', '', text)


def _aehnlichkeit(kompakt, wort):
    """Wie gut kommt das Wort im Text vor (0..1)? 'dultigbis' enthält 'gultigbis' zu 0,89."""
    if wort in kompakt:
        return 1.0
    n = len(wort)
    if len(kompakt) < n - 1:
        return 0.0
    beste = 0.0
    for i in range(max(1, len(kompakt) - n + 1)):
        vergleich = difflib.SequenceMatcher(None, kompakt[i:i + n], wort, autojunk=False)
        if vergleich.real_quick_ratio() > max(beste, _AEHNLICH - 0.01) and vergleich.quick_ratio() > beste:
            beste = max(beste, vergleich.ratio())
    return beste


def _enthaelt(kompakt, wort):
    return _aehnlichkeit(kompakt, wort) >= _AEHNLICH


def datum_lesen(text):
    """'13.12.22', '19/09/2025', '27.02. 26' -> date. Monat-Jahr ('05-2026', Verfall des
    Impfstoffs) und Zusammengezogenes ('07.122022') sind kein Datum -> None."""
    for treffer in _DATUM.finditer((text or '').replace(',', '.')):
        tag, monat, jahr = (int(g) for g in treffer.groups())
        if jahr < 100:
            jahr += 2000
        try:
            return date(jahr, monat, tag)
        except ValueError:
            continue
    return None


# --- Lage im Bild ---

def _hoehe(b):
    return b.y1 - b.y0


def _mitte(b):
    return (b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2


def _zeilen(bloecke):
    """Blöcke zu Textzeilen gruppieren (gleiche Höhe), jede Zeile von links nach rechts."""
    zeilen = []
    for b in sorted(bloecke, key=lambda b: _mitte(b)[1]):
        if zeilen:
            erste = zeilen[-1][0]
            if abs(_mitte(b)[1] - _mitte(erste)[1]) < 0.6 * max(_hoehe(b), _hoehe(erste)):
                zeilen[-1].append(b)
                continue
        zeilen.append([b])
    return [sorted(z, key=lambda b: b.x0) for z in zeilen]


def _text(bloecke):
    return ' '.join(' '.join(b.text for b in z) for z in _zeilen(bloecke))


def _im_bereich(bloecke, x0, y0, x1, y1):
    """Blöcke, deren Mitte im Bereich liegt."""
    return [b for b in bloecke if x0 <= _mitte(b)[0] <= x1 and y0 <= _mitte(b)[1] <= y1]


# --- Auswertung ---

def _beschriftung(b):
    # Die beste Übereinstimmung gewinnt: "gültig bis" ähnelt auch "gültig ab"
    k = _kompakt(b.text)
    wertung = max(((max(_aehnlichkeit(k, w) for w in woerter), art) for art, woerter in FELDER.items()))
    return wertung[1] if wertung[0] >= _AEHNLICH else None


def _ueberschriften(bloecke):
    treffer = []
    for b in bloecke:
        k = _kompakt(b.text)
        for seite, merkmale in SEITEN.items():
            gewicht = sum(g for wort, g in merkmale if _enthaelt(k, wort))
            if gewicht:
                treffer.append((seite, gewicht, b))
    return treffer


def _seite_von(block, ueberschriften, breite):
    """Zu welcher Passseite gehört ein Block? Die nächste Überschrift darüber - bevorzugt in
    derselben Bildhälfte (zwei Seiten nebeneinander). Ohne Überschrift: None (unbekannt)."""
    darueber = [(seite, b) for seite, _, b in ueberschriften if b.y0 <= block.y0 + _hoehe(block)]
    nah = [(s, b) for s, b in darueber if abs(_mitte(b)[0] - _mitte(block)[0]) < 0.6 * breite]
    kandidaten = nah or darueber
    if not kandidaten:
        return None
    return min(kandidaten, key=lambda sb: block.y0 - sb[1].y0)[0]


def _passnummer(bloecke, breite, hoehe):
    kandidaten = []
    for b in bloecke:
        k = re.sub(r'\s', '', b.text.upper())
        if _PASS_GANZ.match(k):
            kandidaten.append(k)
    # Am Seitenrand steht die Nummer oft senkrecht und wird in zwei Blöcken gelesen
    laender = [b for b in bloecke if _PASS_LAND.match(b.text.strip().upper())]
    zahlen = [b for b in bloecke if _PASS_ZAHL.match(b.text.strip())]
    for land in laender:
        for zahl in zahlen:
            (lx, ly), (zx, zy) = _mitte(land), _mitte(zahl)
            if ((lx - zx) ** 2 + (ly - zy) ** 2) ** 0.5 < 0.1 * max(breite, hoehe):
                kandidaten.append(land.text.strip().upper() + zahl.text.strip())
    return kandidaten


def _wert_unter(beschriftung, bloecke, spalte, bis_y, nachlesen):
    """Text im Feld unter einer Beschriftung -> (date|None, gelesener Text)."""
    h = _hoehe(beschriftung)
    bereich = (spalte[0], beschriftung.y1 - 0.3 * h, spalte[1], bis_y)
    text = _text(_im_bereich(bloecke, *bereich))
    datum = datum_lesen(text)
    if datum is None and text and nachlesen is not None:  # ganz leere Felder nicht nachlesen
        nochmal = _text(nachlesen(*bereich))
        if datum_lesen(nochmal):
            return datum_lesen(nochmal), nochmal
        text = text or nochmal
    return datum, text.strip()[:40]


def _impfzeile(label, alle_labels, werte, aufkleber_bloecke, breite, hoehe, ist_tollwut, heute, nachlesen):
    w, h = label.x1 - label.x0, _hoehe(label)
    spalte = (label.x0 - 0.15 * w, label.x1 + 0.35 * w)

    def in_spalte(b):
        return spalte[0] <= _mitte(b)[0] <= spalte[1]

    darunter = sorted((b for art, b in alle_labels if in_spalte(b) and b.y0 > label.y0 and art == 'impfdatum'),
                      key=lambda b: b.y0)
    ende = darunter[0].y0 - 0.3 * h if darunter else min(hoehe, label.y0 + 14 * h)
    in_zeile = sorted(((art, b) for art, b in alle_labels if in_spalte(b) and label.y0 <= b.y0 < ende),
                      key=lambda ab: ab[1].y0)

    def feld_ende(b):
        # bis zur nächsten Beschriftung, höchstens drei Zeilenhöhen - fehlt die nächste Beschriftung
        # (unlesbar), landet sonst der Wert darunter im falschen Feld
        naechste = [x.y0 for _, x in in_zeile if x.y0 > b.y0]
        return min(min(naechste) + 0.2 * h if naechste else ende, b.y1 + 3 * h)

    impfdatum, _ = _wert_unter(label, werte, spalte, feld_ende(label), nachlesen)
    bis_label = next((b for art, b in in_zeile if art == 'gueltig_bis'), None)
    if bis_label is not None:
        gueltig_bis, text_bis = _wert_unter(bis_label, werte, spalte, feld_ende(bis_label), nachlesen)
    else:
        # Beschriftung unlesbar: das unterste Datum der Zeile, das nicht unter "gültig ab" steht
        ab = next((b for art, b in in_zeile if art == 'gueltig_ab'), None)
        rest = [b for b in _im_bereich(werte, spalte[0], feld_ende(label), spalte[1], ende)
                if ab is None or not (ab.y1 - 0.3 * h <= _mitte(b)[1] <= feld_ende(ab))]
        datiert = [(datum_lesen(_text(z)), z) for z in _zeilen(rest)]
        datiert = [(d, z) for d, z in datiert if d]
        gueltig_bis, text_bis = (datiert[-1][0], _text(datiert[-1][1])) if datiert else (None, _text(rest)[:40])
    if any(art == 'gueltig_ab' for art, _ in in_zeile):
        ist_tollwut = True  # "gültig ab" gibt es nur auf der Tollwutseite

    # Aufkleber links neben der Datumsspalte, in derselben Zeile
    links = [b for b in aufkleber_bloecke
             if b.x1 <= label.x0 + 0.1 * w and b.x0 >= label.x0 - 3.5 * w and label.y0 - 0.6 * h <= _mitte(b)[1] < ende]
    felder, namen = [], []
    for zeile in _zeilen(links):
        # Jeder Aufkleber für sich; nur wenn keiner passt, Nachbarn zusammen ("Virbagen®" + "canis L")
        treffer = [impfstoffe.zuordnen(b.text) for b in zeile]
        if not any(treffer):
            treffer = [impfstoffe.zuordnen(a.text + ' ' + b.text) for a, b in zip(zeile, zeile[1:])]
        for t in filter(None, treffer):
            if t['name'] not in namen:
                namen.append(t['name'])
                felder += [f for f in t['felder'] if f not in felder]
    if ist_tollwut and impfstoffe.T not in felder:
        felder.append(impfstoffe.T)

    sicher, grund = _plausibel(felder, impfdatum, gueltig_bis, heute)
    x0 = min([b.x0 for b in links] + [spalte[0]])
    box = (max(0.0, x0 / breite), max(0.0, (label.y0 - 0.6 * h) / hoehe),
           min(1.0, (spalte[1] - x0) / breite), min(1.0, (ende - label.y0 + 2.1 * h) / hoehe))  # Handschrift ragt nach unten
    return {
        'felder': [f for f in impfstoffe.IMPFUNG_INFO if f in felder],
        'impfstoffe': namen,
        'impfdatum': impfdatum.isoformat() if impfdatum else None,
        'gueltig_bis': gueltig_bis.isoformat() if gueltig_bis else None,
        'text_bis': text_bis,
        'sicher': sicher,
        'grund': grund,
        'box': [round(v, 4) for v in box],
    }


def _plausibel(felder, impfdatum, gueltig_bis, heute):
    if not felder:
        return False, 'Impfstoff nicht erkannt'
    if impfdatum is None:
        return False, 'Impfdatum nicht lesbar'
    if gueltig_bis is None:
        return False, '„Gültig bis“ nicht lesbar'
    if impfdatum.year < 2000 or impfdatum > heute:
        return False, 'Impfdatum kann nicht stimmen'
    if gueltig_bis > heute + _MAX_ZUKUNFT:
        return False, '„Gültig bis“ liegt zu weit in der Zukunft'
    if not impfdatum + _MIN_GUELTIG <= gueltig_bis <= impfdatum + _MAX_GUELTIG:
        return False, '„Gültig bis“ passt nicht zum Impfdatum'
    return True, ''


def _geburtstag(labels, werte, ueberschriften, breite, heute):
    for art, label in labels:
        if art != 'geburtsdatum' or _seite_von(label, ueberschriften, breite) not in GEBURT_SEITEN:
            continue
        h = _hoehe(label)
        for bereich in ((label.x0, label.y0 - 0.8 * h, breite, label.y1 + 1.2 * h),           # rechts daneben
                        (label.x0, label.y1, label.x1 + (label.x1 - label.x0), label.y1 + 2.5 * h)):  # darunter
            datum = datum_lesen(_text(_im_bereich(werte, *bereich)))
            if datum and 1990 <= datum.year and datum <= heute:
                return datum.isoformat()
    return None


def auswerten(bloecke, breite, hoehe, nachlesen=None, heute=None):
    """Textblöcke eines Fotos -> erkannte Seiten und Werte. nachlesen(x0, y0, x1, y1) liest
    einen Bildbereich vergrößert noch einmal (Liste von Blöcken) - in Tests None."""
    heute = heute or date.today()
    ueberschriften = _ueberschriften(bloecke)
    punkte = Counter()
    for seite, gewicht, _ in ueberschriften:
        punkte[seite] += gewicht
    labels = [(art, b) for b in bloecke for art in [_beschriftung(b)] if art]
    label_bloecke = {id(b) for _, b in labels}
    werte = [b for b in bloecke if id(b) not in label_bloecke]

    zeilen = []
    for art, label in sorted(labels, key=lambda ab: (ab[1].y0, ab[1].x0)):
        if art != 'impfdatum':
            continue
        seite = _seite_von(label, ueberschriften, breite)
        if seite not in IMPF_SEITEN:
            continue
        zeile = _impfzeile(label, labels, werte, werte, breite, hoehe, seite == 'tollwut', heute, nachlesen)
        if zeile['impfstoffe'] or zeile['impfdatum'] or zeile['gueltig_bis']:
            zeilen.append(zeile)  # leere Zeilen des Passes nicht melden

    pass_kandidaten = _passnummer(bloecke, breite, hoehe)
    return {
        'seiten': sorted(s for s, p in punkte.items() if p >= 2),
        'passnummer': Counter(pass_kandidaten).most_common(1)[0][0] if pass_kandidaten else None,
        'geburtstag': _geburtstag(labels, werte, ueberschriften, breite, heute),
        'zeilen': zeilen,
    }


def zusammenfassen(ergebnisse):
    """Ergebnisse mehrerer Fotos (None = nicht ausgewertet) -> ein Vorschlag für den Dialog."""
    seiten, zeilen, paesse, geburtstag = set(), [], Counter(), None
    vorschlag = {}
    for nr, e in enumerate(ergebnisse):
        if not e:
            continue
        seiten.update(e['seiten'])
        if e['passnummer']:
            paesse[e['passnummer']] += 1
        geburtstag = geburtstag or e['geburtstag']
        for z in e['zeilen']:
            zeilen.append(dict(z, seite=nr))
            if z['sicher']:
                for feld in z['felder']:
                    if z['gueltig_bis'] > vorschlag.get(feld, ''):
                        vorschlag[feld] = z['gueltig_bis']
    # Ein unsicher gelesenes, späteres "gültig bis" (z. B. Impfdatum unleserlich) heißt: der
    # Vorschlag ist vermutlich veraltet - dann lieber nichts vorausfüllen, Saskia sieht den Hinweis
    zeilen.sort(key=lambda z: z['gueltig_bis'] or '', reverse=True)  # das Neueste zuerst
    offen = sorted({f for z in zeilen if not z['sicher'] and z['gueltig_bis'] for f in z['felder']
                    if z['gueltig_bis'] > vorschlag.get(f, '')})
    for feld in offen:
        vorschlag.pop(feld, None)
    return {
        'erkannt': bool(seiten or zeilen),
        'offen': offen,
        'seiten': sorted(seiten),
        'vorschlag': vorschlag,
        'passnummer': paesse.most_common(1)[0][0] if paesse else None,
        'geburtstag': geburtstag,
        'zeilen': zeilen,
    }


def rueckmeldung(erkannt, eingetragen):
    """Was hat Saskia aus den Vorschlägen gemacht? Nur je Feld ein Wort, keine Inhalte - damit
    spätere Versionen der Erkennung gezielt besser werden. eingetragen: {feld: 'JJJJ-MM-TT'}"""
    felder = {}
    for feld, wert in erkannt.get('vorschlag', {}).items():
        if feld not in eingetragen:
            felder[feld] = 'geleert'
        else:
            felder[feld] = 'uebernommen' if eingetragen[feld] == wert else 'geaendert'
    for feld in erkannt.get('offen', []):
        felder[feld] = 'offen-eingetragen' if feld in eingetragen else 'offen-leer'
    return {'version': 1, 'erkannt': bool(erkannt.get('erkannt')), 'seiten': erkannt.get('seiten', []),
            'zeilen': len(erkannt.get('zeilen', [])),
            'sicher': sum(1 for z in erkannt.get('zeilen', []) if z.get('sicher')), 'felder': felder}


# --- Texterkennung (RapidOCR) ---

_ocr = None
_ocr_sperre = threading.Lock()


def verfuegbar():
    return bilder.verfuegbar() and importlib.util.find_spec('rapidocr') is not None


def _lesen(bild_bytes):
    """Bild (JPEG/PNG-Bytes) -> Textblöcke. Eine Erkennung zur Zeit (Speicher, Windows)."""
    global _ocr
    with _ocr_sperre:
        if _ocr is None:
            import logging
            from rapidocr import RapidOCR
            logging.getLogger('RapidOCR').setLevel(logging.WARNING)
            _ocr = RapidOCR()
        ergebnis = _ocr(bild_bytes)
    if ergebnis.boxes is None or ergebnis.txts is None:
        return []
    bloecke = []
    for box, text in zip(ergebnis.boxes, ergebnis.txts):
        xs, ys = [float(p[0]) for p in box], [float(p[1]) for p in box]
        bloecke.append(Block(str(text), min(xs), min(ys), max(xs), max(ys)))
    return bloecke


def foto_auswerten(daten, drehung=0):
    """Foto eines Nachweises -> Ergebnis von auswerten() oder None (kein Bild, keine OCR, Fehler)."""
    if not verfuegbar():
        return None
    try:
        from PIL import Image
        ansicht = bilder.ansicht(daten, drehung, ANALYSE_KANTE)
        if ansicht is None:
            return None
        bild = Image.open(io.BytesIO(ansicht[0])).convert('RGB')
        breite, hoehe = bild.size

        def nachlesen(x0, y0, x1, y1):
            x0, y0 = max(0, int(x0)), max(0, int(y0))
            x1, y1 = min(breite, int(x1)), min(hoehe, int(y1))
            if x1 - x0 < 10 or y1 - y0 < 10:
                return []
            f = NACHLESEN_FAKTOR
            stueck = bild.crop((x0, y0, x1, y1)).resize(((x1 - x0) * f, (y1 - y0) * f), Image.LANCZOS)
            puffer = io.BytesIO()
            stueck.save(puffer, 'PNG')
            return [Block(b.text, x0 + b.x0 / f, y0 + b.y0 / f, x0 + b.x1 / f, y0 + b.y1 / f)
                    for b in _lesen(puffer.getvalue())]

        return auswerten(_lesen(ansicht[0]), breite, hoehe, nachlesen)
    except Exception as e:  # Erkennung ist nur ein Vorschlag - nie das Hochladen blockieren
        print(f'Erkennung übersprungen: {e.__class__.__name__}: {e}')
        return None
