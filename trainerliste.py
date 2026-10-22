# trainerliste.py - Übersicht für Trainer: wer darf auf den Platz?
#
# Erzeugt aus fertigen Zeilen (app.py sammelt sie aus hund_ansicht() und Person.foto_status)
# ein PDF (fpdf2: Ampel-Übersicht + Einzelheiten mit Datum) und ein Bild (Pillow: nur die
# Übersicht, für WhatsApp). Keine Flask- oder Datenbank-Abhängigkeit - direkt testbar.
#
# Zeilenformat:
#   {'halter': 'Jürgen Müller', 'hund': 'Bello',
#    'impfungen': [{'name': 'L', 'status': 'gueltig'|'bald-ablaufend'|'abgelaufen'|'keine-angabe', 'datum': date|None}, ...],
#    'haftpflicht': {'status': 'gueltig'|'bald-ablaufend'|'abgelaufen'|'keine-angabe'|'ohne-nachweis', 'datum': date|None},
#    'foto': 'nachgewiesen'|'ohne-nachweis'|'fehlt'|'widerrufen'}
#
# Die Ampel "Training" bilden nur Impfung und Haftpflicht. Die Fotoeinwilligung ist kein
# Kriterium fürs Training und bekommt eigene Symbole: erlaubt (Kamera), offen (Fragezeichen -
# die Trainer dürfen nur darum bitten) und nein (durchgestrichene Kamera - nicht abbilden).

import io
import logging
import os

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

# Beim Einbetten von Segoe UI meldet fonttools Tabellen, die es nicht verkleinern kann
# ("MERG NOT subset") - harmlos, soll Saskias Konsole aber nicht füllen
logging.getLogger('fontTools.subset').setLevel(logging.ERROR)

TITEL = 'Hundeplatz - Übersicht für Trainer'
VEREIN = 'HSV Großbottwar e.V.'
EINZELHEITEN = 'Einzelheiten - was beim Mitglied nachzufragen ist'
SPALTEN = ('Halter', 'Hund', 'Impfung', 'Haftpflicht', 'Fotoeinwilligung')
LEGENDE_TRAINING = (
    ('ok', 'in Ordnung'),
    ('bald', 'läuft in weniger als einem Monat ab'),
    ('fehlt', 'abgelaufen oder fehlt (Haftpflicht ohne Nachweis)'),
)
HINWEIS_IMPFUNG = 'Impfung: SHP/DAP/DHP, L, BbPi und T zusammen - die schlechteste zählt.'
HINWEIS_EINZELHEITEN = 'Einzelheiten mit Datum auf den folgenden Seiten.'
LEGENDE_FOTO = (
    ('erlaubt', 'Fotos erlaubt'),
    ('offen', 'liegt nicht vor - bitte um die Einwilligung bitten'),
    ('nein', 'NEIN - nicht abbilden'),
)
FARBEN = {
    'ok': (46, 125, 50), 'bald': (242, 169, 0), 'fehlt': (198, 40, 40),
    'erlaubt': (46, 125, 50), 'offen': (122, 133, 126), 'nein': (21, 32, 26),
    'text': (21, 32, 26), 'grau': (85, 98, 90), 'linie': (217, 223, 219), 'trenn': (154, 165, 158),
    'weiss': (255, 255, 255),
}

_IMPFUNG = {'gueltig': 'ok', 'bald-ablaufend': 'bald', 'abgelaufen': 'fehlt', 'keine-angabe': 'fehlt'}
_HAFTPFLICHT = {'gueltig': 'ok', 'bald-ablaufend': 'bald', 'abgelaufen': 'fehlt',
                'keine-angabe': 'fehlt', 'ohne-nachweis': 'fehlt'}
_FOTO = {'nachgewiesen': 'erlaubt', 'ohne-nachweis': 'erlaubt', 'fehlt': 'offen', 'widerrufen': 'nein'}
_RANG = {'ok': 0, 'bald': 1, 'fehlt': 2}


