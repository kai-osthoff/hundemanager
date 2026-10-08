# bilder.py - Fotos von Nachweisen richtig herum anzeigen
#
# Die Originaldatei in instance/nachweise/ wird NIE verändert. Gedreht wird nur die
# Anzeige: Nachweis.drehung (0/90/180/270 Grad im Uhrzeigersinn) steht in der Datenbank.
#
# Halter schicken Fotos vom Impfpass oft quer oder auf dem Kopf (über WhatsApp gehen
# die EXIF-Angaben zur Ausrichtung verloren). ausrichtung_erkennen() schätzt die nötige
# Drehung am Bildinhalt - ohne Texterkennung, nur mit Pillow:
#   1. Textzeilen ergeben im Zeilenprofil (Tinte je Bildzeile) ein starkes Auf und Ab.
#      Liegt das Auf und Ab in den Spalten, ist das Bild quer.
#   2. Oben oder unten? In Druck- und Schreibschrift ragen Oberlängen (b, d, h, k, l,
#      Großbuchstaben) viel häufiger aus der Zeile als Unterlängen (g, p, y). Über dem
#      Mittelband jeder Zeile liegt deshalb mehr Tinte als darunter - auf dem Kopf umgekehrt.
# Das ist nur ein Vorschlag: Saskia kann im Dialog jederzeit selbst drehen.
#
# Fehlt Pillow (z.B. Installation noch nicht nachgezogen), läuft alles weiter -
# dann ohne automatische Drehung und mit dem Originalbild.

import io

try:
    from PIL import Image, ImageChops, ImageFilter, ImageOps
except ImportError:  # pragma: no cover - nur, wenn Pillow fehlt
    Image = None

DREHUNGEN = (0, 90, 180, 270)
ANALYSE_KANTE = 1600     # Analyse auf dieser Größe: kleine Schrift bleibt erkennbar
ANZEIGE_KANTE = 2400     # Anzeige im Browser - scharf genug zum Lesen, nicht 10 MB groß
_QUER_SICHER = 1.08      # so viel stärker muss das Zeilenmuster quer sein, um zu drehen
_KOPF_SICHER = 0.005     # so deutlich müssen die Unterlängen überwiegen, um umzudrehen

# Pillow gibt sonst bei riesigen Bildern eine Warnung bzw. einen Fehler aus
if Image is not None:
    Image.MAX_IMAGE_PIXELS = 120_000_000


def verfuegbar():
    return Image is not None


def drehung_pruefen(wert):
    """Formularwert -> 0/90/180/270 (alles andere wird 0)."""
    try:
        wert = int(wert) % 360
    except (TypeError, ValueError):
        return 0
    return wert if wert in DREHUNGEN else 0


def _oeffnen(daten):
    bild = Image.open(io.BytesIO(daten))
    bild.load()
    # Ausrichtung aus der Kamera (EXIF) gleich anwenden - die Drehung kommt obendrauf
    return ImageOps.exif_transpose(bild)


def _drehen(bild, drehung):
    # Pillow dreht gegen den Uhrzeigersinn
    return bild.rotate(-drehung, expand=True) if drehung else bild


def _tinte(bild):
    """Schwarz-Weiß-Bild: weiß, wo etwas dunkler ist als seine Umgebung (Schrift, Linien)."""
    grau = bild.convert('L')
    faktor = ANALYSE_KANTE / max(grau.size)
    grau = grau.resize((max(1, round(grau.width * faktor)), max(1, round(grau.height * faktor))),
                       Image.LANCZOS if faktor > 1 else Image.BOX)
    umgebung = grau.filter(ImageFilter.BoxBlur(12))
    return ImageChops.subtract(umgebung, grau).point(lambda v: 255 if v > 25 else 0)


def _profil(tinte):
    """Mittlere Tinte je Bildzeile."""
    zeilen = tinte.resize((1, tinte.height), Image.BOX)
    if hasattr(zeilen, 'get_flattened_data'):  # Pillow >= 12.1 (getdata ist veraltet)
        return list(zeilen.get_flattened_data())
    return list(zeilen.getdata())


