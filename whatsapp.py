# whatsapp.py - Nachrichten an Halter über WhatsApp "Click to Chat"
#
# Kein externer Dienst: Der Link öffnet WhatsApp Web im Browser, die Nachricht steht
# schon im Eingabefeld und Saskia schickt sie selbst ab (oder ändert sie vorher).
# Format laut https://faq.whatsapp.com/5913398998672934 : Nummer im internationalen
# Format nur mit Ziffern (ohne +, ohne führende Nullen), Text URL-codiert.

import re
import urllib.parse

# Direkt in die Web-Oberfläche (wa.me zeigt am PC erst eine Zwischenseite)
WEB_ADRESSE = 'https://web.whatsapp.com/send'
LANDESVORWAHL = '49'  # Nummern wie 0171 ... sind deutsche Handynummern
ABSENDER = 'Saskia'
# Wie der Halter antworten soll - dieselben Texte gehen auch per E-Mail raus
ANTWORT_WEG = {'whatsapp': 'hier per WhatsApp', 'email': 'als Antwort auf diese E-Mail'}

_ERLAUBT = re.compile(r'^\+?[0-9 ()/.\-]+$')


def nummer(eingabe):
    """Handynummer -> '491711234567' für WhatsApp, oder None, wenn sie so nicht stimmen kann.

    Akzeptiert die üblichen Schreibweisen: 0171 1234567, 0171/123 45 67, +49 171 1234567,
    0049 171 1234567, +49 (0) 171 1234567, +43 664 1234567.
    """
    # "+49 (0) 171 ..." - die (0) wird international nicht gewählt
    eingabe = (eingabe or '').replace('(0)', '').strip()
    if not eingabe or not _ERLAUBT.match(eingabe):
        return None
    ziffern = re.sub(r'\D', '', eingabe)
    if eingabe.startswith('+'):
        pass                                  # schon international
    elif ziffern.startswith('00'):
        ziffern = ziffern[2:]                 # 0049 ... -> 49 ...
    elif ziffern.startswith('0'):
        ziffern = LANDESVORWAHL + ziffern[1:]  # 0171 ... -> 49171 ...
    # Internationale Nummern haben höchstens 15 Ziffern und beginnen nie mit 0
    if ziffern.startswith('0') or not 8 <= len(ziffern) <= 15:
        return None
    return ziffern


def link(handynummer, text=''):
    """Link, der den Chat in WhatsApp Web öffnet - mit vorausgefülltem Text, falls angegeben."""
    ziffern = nummer(handynummer)
    if not ziffern:
        return None
    parameter = {'phone': ziffern}
    if text:
        parameter['text'] = text
    # quote statt quote_plus: Leerzeichen als %20, so wie WhatsApp es dokumentiert
    return WEB_ADRESSE + '?' + urllib.parse.urlencode(parameter, quote_via=urllib.parse.quote)


def fehlende_daten_nachricht(vorname, hundename, punkte, kanal='whatsapp'):
    """Freundliche Bitte um die fehlenden Angaben. punkte: Liste kurzer Zeilen."""
    zeilen = [f'Hallo {vorname},', '',
              f'für {hundename} fehlen mir noch ein paar Angaben:']
    zeilen += [f'• {p}' for p in punkte]
    zeilen += ['', f'Schick mir einfach ein Foto vom Impfpass bzw. den Nachweis {ANTWORT_WEG[kanal]}.',
               '', 'Danke und viele Grüße', ABSENDER]
    return '\n'.join(zeilen)


def impfpass_nachricht(vorname, hundename, punkte, kanal='whatsapp'):
    """Bitte um ein Foto der Impfpass-Seite, wenn Impfungen abgelaufen, bald fällig oder unbekannt sind."""
    zeilen = [f'Hallo {vorname},', '',
              f'bei {hundename} ist im Impfpass etwas abgelaufen, bald fällig oder mir noch nicht bekannt:']
    zeilen += [f'• {p}' for p in punkte]
    zeilen += ['', f'Bitte schick mir ein Foto der Impfpass-Seite mit der aktuellen Impfung {ANTWORT_WEG[kanal]} '
               '– bei einer Auffrischung gern, sobald sie gemacht ist.',
               '', 'Danke und viele Grüße', ABSENDER]
    return '\n'.join(zeilen)


def fotoeinwilligung_nachricht(vorname, hundenamen, formular_link, kanal='whatsapp'):
    """Bitte um die unterschriebene Einwilligung zu Fotoaufnahmen - mit Link zum Formular."""
    if len(hundenamen) > 1:
        mit = ' mit ' + ', '.join(hundenamen[:-1]) + ' und ' + hundenamen[-1]
    elif hundenamen:
        mit = ' mit ' + hundenamen[0]
    else:
        mit = ''
    zeilen = [f'Hallo {vorname},', '',
              f'damit wir im Verein Fotos und Videos von dir{mit} verwenden dürfen '
              '(z. B. für Website, Berichte oder Flyer), brauche ich noch deine unterschriebene '
              'Einwilligung zu Fotoaufnahmen.', '',
              'Hier ist das Formular zum Ausdrucken:', formular_link, '',
              f'Bitte ausfüllen, unterschreiben und mir ein Foto oder einen Scan {ANTWORT_WEG[kanal]} schicken.',
              '', 'Danke und viele Grüße', ABSENDER]
    return '\n'.join(zeilen)