def ampel(zeile):
    """Die drei Symbole einer Zeile: impfung/haftpflicht ok|bald|fehlt, foto erlaubt|offen|nein."""
    impfung = max((_IMPFUNG[i['status']] for i in zeile['impfungen']), key=_RANG.__getitem__, default='ok')
    return {'impfung': impfung,
            'haftpflicht': _HAFTPFLICHT[zeile['haftpflicht']['status']],
            'foto': _FOTO[zeile['foto']]}


def _datum(datum):
    return datum.strftime('%d.%m.%Y')


def punkte(zeile):
    """Nur die Abweichungen einer Zeile als (zustand, text) - leer, wenn alles passt."""
    ergebnis = []
    for i in zeile['impfungen']:
        if i['status'] == 'keine-angabe':
            ergebnis.append(('fehlt', f'Impfung {i["name"]}: Datum fehlt'))
        elif i['status'] == 'abgelaufen':
            ergebnis.append(('fehlt', f'Impfung {i["name"]}: abgelaufen am {_datum(i["datum"])}'))
        elif i['status'] == 'bald-ablaufend':
            ergebnis.append(('bald', f'Impfung {i["name"]}: läuft am {_datum(i["datum"])} ab'))
    haftpflicht = zeile['haftpflicht']
    if haftpflicht['status'] == 'keine-angabe':
        ergebnis.append(('fehlt', 'Haftpflicht: kein Nachweis'))
    elif haftpflicht['status'] == 'ohne-nachweis':
        ergebnis.append(('fehlt', 'Haftpflicht: nur angegeben, Nachweis fehlt'))
    elif haftpflicht['status'] == 'abgelaufen':
        ergebnis.append(('fehlt', f'Haftpflicht: Nachweis abgelaufen am {_datum(haftpflicht["datum"])}'))
    elif haftpflicht['status'] == 'bald-ablaufend':
        ergebnis.append(('bald', f'Haftpflicht: Nachweis läuft am {_datum(haftpflicht["datum"])} ab'))
    if zeile['foto'] == 'fehlt':
        ergebnis.append(('offen', 'Fotoeinwilligung: liegt nicht vor - bitte darum bitten'))
    elif zeile['foto'] == 'ohne-nachweis':
        ergebnis.append(('erlaubt', 'Fotoeinwilligung: laut Angabe erlaubt, Formular fehlt noch'))
    elif zeile['foto'] == 'widerrufen':
        ergebnis.append(('nein', 'Fotoeinwilligung: NEIN - nicht abbilden'))
    return ergebnis


# --- Schrift ---

# (normal, fett) - Windows 11 bringt Segoe UI und Arial mit, der Mac Arial; sonst Rückfall
_SCHRIFTEN = (
    ('segoeui.ttf', 'segoeuib.ttf'),
    ('arial.ttf', 'arialbd.ttf'),
    (os.path.join('/System', 'Library', 'Fonts', 'Supplemental', 'Arial.ttf'),
     os.path.join('/System', 'Library', 'Fonts', 'Supplemental', 'Arial Bold.ttf')),
    (os.path.join('/usr', 'share', 'fonts', 'truetype', 'dejavu', 'DejaVuSans.ttf'),
     os.path.join('/usr', 'share', 'fonts', 'truetype', 'dejavu', 'DejaVuSans-Bold.ttf')),
)


def schriftart():
    """Pfad einer System-TTF (normal) oder None - dann zeichnen beide Renderer mit ihrer Standardschrift."""
    windows_fonts = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    for normal, _ in _SCHRIFTEN:
        pfad = normal if os.path.isabs(normal) else os.path.join(windows_fonts, normal)
        if os.path.isfile(pfad):
            return pfad
    return None


def _schrift_fett(pfad):
    """Die fette Schwester der Schrift - oder dieselbe Datei, wenn es keine gibt."""
    for normal, fett in _SCHRIFTEN:
        if os.path.basename(pfad) == os.path.basename(normal):
            kandidat = os.path.join(os.path.dirname(pfad), os.path.basename(fett))
            if os.path.isfile(kandidat):
                return kandidat
    return pfad


