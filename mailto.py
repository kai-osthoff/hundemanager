# mailto.py - Nachrichten an Halter per E-Mail
#
# Kein externer Dienst: Der Link ist ein normaler mailto:-Link (RFC 6068). Mit der
# GMX-Erweiterung "MailCheck" (Einstellung "E-Mail Links in Webseiten mit MailCheck öffnen")
# öffnet er GMX im Browser mit Empfänger, Betreff und Text - ohne sie das Mailprogramm von Windows.
# Saskia schickt selbst ab. GMX selbst bietet keinen Verfassen-Link mit Parametern an.
# (Bewusst nicht email.py - das würde Pythons eingebautes email-Paket verdecken.)

import re
import urllib.parse

_ADRESSE = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')


def link(adresse, betreff='', text=''):
    """mailto:-Link mit Betreff und Text - None ohne gültige Adresse."""
    adresse = (adresse or '').strip()
    if not _ADRESSE.fullmatch(adresse):
        return None
    parameter = {}
    if betreff:
        parameter['subject'] = betreff
    if text:
        parameter['body'] = text.replace('\r\n', '\n').replace('\n', '\r\n')  # Zeilenumbruch laut RFC 6068
    ziel = 'mailto:' + urllib.parse.quote(adresse, safe='@')
    if parameter:
        # quote statt quote_plus: ein + würde sonst als Leerzeichen gelesen
        ziel += '?' + urllib.parse.urlencode(parameter, quote_via=urllib.parse.quote)
    return ziel