def _zeilenmuster(tinte, streifen=4):
    """Wie deutlich sich Textzeilen und Lücken abwechseln (Streuung/Mittel des Zeilenprofils) -
    hoch bei waagrechten Zeilen. In senkrechten Streifen, nach Tinte gewichtet: über die ganze
    Breite gemittelt verwischen unterschiedlich lange Zeilen das Muster."""
    breite, hoehe = tinte.size
    summe = gewicht = 0.0
    for k in range(streifen):
        p = _profil(tinte.crop((k * breite // streifen, 0, (k + 1) * breite // streifen, hoehe)))
        mittel = sum(p) / len(p) if p else 0
        if mittel:
            streuung = (sum((v - mittel) ** 2 for v in p) / len(p)) ** 0.5
            summe += streuung  # = Streuung/Mittel, gewichtet mit dem Mittel
            gewicht += mittel
    return summe / gewicht if gewicht else 0.0


def _oberlaengen(tinte, streifen=8):
    """> 0, wenn die Textzeilen oben mehr herausragende Tinte haben als unten (aufrecht),
    < 0 auf dem Kopf. In senkrechten Streifen gerechnet, damit nebeneinanderstehende
    Spalten mit verschiedenen Zeilenabständen sich nicht vermischen."""
    breite, hoehe = tinte.size
    summe, anzahl = 0.0, 0
    for k in range(streifen):
        p = _profil(tinte.crop((k * breite // streifen, 0, (k + 1) * breite // streifen, hoehe)))
        mittel = sum(p) / len(p) if p else 0
        if not mittel:
            continue
        i = 0
        while i < len(p):
            if p[i] <= mittel:
                i += 1
                continue
            # Eine Zeile: zusammenhängender Bereich über dem Mittelwert, mit Ausläufern
            anfang = i
            while anfang > 0 and p[anfang - 1] > mittel * 0.3:
                anfang -= 1
            ende = i
            while ende < len(p) and p[ende] > mittel * 0.3:
                ende += 1
            zeile = p[anfang:ende]
            i = ende + 1
            if not 4 <= len(zeile) <= hoehe * 0.05:
                continue  # zu dünn für Schrift oder zu hoch (Fläche, Foto, Rand)
            # Kern = Mittelband der Buchstaben (x-Höhe); was darüber/darunter liegt, sind
            # Ober- bzw. Unterlängen
            spitze = max(zeile)
            kern = [x for x, v in enumerate(zeile) if v >= spitze * 0.5]
            oben = sum(zeile[:kern[0]])
            unten = sum(zeile[kern[-1] + 1:])
            summe += (oben - unten) / sum(zeile)
            anzahl += 1
    return summe / anzahl if anzahl else 0.0


def ausrichtung_erkennen(daten):
    """Vorschlag, um wie viel Grad (im Uhrzeigersinn) das Foto gedreht werden muss.
    0 bei PDFs, unlesbaren Bildern oder wenn nichts klar dafür spricht."""
    if Image is None:
        return 0
    try:
        tinte = _tinte(_oeffnen(daten))
    except Exception:
        return 0  # kein Bild (PDF) oder beschädigt - dann eben nicht drehen

    quer = _drehen(tinte, 90)
    if _zeilenmuster(quer) > _zeilenmuster(tinte) * _QUER_SICHER:
        # Quer: 90 oder 270 - eins von beiden stimmt, die Schiefe entscheidet
        return 90 if _oberlaengen(quer) >= 0 else 270
    # Steht schon aufrecht oder auf dem Kopf: nur bei deutlichem Befund umdrehen
    return 180 if _oberlaengen(tinte) < -_KOPF_SICHER else 0


def ausschnitt_pruefen(wert):
    """'0.1,0.2,0.5,0.3' (x, y, Breite, Höhe als Anteil des gedrehten Bildes) -> Tupel oder None."""
    try:
        x, y, b, h = (float(t) for t in (wert or '').split(','))
    except ValueError:
        return None
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < b <= 1 and 0 < h <= 1):
        return None
    return x, y, min(b, 1 - x), min(h, 1 - y)


def ansicht(daten, drehung=0, kante=ANZEIGE_KANTE, ausschnitt=None):
    """Foto gedreht und verkleinert als JPEG - (bytes, mimetype). None, wenn es kein Bild ist.
    ausschnitt: nur dieser Teil (siehe ausschnitt_pruefen), z. B. die Zeile, aus der ein Vorschlag stammt."""
    if Image is None:
        return None
    try:
        bild = _drehen(_oeffnen(daten), drehung_pruefen(drehung))
    except Exception:
        return None
    if bild.mode not in ('RGB', 'L'):
        # Transparenz (PNG) auf Weiß legen - JPEG kennt keine
        grund = Image.new('RGB', bild.size, 'white')
        grund.paste(bild.convert('RGBA'), mask=bild.convert('RGBA').getchannel('A'))
        bild = grund
    teil = ausschnitt_pruefen(ausschnitt) if isinstance(ausschnitt, str) else ausschnitt
    if teil:
        x, y, b, h = teil
        w0, h0 = bild.size
        bild = bild.crop((int(x * w0), int(y * h0), max(int(x * w0) + 1, int((x + b) * w0)),
                          max(int(y * h0) + 1, int((y + h) * h0))))
    bild.thumbnail((kante, kante), Image.LANCZOS)
    puffer = io.BytesIO()
    bild.save(puffer, 'JPEG', quality=88)
    return puffer.getvalue(), 'image/jpeg'