def _gruppen(zeilen):
    """Zeilen in der gegebenen Reihenfolge nach Halter gruppiert: [(halter, [zeilen])]."""
    gruppen = []
    for zeile in zeilen:
        if gruppen and gruppen[-1][0] == zeile['halter']:
            gruppen[-1][1].append(zeile)
        else:
            gruppen.append((zeile['halter'], [zeile]))
    return gruppen


# --- PDF ---

class _Pdf(FPDF):
    SPALTEN_MM = (62, 42, 22, 24, 24)
    ZEILE = 8

    def __init__(self, stand):
        super().__init__('P', 'mm', 'A4')
        self.stand = stand
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(True, 20)
        self.alias_nb_pages()
        pfad = schriftart()
        if pfad:
            self.add_font('Hundemanager', '', pfad)
            self.add_font('Hundemanager', 'B', _schrift_fett(pfad))
            self.familie = 'Hundemanager'
        else:
            self.familie = 'Helvetica'  # Kernschrift, cp1252 - Umlaute bleiben erhalten

    def _t(self, text):
        if self.familie == 'Helvetica':
            return text.encode('cp1252', 'replace').decode('cp1252')
        return text

    def schrift(self, groesse, fett=False, farbe='text'):
        self.set_font(self.familie, 'B' if fett else '', groesse)
        self.set_text_color(*FARBEN[farbe])

    def zeile_text(self, text, hoehe, fett=False, farbe='text', groesse=10):
        self.schrift(groesse, fett, farbe)
        self.cell(0, hoehe, self._t(text))
        self.ln(hoehe)

    def header(self):
        self.schrift(16, True)
        self.cell(0, 8, self._t(TITEL))
        self.ln(8)
        self.schrift(9, False, 'grau')
        self.cell(self.epw / 2, 5, self._t(f'Stand {_datum(self.stand)} · nur aktive Halter'))
        self.cell(self.epw / 2, 5, self._t(VEREIN), align='R')
        self.ln(5)
        self.set_draw_color(*FARBEN['text'])
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
        self.ln(7)

    def footer(self):
        self.set_y(-14)
        self.schrift(8, False, 'grau')
        self.cell(self.epw / 2, 5, self._t('Erstellt mit dem Hundemanager'))
        self.cell(self.epw / 2, 5, self._t(f'Seite {self.page_no()}/{{nb}}'), align='R')

    # Symbole: Mittelpunkt (x, y) in mm, Radius r
    def symbol(self, x, y, zustand, r=2.2):
        farbe = FARBEN[zustand]
        if zustand == 'ok':
            self.set_fill_color(*farbe)
            self.ellipse(x - r, y - r, 2 * r, 2 * r, 'F')
        elif zustand == 'bald':
            self.set_fill_color(*farbe)
            self.polygon([(x, y - 1.15 * r), (x + 1.15 * r, y + 0.85 * r), (x - 1.15 * r, y + 0.85 * r)], style='F')
        elif zustand == 'fehlt':
            self.set_draw_color(*farbe)
            self.set_line_width(1.0)
            self.line(x - 0.8 * r, y - 0.8 * r, x + 0.8 * r, y + 0.8 * r)
            self.line(x - 0.8 * r, y + 0.8 * r, x + 0.8 * r, y - 0.8 * r)
            self.set_line_width(0.2)
        elif zustand == 'offen':
            self.set_draw_color(*farbe)
            self.set_line_width(0.5)
            self.ellipse(x - r, y - r, 2 * r, 2 * r, 'D')
            self.set_line_width(0.2)
            self.schrift(9, True, 'offen')
            self.set_xy(x - r, y - r)
            self.cell(2 * r, 2 * r, '?', align='C')
        else:  # erlaubt / nein: Kamera, bei nein schwarz mit rotem Strich
            self.set_fill_color(*farbe)
            self.rect(x - 1.2 * r, y - 0.7 * r, 2.4 * r, 1.6 * r, 'F')
            self.rect(x - 0.45 * r, y - 1.05 * r, 0.9 * r, 0.4 * r, 'F')
            self.set_fill_color(*FARBEN['weiss'])
            self.ellipse(x - 0.4 * r, y - 0.3 * r, 0.8 * r, 0.8 * r, 'F')
            if zustand == 'nein':
                self.set_draw_color(*FARBEN['fehlt'])
                self.set_line_width(0.8)
                self.line(x - 1.4 * r, y + 1.1 * r, x + 1.4 * r, y - 1.1 * r)
                self.set_line_width(0.2)

    def tabellenkopf(self):
        self.schrift(9, True, 'grau')
        x = self.l_margin
        for name, breite in zip(SPALTEN, self.SPALTEN_MM):
            self.set_xy(x, self.get_y())
            self.cell(breite, 6, self._t(name), align='L' if breite > 30 else 'C')
            x += breite
        self.ln(6)
        self.set_draw_color(*FARBEN['text'])
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1)

    def uebersicht(self, zeilen):
        self.tabellenkopf()
        if not zeilen:
            self.zeile_text('Keine aktiven Hunde', self.ZEILE, farbe='grau')
            return
        for halter, hunde in _gruppen(zeilen):
            halter_gedruckt = False
            for nr, zeile in enumerate(hunde):
                if self.will_page_break(self.ZEILE):
                    self.add_page()
                    self.tabellenkopf()
                    halter_gedruckt = False
                y = self.get_y()
                if nr == 0:
                    self.set_draw_color(*FARBEN['trenn'])
                else:
                    self.set_draw_color(*FARBEN['linie'])
                self.set_line_width(0.2)
                self.line(self.l_margin, y, self.w - self.r_margin, y)
                self.schrift(10)
                self.set_xy(self.l_margin, y)
                self.cell(self.SPALTEN_MM[0], self.ZEILE, self._t(halter if not halter_gedruckt else ''))
                halter_gedruckt = True
                self.cell(self.SPALTEN_MM[1], self.ZEILE, self._t(zeile['hund']))
                x = self.l_margin + self.SPALTEN_MM[0] + self.SPALTEN_MM[1]
                werte = ampel(zeile)
                for schluessel, breite in zip(('impfung', 'haftpflicht', 'foto'), self.SPALTEN_MM[2:]):
                    self.symbol(x + breite / 2, y + self.ZEILE / 2, werte[schluessel])
                    x += breite
                self.set_xy(self.l_margin, y + self.ZEILE)

    def legende(self, mit_einzelheiten):
        self.ln(6)
        self.zeile_text('Training: Impfung und Haftpflicht', 6, fett=True)
        for zustand, text in LEGENDE_TRAINING:
            self.legendenzeile(zustand, text)
        hinweis = HINWEIS_IMPFUNG + (' ' + HINWEIS_EINZELHEITEN if mit_einzelheiten else '')
        self.zeile_text(hinweis, 6, farbe='grau', groesse=9)
        self.ln(2)
        self.zeile_text('Fotoeinwilligung - kein Kriterium fürs Training', 6, fett=True)
        for zustand, text in LEGENDE_FOTO:
            self.legendenzeile(zustand, text, fett=(zustand == 'nein'))

    def legendenzeile(self, zustand, text, fett=False, hoehe=6.5):
        if self.will_page_break(hoehe):
            self.add_page()
        y = self.get_y()
        self.symbol(self.l_margin + 4, y + hoehe / 2, zustand, r=1.9)
        self.schrift(9.5, fett)
        self.set_xy(self.l_margin + 10, y)
        self.cell(0, hoehe, self._t(text))
        self.ln(hoehe)

    def einzelheiten(self, zeilen):
        self.add_page()
        self.zeile_text(EINZELHEITEN, 8, fett=True, groesse=14)
        self.zeile_text('Nur Hunde mit gelben, roten oder offenen Punkten - alle anderen fehlen hier.', 5,
                        farbe='grau', groesse=9)
        self.ln(3)
        for halter, hunde in _gruppen(zeilen):
            hunde = [(z, punkte(z)) for z in hunde]
            hunde = [(z, p) for z, p in hunde if p]
            if not hunde:
                continue
            if self.will_page_break(22):
                self.add_page()
            self.set_draw_color(*FARBEN['trenn'])
            self.set_line_width(0.2)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(2)
            self.zeile_text(halter, 7, fett=True, groesse=11)
            for zeile, liste in hunde:
                for nr, (zustand, text) in enumerate(liste):
                    if self.will_page_break(6.5):
                        self.add_page()
                    y = self.get_y()
                    if nr == 0:
                        self.schrift(10, True)
                        self.set_xy(self.l_margin + 4, y)
                        self.cell(38, 6.5, self._t(zeile['hund']))
                    self.symbol(self.l_margin + 46, y + 3.25, zustand, r=1.9)
                    self.schrift(10, zustand == 'nein')
                    self.set_xy(self.l_margin + 52, y)
                    self.cell(0, 6.5, self._t(text))
                    self.ln(6.5)
            self.ln(3)


