# app.py - Hauptanwendung
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import io
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import traceback
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlalchemy import func, inspect, text #NEU
import backup
import nachweise
import updater
import whatsapp

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
# Fester Pfad, damit App und Sicherung garantiert dieselbe Datei meinen
os.makedirs(backup.INSTANCE_DIR, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + backup.DB_PFAD
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = nachweise.MAX_GROESSE + 1024 * 1024

db = SQLAlchemy(app)

# Datenbankmodelle
class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vorname = db.Column(db.String(100), nullable=False)
    nachname = db.Column(db.String(100), nullable=False)
    aktiv = db.Column(db.Boolean, default=True)  # 👈v4
    fotofreigabe = db.Column(db.Boolean, default=False)  # 👈 NEU v5
    mobil = db.Column(db.String(30), nullable=True)   # für WhatsApp, so wie eingegeben
    email = db.Column(db.String(200), nullable=True)
    hunde = db.relationship('Hund', backref='besitzer', lazy=True, cascade='all, delete-orphan')


    @property
    def vollstaendiger_name(self):
        return f"{self.vorname} {self.nachname}"

    @property
    def whatsapp_link(self):
        """Leerer Chat in WhatsApp Web - None ohne gültige Handynummer."""
        return whatsapp.link(self.mobil)

class Hund(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    geburtstag = db.Column(db.Date, nullable=True)
    gueltig_shp_dap_dhp = db.Column(db.Date, nullable=True)
    gueltig_l = db.Column(db.Date, nullable=True)
    gueltig_bbpi = db.Column(db.Date, nullable=True)
    gueltig_t = db.Column(db.Date, nullable=True)
    haftpflicht_gueltig = db.Column(db.Boolean, default=False)  # alte Ja/Nein-Angabe ohne Nachweis
    bemerkung = db.Column(db.Text, nullable=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    nachweise = db.relationship('Nachweis', backref='hund', lazy=True,
                                cascade='all, delete-orphan',
                                order_by='Nachweis.hochgeladen_am.desc()')

    def nachweise_der_art(self, art):
        """Nachweise einer Art, der am längsten gültige zuerst (ohne Datum zuletzt)."""
        return sorted((n for n in self.nachweise if n.art == art),
                      key=lambda n: (n.gueltig_bis is not None, n.gueltig_bis or date.min, n.hochgeladen_am),
                      reverse=True)

    @property
    def aktueller_nachweis(self):
        """Der Haftpflicht-Nachweis mit der längsten Gültigkeit - ältere bleiben als Historie erhalten."""
        haftpflicht = self.nachweise_der_art('haftpflicht')
        return haftpflicht[0] if haftpflicht else None


# Alle Nachweise liegen in EINER Ablage - die Art bestimmt Felder und Ablauf.
# Neue Arten (z.B. Wesenstest) hier ergänzen; die Datei-Ablage und Sicherung bleiben gleich.
NACHWEIS_ARTEN = {
    'haftpflicht': {
        'name': 'Haftpflicht',
        'aussteller': 'Versicherer',
        'nummer': 'Vertragsnummer',
        'gueltig_pflicht': True,     # ohne Gültigkeit kein Haftpflicht-Nachweis
        'tierdaten': True,           # Tier und Chip laut Dokument
        'impfungen': False,
    },
    'impfpass': {
        'name': 'Impfpass',
        'aussteller': 'Tierarzt / Praxis',
        'nummer': None,
        'gueltig_pflicht': False,
        'tierdaten': False,
        'impfungen': True,           # welche Impfungen das Foto belegt
    },
}
# So lange vor Ablauf soll später an einen neuen Nachweis erinnert werden
ERINNERUNG_VORLAUF = relativedelta(weeks=6)


class Nachweis(db.Model):
    """Ein eingereichtes Dokument. Die Datei selbst liegt unveränderlich in instance/nachweise/."""
    id = db.Column(db.Integer, primary_key=True)
    hund_id = db.Column(db.Integer, db.ForeignKey('hund.id'), nullable=False)
    art = db.Column(db.String(20), nullable=False, default='haftpflicht')
    datei_sha256 = db.Column(db.String(64), nullable=False)
    datei_endung = db.Column(db.String(4), nullable=False)
    original_name = db.Column(db.String(255), nullable=True)
    hochgeladen_am = db.Column(db.DateTime, nullable=False, default=datetime.now)
    eingereicht_von = db.Column(db.String(200), nullable=True)   # Halter beim Hochladen
    aussteller = db.Column(db.String(200), nullable=True)        # Quelle: Versicherer, Tierarzt ...
    nummer = db.Column(db.String(100), nullable=True)            # Vertrags-/Dokumentnummer
    ausgestellt_am = db.Column(db.Date, nullable=True)
    gueltig_bis = db.Column(db.Date, nullable=True)
    tier_laut_nachweis = db.Column(db.String(100), nullable=True)
    chipnummer = db.Column(db.String(30), nullable=True)
    impfungen = db.Column(db.String(100), nullable=True)         # z.B. "SHP/DAP/DHP, L"
    bemerkung = db.Column(db.Text, nullable=True)

    @property
    def art_name(self):
        return NACHWEIS_ARTEN.get(self.art, {}).get('name', self.art)

    @property
    def status(self):
        return get_status(self.gueltig_bis)

    @property
    def erinnern_ab(self):
        return self.gueltig_bis - ERINNERUNG_VORLAUF if self.gueltig_bis else None


def get_status(datum):
    """Prüft den Status eines Gültigkeitsdatums"""
    if datum is None:
        return 'keine-angabe'
    
    heute = date.today()
    ein_monat_spaeter = heute + relativedelta(months=1)
    
    if datum < heute:
        return 'abgelaufen'  # rot
    elif datum <= ein_monat_spaeter:
        return 'bald-ablaufend'  # orange
    else:
        return 'gueltig'  # grün

def format_datum(datum):
    """Formatiert ein Datum für die Anzeige"""
    if datum is None:
        return '-'
    return datum.strftime('%d.%m.%Y')

def iso_datum(wert):
    """Für <input type="date">: date-Objekt oder bereits 'JJJJ-MM-TT'."""
    if isinstance(wert, date):
        return wert.isoformat()
    return wert or ''

# Jinja2 Filter registrieren
app.jinja_env.filters['format_datum'] = format_datum
app.jinja_env.filters['iso_datum'] = iso_datum
app.jinja_env.globals['get_status'] = get_status

IMPFUNGEN = [
    ('SHP/DAP/DHP', 'gueltig_shp_dap_dhp'),
    ('L', 'gueltig_l'),
    ('BbPi', 'gueltig_bbpi'),
    ('T', 'gueltig_t'),
]
GESAMT_TEXT = {
    'ok': 'Alles gültig',
    'bald': 'Bald fällig',
    'abgelaufen': 'Abgelaufen',
    'unvollstaendig': 'Unvollständig',
}


def hund_ansicht(hund):
    """Alles, was eine Hundekarte braucht - inklusive Gesamtstatus für Farbe und Filter."""
    heute = date.today()
    impfungen = []
    for name, feld in IMPFUNGEN:
        datum = getattr(hund, feld)
        status = get_status(datum)
        hinweis = ''
        if status == 'abgelaufen':
            hinweis = 'abgelaufen'
        elif status == 'bald-ablaufend':
            tage = (datum - heute).days
            hinweis = 'heute' if tage == 0 else ('morgen' if tage == 1 else f'in {tage} Tagen')
        impfungen.append({'name': name, 'datum': datum, 'status': status, 'hinweis': hinweis})

    nachweis = hund.aktueller_nachweis
    if nachweis:
        haftpflicht = get_status(nachweis.gueltig_bis)
    elif hund.haftpflicht_gueltig:
        haftpflicht = 'ohne-nachweis'
    else:
        haftpflicht = 'keine-angabe'

    nachfragen = fehlende_angaben(hund, impfungen, haftpflicht, nachweis)
    whatsapp_nachfrage = None
    if nachfragen:
        whatsapp_nachfrage = whatsapp.link(hund.besitzer.mobil, whatsapp.fehlende_daten_nachricht(
            hund.besitzer.vorname, hund.name, nachfragen))

    stati = [i['status'] for i in impfungen] + [haftpflicht]
    if 'abgelaufen' in stati:
        gesamt = 'abgelaufen'
    elif 'bald-ablaufend' in stati:
        gesamt = 'bald'
    elif 'keine-angabe' in stati or 'ohne-nachweis' in stati:
        gesamt = 'unvollstaendig'
    else:
        gesamt = 'ok'

    return {
        'hund': hund,
        'impfungen': impfungen,
        'nachweis': nachweis,
        'haftpflicht': haftpflicht,
        'gesamt': gesamt,
        'gesamt_text': GESAMT_TEXT[gesamt],
        'nachfragen': nachfragen,
        'whatsapp_nachfrage': whatsapp_nachfrage,
    }


def fehlende_angaben(hund, impfungen, haftpflicht, nachweis):
    """Was beim Halter nachzufragen ist - je Punkt eine kurze Zeile für die Nachricht."""
    punkte = []
    for i in impfungen:
        if i['status'] == 'keine-angabe':
            punkte.append(f'Impfung {i["name"]}: Datum fehlt noch')
        elif i['status'] == 'abgelaufen':
            punkte.append(f'Impfung {i["name"]}: abgelaufen am {format_datum(i["datum"])}')
        elif i['status'] == 'bald-ablaufend':
            punkte.append(f'Impfung {i["name"]}: läuft am {format_datum(i["datum"])} ab')
    if haftpflicht in ('keine-angabe', 'ohne-nachweis'):
        punkte.append('Haftpflicht: Versicherungsnachweis fehlt noch')
    elif haftpflicht == 'abgelaufen':
        punkte.append(f'Haftpflicht: Nachweis abgelaufen am {format_datum(nachweis.gueltig_bis)}')
    elif haftpflicht == 'bald-ablaufend':
        punkte.append(f'Haftpflicht: Nachweis läuft am {format_datum(nachweis.gueltig_bis)} ab')
    if not hund.geburtstag:
        punkte.append('Geburtstag')
    return punkte


@app.route('/')
def index():
    ansicht = request.args.get('ansicht', 'aktiv')
    if request.args.get('all') == '1':  # alte Links aus v5.1.1 und früher
        ansicht = 'alle'
    if ansicht not in ('aktiv', 'handlungsbedarf', 'alle'):
        ansicht = 'aktiv'

    alle_personen = Person.query.order_by(
        Person.aktiv.desc(),
        func.lower(Person.nachname),
        func.lower(Person.vorname)
    ).all()
    aktive = [p for p in alle_personen if p.aktiv]
    pausierte = [p for p in alle_personen if not p.aktiv]

    gruppen = []
    for person in (alle_personen if ansicht == 'alle' else aktive):
        hunde = [hund_ansicht(h) for h in sorted(person.hunde, key=lambda h: h.name.lower())]
        if ansicht == 'handlungsbedarf':
            hunde = [h for h in hunde if h['gesamt'] != 'ok']
            if not hunde:
                continue
        gruppen.append({'person': person, 'hunde': hunde})

    # Kennzahlen immer über die aktiven Halter
    aktive_hunde = [hund_ansicht(h) for p in aktive for h in p.hunde]
    impf_stati = [i['status'] for h in aktive_hunde for i in h['impfungen']]
    kennzahlen = {
        'hunde': len(aktive_hunde),
        'bald': impf_stati.count('bald-ablaufend'),
        'abgelaufen': impf_stati.count('abgelaufen'),
        'ohne_haftpflicht': sum(1 for h in aktive_hunde if h['haftpflicht'] not in ('gueltig', 'bald-ablaufend')),
        'handlungsbedarf': sum(1 for h in aktive_hunde if h['gesamt'] != 'ok'),
    }

    return render_template('index.html', gruppen=gruppen, ansicht=ansicht,
                           pausierte=pausierte if ansicht != 'alle' else [],
                           anzahl_pausiert=len(pausierte), kennzahlen=kennzahlen,
                           gibt_personen=bool(alle_personen))

def _person_angaben(person):
    """Übernimmt die Formularfelder. Gibt eine Fehlermeldung zurück oder None."""
    vorname = request.form.get('vorname', '').strip()
    nachname = request.form.get('nachname', '').strip()
    mobil = request.form.get('mobil', '').strip()[:30]
    email = request.form.get('email', '').strip()[:200]
    if not vorname or not nachname:
        return 'Bitte Vor- und Nachname angeben.'
    if mobil and not whatsapp.nummer(mobil):
        return 'Die Handynummer stimmt so nicht – bitte z. B. als 0171 1234567 oder +49 171 1234567 eingeben.'
    if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        return 'Die E-Mail-Adresse stimmt so nicht – bitte prüfen.'
    person.vorname = vorname
    person.nachname = nachname
    person.fotofreigabe = request.form.get('fotofreigabe') == '1'
    person.mobil = mobil or None
    person.email = email or None
    return None


@app.route('/person/neu', methods=['GET', 'POST'])
def person_neu():
    if request.method == 'POST':
        person = Person()
        fehler = _person_angaben(person)
        if fehler:
            flash(fehler, 'error')
            return render_template('person_form.html', person=None, werte=request.form)

        db.session.add(person)
        db.session.commit()
        flash(f'Person "{person.vollstaendiger_name}" wurde angelegt.', 'success')
        return redirect(url_for('index'))
    
    return render_template('person_form.html', person=None)

@app.route('/person/<int:person_id>/bearbeiten', methods=['GET', 'POST'])
def person_bearbeiten(person_id):
    person = Person.query.get_or_404(person_id)
    
    if request.method == 'POST':
        fehler = _person_angaben(person)
        if fehler:
            flash(fehler, 'error')
            return render_template('person_form.html', person=person, werte=request.form)

        db.session.commit()
        flash(f'Person wurde aktualisiert.', 'success')
        return redirect(url_for('index'))
    
    return render_template('person_form.html', person=person)

@app.route('/person/<int:person_id>/loeschen', methods=['POST'])
def person_loeschen(person_id):
    person = Person.query.get_or_404(person_id)
    name = person.vollstaendiger_name
    db.session.delete(person)
    db.session.commit()
    flash(f'Person "{name}" und alle zugehörigen Hunde wurden gelöscht.', 'success')
    return redirect(url_for('index'))

@app.route('/person/<int:person_id>/hund/neu', methods=['GET', 'POST'])
def hund_neu(person_id):
    person = Person.query.get_or_404(person_id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        
        if not name:
            flash('Bitte mindestens den Namen des Hundes angeben.', 'error')
            return render_template('hund_form.html', person=person, hund=None)
        
        hund = Hund(
            name=name,
            geburtstag=parse_datum(request.form.get('geburtstag')),
            gueltig_shp_dap_dhp=parse_datum(request.form.get('gueltig_shp_dap_dhp')),
            gueltig_l=parse_datum(request.form.get('gueltig_l')),
            gueltig_bbpi=parse_datum(request.form.get('gueltig_bbpi')),
            gueltig_t=parse_datum(request.form.get('gueltig_t')),
            haftpflicht_gueltig=request.form.get('haftpflicht_gueltig') == 'ja',
            bemerkung=request.form.get('bemerkung', '').strip() or None,
            person_id=person.id
        )
        db.session.add(hund)
        db.session.commit()
        flash(f'Hund "{hund.name}" wurde angelegt.', 'success')
        return redirect(url_for('index'))
    
    return render_template('hund_form.html', person=person, hund=None)

@app.route('/hund/<int:hund_id>/bearbeiten', methods=['GET', 'POST'])
def hund_bearbeiten(hund_id):
    hund = Hund.query.get_or_404(hund_id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        
        if not name:
            flash('Bitte mindestens den Namen des Hundes angeben.', 'error')
            return render_template('hund_form.html', person=hund.besitzer, hund=hund)
        
        hund.name = name
        hund.geburtstag = parse_datum(request.form.get('geburtstag'))
        hund.gueltig_shp_dap_dhp = parse_datum(request.form.get('gueltig_shp_dap_dhp'))
        hund.gueltig_l = parse_datum(request.form.get('gueltig_l'))
        hund.gueltig_bbpi = parse_datum(request.form.get('gueltig_bbpi'))
        hund.gueltig_t = parse_datum(request.form.get('gueltig_t'))
        hund.haftpflicht_gueltig = request.form.get('haftpflicht_gueltig') == 'ja'
        hund.bemerkung = request.form.get('bemerkung', '').strip() or None
        
        db.session.commit()
        flash(f'Hund "{hund.name}" wurde aktualisiert.', 'success')
        return redirect(url_for('index'))
    
    return render_template('hund_form.html', person=hund.besitzer, hund=hund)

@app.route('/hund/<int:hund_id>/loeschen', methods=['POST'])
def hund_loeschen(hund_id):
    hund = Hund.query.get_or_404(hund_id)
    name = hund.name
    db.session.delete(hund)
    db.session.commit()
    flash(f'Hund "{name}" wurde gelöscht.', 'success')
    return redirect(url_for('index'))

# --- Nachweise (Haftpflicht, Impfpass, ...) ---

@app.errorhandler(413)
def datei_zu_gross(_fehler):
    flash('Die Datei ist zu groß (maximal 25 MB).', 'error')
    return redirect(request.referrer or url_for('index'))


@app.route('/hund/<int:hund_id>/haftpflicht')
def haftpflicht(hund_id):
    """Alte Adresse aus 5.1.1/5.1.2 - führt zur Nachweis-Seite des Hundes."""
    return redirect(url_for('hund_nachweise', hund_id=hund_id))


@app.route('/hund/<int:hund_id>/nachweise')
def hund_nachweise(hund_id):
    hund = Hund.query.get_or_404(hund_id)
    art = request.args.get('art', 'haftpflicht')
    return render_template('hund_nachweise.html', hund=hund, arten=NACHWEIS_ARTEN,
                           gewaehlte_art=art if art in NACHWEIS_ARTEN else 'haftpflicht')


@app.route('/hund/<int:hund_id>/nachweise/hochladen', methods=['POST'])
@app.route('/hund/<int:hund_id>/haftpflicht/hochladen', methods=['POST'])
def nachweis_hochladen(hund_id):
    hund = Hund.query.get_or_404(hund_id)
    art = request.form.get('art', 'haftpflicht')
    if art not in NACHWEIS_ARTEN:
        art = 'haftpflicht'
    datei = request.files.get('datei')
    if not datei or not datei.filename:
        flash('Bitte eine Datei auswählen.', 'error')
        return redirect(url_for('hund_nachweise', hund_id=hund.id, art=art))

    daten = datei.read()
    try:
        sha256, endung = nachweise.speichern(daten)
    except nachweise.NachweisFehler as e:
        flash(str(e), 'error')
        return redirect(url_for('hund_nachweise', hund_id=hund.id, art=art))

    vorschlag = {'eingereicht_von': hund.besitzer.vollstaendiger_name}
    warnungen = []
    erkannt = False
    if art == 'haftpflicht' and endung == 'pdf':
        erkannt_daten = nachweise.angaben_vorschlagen(nachweise.pdf_text(daten))
        erkannt = bool(erkannt_daten)
        vorschlag.update(erkannt_daten)
        tier = vorschlag.get('tier')
        if tier and hund.name.casefold() not in tier.casefold():
            warnungen.append(f'Im Nachweis steht das Tier „{tier}“ – passt das zu {hund.name}?')
    gueltig_bis = vorschlag.get('gueltig_bis')
    if gueltig_bis and gueltig_bis < date.today():
        warnungen.append('Laut Dokument ist dieser Nachweis bereits abgelaufen.')

    return render_template('nachweis_angaben.html', hund=hund, nachweis=None, art=art,
                           art_info=NACHWEIS_ARTEN[art], impfungen_auswahl=[n for n, _ in IMPFUNGEN],
                           vorschlag=vorschlag, warnungen=warnungen, sha256=sha256, endung=endung,
                           original_name=os.path.basename(datei.filename)[:255], text_erkannt=erkannt)


def _nachweis_angaben(nachweis):
    """Übernimmt die Formularfelder. Gibt eine Fehlermeldung zurück oder None."""
    art_info = NACHWEIS_ARTEN[nachweis.art]
    gueltig_bis = parse_datum(request.form.get('gueltig_bis'))
    if art_info['gueltig_pflicht'] and not gueltig_bis:
        return 'Bitte angeben, bis wann der Nachweis gültig ist.'
    nachweis.gueltig_bis = gueltig_bis
    nachweis.ausgestellt_am = parse_datum(request.form.get('ausgestellt_am'))
    nachweis.eingereicht_von = request.form.get('eingereicht_von', '').strip()[:200] or None
    nachweis.aussteller = request.form.get('aussteller', '').strip()[:200] or None
    nachweis.nummer = request.form.get('nummer', '').strip()[:100] or None
    nachweis.tier_laut_nachweis = request.form.get('tier_laut_nachweis', '').strip()[:100] or None
    nachweis.chipnummer = request.form.get('chipnummer', '').strip()[:30] or None
    gueltige = [n for n, _ in IMPFUNGEN]
    nachweis.impfungen = ', '.join(i for i in request.form.getlist('impfungen') if i in gueltige) or None
    nachweis.bemerkung = request.form.get('bemerkung', '').strip() or None
    return None


@app.route('/hund/<int:hund_id>/nachweise/speichern', methods=['POST'])
@app.route('/hund/<int:hund_id>/haftpflicht/speichern', methods=['POST'])
def nachweis_speichern(hund_id):
    hund = Hund.query.get_or_404(hund_id)
    art = request.form.get('art', 'haftpflicht')
    if art not in NACHWEIS_ARTEN:
        art = 'haftpflicht'
    sha256 = request.form.get('sha256', '')
    endung = request.form.get('endung', '')
    try:
        if not os.path.exists(nachweise.pfad(sha256, endung)):
            raise nachweise.NachweisFehler('Die hochgeladene Datei wurde nicht gefunden.')
    except nachweise.NachweisFehler as e:
        flash(f'{e} Bitte erneut hochladen.', 'error')
        return redirect(url_for('hund_nachweise', hund_id=hund.id, art=art))

    nachweis = Nachweis(hund_id=hund.id, art=art, datei_sha256=sha256, datei_endung=endung,
                        original_name=request.form.get('original_name', '')[:255] or None)
    fehler = _nachweis_angaben(nachweis)
    if fehler:
        flash(fehler, 'error')
        vorschlag = request.form.to_dict()
        vorschlag['impfungen_liste'] = request.form.getlist('impfungen')
        return render_template('nachweis_angaben.html', hund=hund, nachweis=None, art=art,
                               art_info=NACHWEIS_ARTEN[art], impfungen_auswahl=[n for n, _ in IMPFUNGEN],
                               vorschlag=vorschlag, warnungen=[], sha256=sha256, endung=endung,
                               original_name=nachweis.original_name, text_erkannt=False)
    db.session.add(nachweis)
    db.session.commit()
    gueltig = f' (gültig bis {format_datum(nachweis.gueltig_bis)})' if nachweis.gueltig_bis else ''
    flash(f'{nachweis.art_name}-Nachweis für {hund.name} gespeichert{gueltig}.', 'success')
    return redirect(url_for('hund_nachweise', hund_id=hund.id, art=art))


@app.route('/nachweis/<int:nachweis_id>/bearbeiten', methods=['GET', 'POST'])
def nachweis_bearbeiten(nachweis_id):
    """Angaben korrigieren - die Datei selbst bleibt unverändert."""
    nachweis = Nachweis.query.get_or_404(nachweis_id)
    if request.method == 'POST':
        fehler = _nachweis_angaben(nachweis)
        if fehler:
            flash(fehler, 'error')
        else:
            db.session.commit()
            flash('Angaben zum Nachweis aktualisiert.', 'success')
            return redirect(url_for('hund_nachweise', hund_id=nachweis.hund_id, art=nachweis.art))
    vorschlag = {
        'gueltig_bis': nachweis.gueltig_bis, 'ausgestellt_am': nachweis.ausgestellt_am,
        'eingereicht_von': nachweis.eingereicht_von, 'aussteller': nachweis.aussteller,
        'nummer': nachweis.nummer, 'tier': nachweis.tier_laut_nachweis,
        'chipnummer': nachweis.chipnummer, 'bemerkung': nachweis.bemerkung,
        'impfungen_liste': [i.strip() for i in (nachweis.impfungen or '').split(',') if i.strip()],
    }
    return render_template('nachweis_angaben.html', hund=nachweis.hund, nachweis=nachweis, art=nachweis.art,
                           art_info=NACHWEIS_ARTEN[nachweis.art], impfungen_auswahl=[n for n, _ in IMPFUNGEN],
                           vorschlag=vorschlag, warnungen=[], sha256=nachweis.datei_sha256,
                           endung=nachweis.datei_endung, original_name=nachweis.original_name,
                           text_erkannt=False)


@app.route('/nachweis/<int:nachweis_id>/datei')
def nachweis_datei(nachweis_id):
    nachweis = Nachweis.query.get_or_404(nachweis_id)
    return _sende_nachweis(nachweis.datei_sha256, nachweis.datei_endung, nachweis.original_name)


@app.route('/nachweis/vorschau/<sha256>.<endung>')
def nachweis_vorschau(sha256, endung):
    """Gerade hochgeladene Datei ansehen, bevor die Angaben gespeichert sind."""
    return _sende_nachweis(sha256, endung, None)


def _sende_nachweis(sha256, endung, original_name):
    try:
        datei_pfad = nachweise.pfad(sha256, endung)
    except nachweise.NachweisFehler:
        return 'Nicht gefunden', 404
    if not os.path.exists(datei_pfad):
        return 'Die Datei fehlt - bitte unter "Sicherungen" einen Stand wiederherstellen.', 404
    return send_file(datei_pfad, mimetype=nachweise.mimetype(endung),
                     download_name=original_name or f'nachweis.{endung}')


@app.route('/nachweise')
def nachweise_uebersicht():
    """Historie aller Nachweise - und welche bald erneuert werden müssen."""
    art = request.args.get('art', '')
    abfrage = Nachweis.query.join(Hund).join(Person)
    if art in NACHWEIS_ARTEN:
        abfrage = abfrage.filter(Nachweis.art == art)
    else:
        art = ''
    alle = abfrage.order_by(Nachweis.hochgeladen_am.desc()).all()

    # Bald fällig: nur der jeweils aktuelle Nachweis je Hund und Art zählt -
    # wer schon einen neueren eingereicht hat, muss nicht erinnert werden
    heute = date.today()
    aktuellste = {}
    for n in alle:
        if n.gueltig_bis and n.hund.besitzer.aktiv:
            schluessel = (n.hund_id, n.art)
            if schluessel not in aktuellste or n.gueltig_bis > aktuellste[schluessel].gueltig_bis:
                aktuellste[schluessel] = n
    erneuern = sorted((n for n in aktuellste.values() if n.erinnern_ab <= heute),
                      key=lambda n: n.gueltig_bis)

    return render_template('nachweise.html', nachweise=alle, erneuern=erneuern, art=art,
                           arten=NACHWEIS_ARTEN, heute=heute, vorlauf_wochen=6)


def parse_datum(datum_string):
    """Parst einen Datum-String in ein date-Objekt"""
    if not datum_string:
        return None
    try:
        return datetime.strptime(datum_string, '%Y-%m-%d').date()
    except ValueError:
        return None

@app.route('/export/excel')
def export_excel():
    """Exportiert alle Daten als Excel-Datei"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hundeübersicht"
    
    # Styles
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    orange_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    
    fill_rot = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    fill_gelb = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    fill_gruen = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Header
    headers = ['Nachname', 'Vorname', 'Foto', 'Hundename', 'Geburtstag', 'SHP/DAP/DHP', 'L', 'BbPi', 'T', 'Haftpflicht', 'Bemerkung', 'Handynummer', 'E-Mail']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border
    
    # Daten
    personen = Person.query.order_by(Person.nachname.asc(), Person.vorname.asc()).all()
    row = 2
    
    for person in personen:
        for hund in person.hunde:
            ws.cell(row=row, column=1, value=person.nachname).border = thin_border
            ws.cell(row=row, column=2, value=person.vorname).border = thin_border
            
            """ws.cell(row=row, column=3, value=person.fotofreigabe).border = thin_border"""
            foto_cell = ws.cell(row=row, column=3, value='Ja' if person.fotofreigabe else 'Nein')
            foto_cell.border = thin_border
            foto_cell.alignment = Alignment(horizontal='center')
            if person.fotofreigabe:
                foto_cell.fill = green_fill
            else:
                foto_cell.fill = red_fill
                
                
            status = impfstatus_farbe(hund)
            ws.cell(row=row, column=4, value=hund.name).border = thin_border
            if status == 'rot':
                ws.cell(row=row, column=4, value=hund.name).fill = fill_rot
            elif status == 'gelb':
                ws.cell(row=row, column=4, value=hund.name).fill = fill_gelb
            elif status == 'gruen':
                ws.cell(row=row, column=4, value=hund.name).fill = fill_gruen

            
            ws.cell(row=row, column=5, value=format_datum(hund.geburtstag)).border = thin_border
            
            # Gültigkeitsdaten mit Farbcodierung
            for col, datum in [(6, hund.gueltig_shp_dap_dhp), (7, hund.gueltig_l), 
                               (8, hund.gueltig_bbpi), (9, hund.gueltig_t)]:
                cell = ws.cell(row=row, column=col, value=format_datum(datum))
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center')
                status = get_status(datum)
                if status == 'gueltig':
                    cell.fill = green_fill
                elif status == 'bald-ablaufend':
                    cell.fill = orange_fill
                elif status == 'abgelaufen':
                    cell.fill = red_fill
            
            nachweis = hund.aktueller_nachweis
            if nachweis:
                # Mit Nachweis: Gültigkeitsdatum, gefärbt wie die Impfungen
                haftpflicht_cell = ws.cell(row=row, column=10, value=f'bis {format_datum(nachweis.gueltig_bis)}')
                haftpflicht_status = get_status(nachweis.gueltig_bis)
                haftpflicht_cell.fill = {'gueltig': green_fill, 'bald-ablaufend': orange_fill}.get(haftpflicht_status, red_fill)
            else:
                haftpflicht_cell = ws.cell(row=row, column=10,
                                           value='Ja (ohne Nachweis)' if hund.haftpflicht_gueltig else 'Nein')
                haftpflicht_cell.fill = orange_fill if hund.haftpflicht_gueltig else red_fill
            haftpflicht_cell.border = thin_border
            haftpflicht_cell.alignment = Alignment(horizontal='center')
            
            ws.cell(row=row, column=11, value=hund.bemerkung or '').border = thin_border
            ws.cell(row=row, column=12, value=person.mobil or '').border = thin_border
            ws.cell(row=row, column=13, value=person.email or '').border = thin_border
            row += 1
    
    # Spaltenbreiten anpassen
    column_widths = [15, 15, 7, 20, 12, 15, 12, 12, 12, 18, 30, 18, 28]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width
    
    # Als BytesIO speichern
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'hundeuebersicht_{date.today().strftime("%Y-%m-%d")}.xlsx'
    )



@app.route('/person/<int:person_id>/toggle_aktiv', methods=['POST'])
def person_toggle_aktiv(person_id):
    person = Person.query.get_or_404(person_id)
    person.aktiv = not person.aktiv
    db.session.commit()

    if person.aktiv:
        flash(f'{person.vollstaendiger_name} ist wieder aktiv.', 'success')
    else:
        flash(f'{person.vollstaendiger_name} ist pausiert – zu finden unten unter „Pausiert“.', 'success')

    return redirect(request.referrer or url_for('index'))


def impfstatus_farbe(hund):
    heute = date.today()
    plus_1_monat = heute + relativedelta(months=1)
    minus_1_monat = heute - relativedelta(months=1)

    impfungen = [
        hund.gueltig_shp_dap_dhp,
        hund.gueltig_l,
        hund.gueltig_bbpi,
        hund.gueltig_t
    ]

    # 🟥 ROT: fehlt oder >1 Monat abgelaufen
    for datum in impfungen:
        if datum is None:
            return 'rot'
        if datum < minus_1_monat:
            return 'rot'

    # 🟨 GELB: innerhalb ±1 Monat
    for datum in impfungen:
        if minus_1_monat <= datum <= plus_1_monat:
            return 'gelb'

    # 🟩 GRÜN: alles >1 Monat gültig
    return 'gruen'


# --- Updates ---

NEUSTART_CODE = 3        # start.py startet die App bei diesem Exit-Code neu
SELBSTTEST_FEHLER = 4    # start.py nimmt das Update dann zurück
# Beim Start festhalten - nach einem Update steht in VERSION schon die neue Nummer
LAUFENDE_VERSION = updater.aktuelle_version()
# Eindeutig je Prozess - daran erkennen Browser und Tests einen Neustart. Unter Windows
# ist der Server beim Neustart nicht erkennbar "weg": Verbindungsversuche warten dort
# ~2 Sekunden und landen dann nahtlos beim neuen Prozess.
INSTANZ = f'{os.getpid()}-{secrets.token_hex(4)}'
# Ab Protokoll 2 sichert start.py Updates ab (Rücknahme bei Fehlstart)
LAUNCHER_PROTOKOLL = int(os.environ.get('HUNDEMANAGER_LAUNCHER') or 0)

_hinweise = {'backup_fehler': None}


def lies_update_fehlgeschlagen():
    try:
        with open(backup.UPDATE_FEHLGESCHLAGEN, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


@app.context_processor
def update_kontext():
    return {
        'app_version': LAUFENDE_VERSION,
        'update_info': updater.update_status(),
        'update_fehlgeschlagen': lies_update_fehlgeschlagen(),
        'backup_fehler': _hinweise['backup_fehler'],
        # Alter Starter (v5.1.0) läuft noch - erst nach Neustart über START.bat ist die Absicherung aktiv
        'starter_veraltet': LAUNCHER_PROTOKOLL == 1,
    }


@app.route('/update/pruefen', methods=['POST'])
def update_pruefen():
    info = updater.pruefe_auf_update(erzwingen=True)
    if info.get('fehler'):
        flash(info['fehler'] + ' - bitte Internetverbindung prüfen.', 'error')
    elif info['verfuegbar']:
        flash(f'Version {info["version"]} ist verfügbar.', 'success')
    else:
        flash('Der Hundemanager ist auf dem neuesten Stand.', 'success')
    return redirect(url_for('index'))


@app.route('/update/installieren', methods=['POST'])
def update_installieren():
    # Vorher laden: nach dem Update liegen auf der Platte schon die neuen Templates,
    # dieser Prozess kennt aber nur die alten Routen
    fertig_seite = app.jinja_env.get_template('update_fertig.html')
    erfolg, meldung = updater.installiere_update()
    if not erfolg:
        flash(meldung, 'error')
        return redirect(url_for('index'))

    threading.Thread(target=neustart, daemon=True).start()
    return fertig_seite.render(meldung=meldung, alte_version=LAUFENDE_VERSION, alte_instanz=INSTANZ,
                               url_for=url_for)


@app.route('/update/hinweis-schliessen', methods=['POST'])
def update_hinweis_schliessen():
    if os.path.exists(backup.UPDATE_FEHLGESCHLAGEN):
        os.remove(backup.UPDATE_FEHLGESCHLAGEN)
    return redirect(url_for('index'))


@app.route('/api/version')
def api_version():
    return jsonify(version=LAUFENDE_VERSION, instanz=INSTANZ)


def neustart():
    time.sleep(1.5)  # Antwortseite erst noch ausliefern
    if LAUNCHER_PROTOKOLL:
        os._exit(NEUSTART_CODE)  # start.py startet neu
    # Ohne start.py gestartet (z.B. "python app.py"): selbst neu starten
    env = dict(os.environ, HUNDEMANAGER_WARTEN='2')
    subprocess.Popen([sys.executable] + sys.argv, env=env)
    os._exit(0)


# --- Sicherungen ---

def taeglich_sichern():
    """Einmal pro Tag eine Sicherung - schützt auch vor versehentlichem Löschen."""
    try:
        if backup.taegliches_backup_faellig():
            _, spiegel_fehler = backup.erstelle_backup('taeglich', LAUFENDE_VERSION)
            _hinweise['backup_fehler'] = spiegel_fehler
    except backup.BackupFehler as e:
        _hinweise['backup_fehler'] = f'Tägliche Sicherung fehlgeschlagen: {e}'
        print(_hinweise['backup_fehler'])


@app.route('/sicherungen')
def sicherungen():
    return render_template('sicherungen.html', backups=backup.liste_backups(),
                           backup_dir=backup.BACKUP_DIR, zweiter_ort=backup.zweiter_ort())


@app.route('/sicherungen/jetzt', methods=['POST'])
def sicherung_jetzt():
    try:
        _, spiegel_fehler = backup.erstelle_backup('manuell', LAUFENDE_VERSION)
        flash('Sicherung erstellt und geprüft.', 'success')
        if spiegel_fehler:
            flash(spiegel_fehler, 'error')
    except backup.BackupFehler as e:
        flash(f'Sicherung fehlgeschlagen: {e}', 'error')
    return redirect(url_for('sicherungen'))


@app.route('/sicherungen/wiederherstellen', methods=['POST'])
def sicherung_wiederherstellen():
    try:
        ordner = backup.finde_backup(request.form.get('name', ''))
        # Keine offenen Verbindungen der App, während die Datenbank zurückgespielt wird
        db.session.remove()
        db.engine.dispose()
        manifest = backup.datenbank_wiederherstellen(ordner, LAUFENDE_VERSION)
        migriere_datenbank()  # ältere Sicherung? Fehlende Spalten ergänzen
        flash(f'Daten vom {manifest["erstellt"][:16].replace("T", " ")} wiederhergestellt. '
              f'Der vorherige Stand wurde vorher gesichert.', 'success')
    except backup.BackupFehler as e:
        flash(f'Wiederherstellung nicht möglich: {e} Die Daten wurden nicht verändert.', 'error')
    return redirect(url_for('sicherungen'))


# --- Datenbank-Migration ---

def _sql_standardwert(spalte):
    if spalte.default is None or not spalte.default.is_scalar:
        return None
    wert = spalte.default.arg
    if isinstance(wert, bool):
        return '1' if wert else '0'
    if isinstance(wert, (int, float)):
        return str(wert)
    return "'" + str(wert).replace("'", "''") + "'"


def migriere_datenbank():
    """Ergänzt fehlende Tabellen/Spalten in einer bestehenden Datenbank.

    db.create_all() legt nur neue Tabellen an, aber keine neuen Spalten.
    Ohne diese Migration würde eine ältere Datenbank (z.B. aus v3/v4) nach
    einem Update mit "no such column" abstürzen.
    """
    inspektor = inspect(db.engine)
    vorhandene_tabellen = set(inspektor.get_table_names())
    gesichert = False

    for tabelle in db.metadata.sorted_tables:
        if tabelle.name not in vorhandene_tabellen:
            continue  # wird unten von create_all() angelegt
        vorhanden = {s['name'] for s in inspektor.get_columns(tabelle.name)}
        for spalte in tabelle.columns:
            if spalte.name in vorhanden:
                continue
            if not gesichert:
                # Ohne geprüfte Sicherung keine Änderung an der Datenbank
                backup.erstelle_backup('vor-migration', LAUFENDE_VERSION, mit_code=False)
                gesichert = True
            sql = f'ALTER TABLE {tabelle.name} ADD COLUMN {spalte.name} {spalte.type.compile(db.engine.dialect)}'
            standard = _sql_standardwert(spalte)
            if standard is not None:
                sql += f' DEFAULT {standard}'
            with db.engine.begin() as verbindung:
                verbindung.execute(text(sql))
            print(f'Datenbank aktualisiert: Spalte {tabelle.name}.{spalte.name} ergänzt')

    db.create_all()
    _haftpflicht_nachweise_uebernehmen(gesichert)


def _haftpflicht_nachweise_uebernehmen(schon_gesichert):
    """5.1.1/5.1.2 hatten eine eigene Tabelle haftpflicht_nachweis - in die gemeinsame
    Ablage 'nachweis' übernehmen. Die alte Tabelle bleibt zur Sicherheit unverändert stehen."""
    if 'haftpflicht_nachweis' not in inspect(db.engine).get_table_names():
        return
    with db.engine.connect() as v:
        alt = v.execute(text('SELECT COUNT(*) FROM haftpflicht_nachweis')).scalar()
        schon = v.execute(text("SELECT COUNT(*) FROM nachweis WHERE art = 'haftpflicht'")).scalar()
    if alt == 0 or schon > 0:
        return  # nichts zu tun oder bereits übernommen
    if not schon_gesichert:
        backup.erstelle_backup('vor-migration', LAUFENDE_VERSION, mit_code=False)
    with db.engine.begin() as v:  # alles oder nichts
        v.execute(text('''
            INSERT INTO nachweis (hund_id, art, datei_sha256, datei_endung, original_name,
                                  hochgeladen_am, eingereicht_von, aussteller, nummer,
                                  ausgestellt_am, gueltig_bis, tier_laut_nachweis, chipnummer)
            SELECT h.hund_id, 'haftpflicht', h.datei_sha256, h.datei_endung, h.original_name,
                   h.hochgeladen_am, p.vorname || ' ' || p.nachname, h.versicherer, h.vertragsnummer,
                   h.ausgestellt_am, h.gueltig_bis, h.tier_laut_nachweis, h.chipnummer
            FROM haftpflicht_nachweis h
            JOIN hund ON hund.id = h.hund_id
            JOIN person p ON p.id = hund.person_id
            ORDER BY h.id'''))
        neu = v.execute(text("SELECT COUNT(*) FROM nachweis WHERE art = 'haftpflicht'")).scalar()
        if neu != alt:
            raise RuntimeError(f'Übernahme der Haftpflicht-Nachweise unvollständig ({neu} von {alt})')
    print(f'Datenbank aktualisiert: {alt} Haftpflicht-Nachweis(e) in die Nachweis-Ablage übernommen')


def selbsttest():
    """Lädt die wichtigsten Seiten einmal intern - fällt etwas um, gilt das Update als fehlgeschlagen."""
    with app.test_client() as client:
        for pfad in ('/', '/?ansicht=handlungsbedarf', '/?ansicht=alle', '/nachweise', '/sicherungen', '/export/excel'):
            antwort = client.get(pfad)
            if antwort.status_code != 200:
                raise RuntimeError(f'Selbsttest: {pfad} liefert {antwort.status_code}')


def starten():
    nach_update = backup.lies_update_marker() is not None
    try:
        with app.app_context():
            migriere_datenbank()
            selbsttest()
    except Exception:
        traceback.print_exc()
        if not nach_update:
            raise
        if LAUNCHER_PROTOKOLL >= 2:
            sys.exit(SELBSTTEST_FEHLER)  # start.py nimmt das Update zurück
        # Alter Starter: selbst zurücknehmen und neu starten lassen
        backup.update_zuruecknehmen('Die neue Version hat den Selbsttest nicht bestanden.')
        neustart()

    if nach_update:
        backup.entferne_update_marker()
        print(f'Update auf {LAUFENDE_VERSION} bestätigt.')

    taeglich_sichern()
    updater.starte_hintergrund_pruefung(taeglich_sichern)
    port = int(os.environ.get('HUNDEMANAGER_PORT', 5000))
    print(f'Hundemanager {LAUFENDE_VERSION} läuft auf http://127.0.0.1:{port}')
    # Nur auf diesem PC erreichbar, ohne Debugger
    app.run(host='127.0.0.1', port=port)


if __name__ == '__main__':
    time.sleep(float(os.environ.get('HUNDEMANAGER_WARTEN', 0)))
    starten()
