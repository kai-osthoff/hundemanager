# app.py - Hauptanwendung
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import io
import os
import secrets
import subprocess
import sys
import threading
import time
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlalchemy import func, inspect, text #NEU
import updater

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hundemanager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Datenbankmodelle
class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vorname = db.Column(db.String(100), nullable=False)
    nachname = db.Column(db.String(100), nullable=False)
    aktiv = db.Column(db.Boolean, default=True)  # 👈v4
    fotofreigabe = db.Column(db.Boolean, default=False)  # 👈 NEU v5
    hunde = db.relationship('Hund', backref='besitzer', lazy=True, cascade='all, delete-orphan')


    @property
    def vollstaendiger_name(self):
        return f"{self.vorname} {self.nachname}"

class Hund(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    geburtstag = db.Column(db.Date, nullable=True)
    gueltig_shp_dap_dhp = db.Column(db.Date, nullable=True)
    gueltig_l = db.Column(db.Date, nullable=True)
    gueltig_bbpi = db.Column(db.Date, nullable=True)
    gueltig_t = db.Column(db.Date, nullable=True)
    haftpflicht_gueltig = db.Column(db.Boolean, default=False)
    bemerkung = db.Column(db.Text, nullable=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)

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

# Jinja2 Filter registrieren
app.jinja_env.filters['format_datum'] = format_datum
app.jinja_env.globals['get_status'] = get_status

@app.route('/')
def index():
    
    show_all = request.args.get('all') == '1'

    query = Person.query

    if not show_all:
        query = query.filter_by(aktiv=True)

    personen = query.order_by(
        Person.aktiv.desc(),
        func.lower(Person.nachname),
        func.lower(Person.vorname)
    ).all()

    return render_template('index.html', personen=personen)

@app.route('/person/neu', methods=['GET', 'POST'])
def person_neu():
    if request.method == 'POST':
        vorname = request.form.get('vorname', '').strip()
        nachname = request.form.get('nachname', '').strip()
        fotofreigabe = request.form.get('fotofreigabe') == '1'
        
        if not vorname or not nachname:
            flash('Bitte Vor- und Nachname angeben.', 'error')
            return render_template('person_form.html', person=None)
        
        person = Person(vorname=vorname, nachname=nachname, fotofreigabe=fotofreigabe)
        db.session.add(person)
        db.session.commit()
        flash(f'Person "{person.vollstaendiger_name}" wurde angelegt.', 'success')
        return redirect(url_for('index'))
    
    return render_template('person_form.html', person=None)

@app.route('/person/<int:person_id>/bearbeiten', methods=['GET', 'POST'])
def person_bearbeiten(person_id):
    person = Person.query.get_or_404(person_id)
    
    if request.method == 'POST':
        vorname = request.form.get('vorname', '').strip()
        nachname = request.form.get('nachname', '').strip()

        if not vorname or not nachname:
            flash('Bitte Vor- und Nachname angeben.', 'error')
            return render_template('person_form.html', person=person)

        person.fotofreigabe = request.form.get('fotofreigabe') == '1'
        person.vorname = vorname
        person.nachname = nachname
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
    headers = ['Nachname', 'Vorname', 'Foto', 'Hundename', 'Geburtstag', 'SHP/DAP/DHP', 'L', 'BbPi', 'T', 'Haftpflicht', 'Bemerkung']
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
            
            haftpflicht_cell = ws.cell(row=row, column=10, value='Ja' if hund.haftpflicht_gueltig else 'Nein')
            haftpflicht_cell.border = thin_border
            haftpflicht_cell.alignment = Alignment(horizontal='center')
            if hund.haftpflicht_gueltig:
                haftpflicht_cell.fill = green_fill
            else:
                haftpflicht_cell.fill = red_fill
            
            ws.cell(row=row, column=11, value=hund.bemerkung or '').border = thin_border
            row += 1
    
    # Spaltenbreiten anpassen
    column_widths = [15, 15, 7, 20, 12, 15, 12, 12, 12, 12, 30]
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

    status = "aktiviert" if person.aktiv else "deaktiviert"
    flash(f'Person wurde {status}.', 'success')

    return redirect(url_for('index'))


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

NEUSTART_CODE = 3  # start.py startet die App bei diesem Exit-Code neu
# Beim Start festhalten - nach einem Update steht in VERSION schon die neue Nummer
LAUFENDE_VERSION = updater.aktuelle_version()


@app.context_processor
def update_kontext():
    return {
        'app_version': LAUFENDE_VERSION,
        'update_info': updater.update_status(),
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
    erfolg, meldung = updater.installiere_update(db.engine.url.database)
    if not erfolg:
        flash(meldung, 'error')
        return redirect(url_for('index'))

    threading.Thread(target=neustart, daemon=True).start()
    return render_template('update_fertig.html', meldung=meldung,
                           alte_version=LAUFENDE_VERSION)


@app.route('/api/version')
def api_version():
    return jsonify(version=LAUFENDE_VERSION)


def neustart():
    time.sleep(1.5)  # Antwortseite erst noch ausliefern
    if os.environ.get('HUNDEMANAGER_LAUNCHER'):
        os._exit(NEUSTART_CODE)  # start.py startet neu
    # Ohne start.py gestartet (z.B. "python app.py"): selbst neu starten
    env = dict(os.environ, HUNDEMANAGER_WARTEN='2')
    subprocess.Popen([sys.executable] + sys.argv, env=env)
    os._exit(0)


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
    db_pfad = db.engine.url.database
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
                updater.sichere_datenbank(db_pfad, 'vor-migration')
                gesichert = True
            sql = f'ALTER TABLE {tabelle.name} ADD COLUMN {spalte.name} {spalte.type.compile(db.engine.dialect)}'
            standard = _sql_standardwert(spalte)
            if standard is not None:
                sql += f' DEFAULT {standard}'
            with db.engine.begin() as verbindung:
                verbindung.execute(text(sql))
            print(f'Datenbank aktualisiert: Spalte {tabelle.name}.{spalte.name} ergänzt')

    db.create_all()


if __name__ == '__main__':
    time.sleep(float(os.environ.get('HUNDEMANAGER_WARTEN', 0)))
    with app.app_context():
        migriere_datenbank()
    updater.starte_hintergrund_pruefung()
    port = int(os.environ.get('HUNDEMANAGER_PORT', 5000))
    print(f'Hundemanager {LAUFENDE_VERSION} läuft auf http://127.0.0.1:{port}')
    # Nur auf diesem PC erreichbar, ohne Debugger
    app.run(host='127.0.0.1', port=port)