def pdf(zeilen, stand):
    """Das PDF als Bytes: Übersicht mit Legende, danach die Einzelheiten (wenn es welche gibt)."""
    dokument = _Pdf(stand)
    dokument.add_page()
    mit_einzelheiten = any(punkte(z) for z in zeilen)
    dokument.uebersicht(zeilen)
    dokument.legende(mit_einzelheiten)
    if mit_einzelheiten:
        dokument.einzelheiten(zeilen)
    return bytes(dokument.output())


# --- Bild ---

_BREITE = 1200
_RAND = 60
_SPALTEN_PX = (400, 260, 130, 140, 150)
_ZEILE_PX = 44


def _schrift_px(groesse, fett=False):
    pfad = schriftart()
    if pfad:
        return ImageFont.truetype(_schrift_fett(pfad) if fett else pfad, groesse)
    return ImageFont.load_default(size=groesse)


def _symbol_px(draw, x, y, zustand, r=13, schrift=None):
    farbe = FARBEN[zustand]
    if zustand == 'ok':
        draw.ellipse((x - r, y - r, x + r, y + r), fill=farbe)
    elif zustand == 'bald':
        draw.polygon([(x, y - 1.15 * r), (x + 1.15 * r, y + 0.85 * r), (x - 1.15 * r, y + 0.85 * r)], fill=farbe)
    elif zustand == 'fehlt':
        draw.line((x - 0.8 * r, y - 0.8 * r, x + 0.8 * r, y + 0.8 * r), fill=farbe, width=5)
        draw.line((x - 0.8 * r, y + 0.8 * r, x + 0.8 * r, y - 0.8 * r), fill=farbe, width=5)
    elif zustand == 'offen':
        draw.ellipse((x - r, y - r, x + r, y + r), outline=farbe, width=3)
        draw.text((x, y + 1), '?', fill=farbe, font=schrift, anchor='mm')
    else:
        draw.rectangle((x - 1.2 * r, y - 0.7 * r, x + 1.2 * r, y + 0.9 * r), fill=farbe)
        draw.rectangle((x - 0.45 * r, y - 1.05 * r, x + 0.45 * r, y - 0.6 * r), fill=farbe)
        draw.ellipse((x - 0.4 * r, y - 0.3 * r, x + 0.4 * r, y + 0.5 * r), fill=FARBEN['weiss'])
        if zustand == 'nein':
            draw.line((x - 1.4 * r, y + 1.1 * r, x + 1.4 * r, y - 1.1 * r), fill=FARBEN['fehlt'], width=4)


