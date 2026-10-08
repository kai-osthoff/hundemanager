# impfstoffe.py - welcher Impfstoff-Aufkleber im Impfpass gehört zu welcher Impfung?
#
# Im EU-Heimtierausweis klebt der Tierarzt je Impfung den Aufkleber des Impfstoffs ein
# (z. B. "Nobivac SHP", "Versican Plus L4"). Die App führt nur vier Impfungen
# (SHP/DAP/DHP, L, BbPi, T) - diese Tabelle übersetzt Aufkleber in diese Impfungen.
# Ein Kombi-Impfstoff deckt mehrere ab (Nobivac RL = Tollwut + Leptospirose).
#
# zuordnen() verträgt Schreibweisen der Texterkennung: fehlende Leerzeichen, ®, Groß/klein
# und kleine Vertipper im Markennamen ("Nobivoc SHP", "Nobivar® T", "VERSICAN PIUs").
#
# ACHTUNG: "verw. bis" / "Exp." auf dem Aufkleber ist das Verfallsdatum des Impfstoffs,
# NICHT die Gültigkeit der Impfung. Die steht daneben unter "Gültig bis / Valid until".
#
# Neue Impfstoffe einfach unten in IMPFSTOFFE ergänzen.

import difflib
import re

SHP, L, BBPI, T = 'gueltig_shp_dap_dhp', 'gueltig_l', 'gueltig_bbpi', 'gueltig_t'

IMPFUNG_INFO = {
    SHP: {'kurz': 'SHP/DAP/DHP', 'krankheiten': 'Staupe, Hepatitis, Parvovirose',
          'gilt': 'meist 1–3 Jahre'},
    L: {'kurz': 'L', 'krankheiten': 'Leptospirose', 'gilt': 'meist 1 Jahr'},
    BBPI: {'kurz': 'BbPi', 'krankheiten': 'Zwingerhusten (Bordetella, Parainfluenza)', 'gilt': 'meist 1 Jahr'},
    T: {'kurz': 'T', 'krankheiten': 'Tollwut', 'gilt': '1–3 Jahre, eigene Seite im Heimtierausweis'},
}

# (Marke, Zusatz, Impfungen) - Zusatz so, wie er nach der Marke auf dem Aufkleber steht
IMPFSTOFFE = [
    ('Nobivac', 'SHP', [SHP]),
    ('Nobivac', 'DHP', [SHP]),
    ('Nobivac', 'DHPPi', [SHP]),
    ('Nobivac', 'Puppy DP', [SHP]),
    ('Nobivac', 'L4', [L]),
    ('Nobivac', 'Lepto', [L]),
    ('Nobivac', 'BbPi', [BBPI]),
    ('Nobivac', 'KC', [BBPI]),
    ('Nobivac', 'RL', [T, L]),
    ('Nobivac', 'T', [T]),
    ('Versican Plus', 'DHPPi/L4R', [SHP, L, T]),
    ('Versican Plus', 'DHPPi/L4', [SHP, L]),
    ('Versican Plus', 'DHPPi', [SHP]),
    ('Versican Plus', 'L4R', [L, T]),
    ('Versican Plus', 'L4', [L]),
    ('Virbagen canis', 'SHAPPi/L', [SHP, L]),
    ('Virbagen canis', 'SHAPPi', [SHP]),
    ('Virbagen canis', 'L', [L]),
    ('Eurican', 'DAPPi-L4', [SHP, L]),
    ('Eurican', 'DAPPi', [SHP]),
    ('Eurican', 'L4', [L]),
    ('Canigen', 'DHPPi/L', [SHP, L]),
    ('Canigen', 'DHPPi', [SHP]),
    ('Canigen', 'L4', [L]),
    ('Canigen', 'R', [T]),
    ('Rabisin', '', [T]),
    ('Rabdomun', '', [T]),
    ('Versiguard', 'Rabies', [T]),
    ('Pneumodog', '', [BBPI]),
]

_MARKE_AEHNLICH = 0.8   # "Nobivoc"/"Nobivar" gelten noch als "Nobivac"


def _kompakt(text):
    return re.sub(r'[^a-z0-9]', '', (text or '').lower())


# Längster Zusatz zuerst: "DHPPi/L4R" muss vor "DHPPi" geprüft werden
_SUCHE = sorted(((_kompakt(m), _kompakt(z), m, z, f) for m, z, f in IMPFSTOFFE),
                key=lambda e: -len(e[1]))


def _passt(kompakt, marke, zusatz):
    for i in range(len(kompakt) - len(marke) + 1):
        stueck = kompakt[i:i + len(marke)]
        if stueck[0] != marke[0]:
            continue
        # Nur die Marke allein (z. B. "Rabisin") muss exakt stimmen - sonst wäre "Rabies" ein Treffer
        genug = 1.0 if not zusatz else _MARKE_AEHNLICH
        if difflib.SequenceMatcher(None, stueck, marke).ratio() >= genug \
                and kompakt[i + len(marke):].startswith(zusatz):
            return True
    return False


def zuordnen(text):
    """Text eines Aufklebers -> {'name': 'Nobivac SHP', 'felder': [...]} oder None."""
    kompakt = _kompakt(text)
    if not kompakt:
        return None
    for marke, zusatz, m, z, felder in _SUCHE:
        if _passt(kompakt, marke, zusatz):
            return {'name': f'{m} {z}'.strip(), 'felder': list(felder)}
    return None


def aufkleber_fuer(feld):
    """Namen aller bekannten Impfstoffe, die diese Impfung abdecken."""
    return [f'{m} {z}'.strip() for m, z, felder in IMPFSTOFFE if feld in felder]


def beschreibung(feld):
    """'L – Leptospirose'"""
    info = IMPFUNG_INFO[feld]
    return f"{info['kurz']} – {info['krankheiten']}"