def png(zeilen, stand):
    """Die Übersicht als PNG (1200 px breit) - ohne Einzelheiten, für WhatsApp."""
    titel, klein, kopf, text, fett = (_schrift_px(34, True), _schrift_px(18), _schrift_px(17, True),
                                      _schrift_px(21), _schrift_px(21, True))
    gruppen = _gruppen(zeilen)
    legende = 3 + len(LEGENDE_TRAINING) + 1 + 3 + len(LEGENDE_FOTO)
    hoehe = (_RAND + 100 + 50 + max(len(zeilen), 1) * _ZEILE_PX + 30 + legende * 32 + 40 + _RAND)
    bild = Image.new('RGB', (_BREITE, hoehe), FARBEN['weiss'])
    draw = ImageDraw.Draw(bild)
    rechts = _BREITE - _RAND

    draw.text((_RAND, _RAND), TITEL, fill=FARBEN['text'], font=titel)
    draw.text((_RAND, _RAND + 50), f'Stand {_datum(stand)} · nur aktive Halter', fill=FARBEN['grau'], font=klein)
    draw.text((rechts, _RAND + 50), VEREIN, fill=FARBEN['grau'], font=klein, anchor='ra')
    y = _RAND + 100
    x = _RAND
    for name, breite in zip(SPALTEN, _SPALTEN_PX):
        if breite > 200:
            draw.text((x, y), name, fill=FARBEN['grau'], font=kopf)
        else:
            draw.text((x + breite / 2, y), name, fill=FARBEN['grau'], font=kopf, anchor='ma')
        x += breite
    y += 34
    draw.line((_RAND, y, rechts, y), fill=FARBEN['text'], width=3)
    y += 4
    if not zeilen:
        draw.text((_RAND, y + 10), 'Keine aktiven Hunde', fill=FARBEN['grau'], font=text)
        y += _ZEILE_PX
    for halter, hunde in gruppen:
        for nr, zeile in enumerate(hunde):
            draw.line((_RAND, y, rechts, y), fill=FARBEN['trenn' if nr == 0 else 'linie'], width=1)
            mitte = y + _ZEILE_PX / 2
            if nr == 0:
                draw.text((_RAND, mitte), halter, fill=FARBEN['text'], font=text, anchor='lm')
            draw.text((_RAND + _SPALTEN_PX[0], mitte), zeile['hund'], fill=FARBEN['text'], font=text, anchor='lm')
            x = _RAND + _SPALTEN_PX[0] + _SPALTEN_PX[1]
            werte = ampel(zeile)
            for schluessel, breite in zip(('impfung', 'haftpflicht', 'foto'), _SPALTEN_PX[2:]):
                _symbol_px(draw, x + breite / 2, mitte, werte[schluessel], schrift=kopf)
                x += breite
            y += _ZEILE_PX
    draw.line((_RAND, y, rechts, y), fill=FARBEN['linie'], width=1)

    y += 30
    draw.text((_RAND, y), 'Training: Impfung und Haftpflicht', fill=FARBEN['text'], font=fett)
    y += 32
    for zustand, beschreibung in LEGENDE_TRAINING:
        _symbol_px(draw, _RAND + 14, y + 14, zustand, r=11)
        draw.text((_RAND + 40, y + 14), beschreibung, fill=FARBEN['text'], font=klein, anchor='lm')
        y += 32
    draw.text((_RAND, y + 14), HINWEIS_IMPFUNG, fill=FARBEN['grau'], font=klein, anchor='lm')
    y += 32 * 2
    draw.text((_RAND, y), 'Fotoeinwilligung - kein Kriterium fürs Training', fill=FARBEN['text'], font=fett)
    y += 32
    for zustand, beschreibung in LEGENDE_FOTO:
        _symbol_px(draw, _RAND + 14, y + 14, zustand, r=11, schrift=kopf)
        draw.text((_RAND + 40, y + 14), beschreibung, fill=FARBEN['text'],
                  font=_schrift_px(18, True) if zustand == 'nein' else klein, anchor='lm')
        y += 32
    draw.text((_RAND, hoehe - _RAND), 'Erstellt mit dem Hundemanager', fill=FARBEN['grau'], font=klein, anchor='ls')

    puffer = io.BytesIO()
    bild.save(puffer, 'PNG')
    return puffer.getvalue()
