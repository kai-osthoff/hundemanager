# Einstellbare Anforderungen: Welche Impfungen und Nachweise verlangt ein Verein?

Stand: 2026-10-10 · Recherche, keine Umsetzung

## Anlass

Saskia hat vorgeschlagen, die benötigten Impfungen einstellbar zu machen, „weil jeder Hundeverein da
andere Vorgaben haben kann“. Ihr Beispiel war die Rettungshundestaffel, die nur Tollwut und die
„5-fach-Impfung“ (SHP, Pi + L4) braucht. Offen war, wie andere Vereine das handhaben, ob es eine
einheitliche Vorgabe gibt und ob es Software gibt, die das schon kann.

Heute sind im Hundemanager die vier Impfungen `SHP/DAP/DHP`, `L`, `BbPi` und `T` fest eingebaut:
als vier Spalten am `Hund` (`gueltig_shp_dap_dhp` …), als Liste `IMPFUNGEN` in `app.py` und als
Zuordnung in `impfstoffe.py`. Alle vier zählen immer für den Gesamtstatus, für „Handlungsbedarf“ und
für die WhatsApp-Nachfrage. Gleiches gilt für Haftpflicht und Geburtstag.

## Kurzfassung

1. **Es gibt keine einheitliche Vorgabe.** In Deutschland ist keine Impfung gesetzlich vorgeschrieben.
   Die einzige Ausnahme ist Tollwut bei Reisen (VO (EU) 576/2013). Jeder Verein regelt das über sein
   Hausrecht selbst. Das VG Düsseldorf hat 2020 bestätigt, dass eine Hundeschule einen Impfnachweis
   verlangen darf.
2. **Die Vorgaben sind sehr unterschiedlich.** In 15 untersuchten Platzordnungen reicht die Spanne von
   „geimpft“ ohne Nennung einer Krankheit über „nur Tollwut“ (vier Vereine) bis zur vollen Liste
   SHPPi + L + T + Zwingerhusten.
3. **Haftpflicht ist fast überall Pflicht.** Das gilt in 11 von 12 Vereinen, aber keiner nennt eine
   Deckungssumme.
4. **Rettungshundestaffeln sind strenger und anders.** BRH, DRK, DLRG und IRO verlangen Tollwut,
   Staupe, Hepatitis, Parvovirose und Leptospirose. **Parainfluenza (Pi) und Zwingerhusten verlangt
   keine dieser Ordnungen.** Dazu kommen Nachweise, die der Hundemanager noch nicht kennt:
   Prüfungsgültigkeit, Erste-Hilfe-Kurs und Chipkontrolle.
5. **In Deutschland gibt es keine Software, die das kann.** Weder Hundeschul- noch Vereinssoftware
   bildet einstellbare Pflichtimpfungen nachweisbar ab. US-Software für Hundetagesstätten und
   Hundepensionen (Time To Pet, MoeGo, DaySmart Pet, Gingr) macht es dagegen alle nach demselben
   Muster: Der Betrieb pflegt eine **Liste der Impfarten**, und jede bekommt einen **Pflicht-Schalter**.
   Dieses Muster empfehle ich auch für uns.

**Empfehlung:** In einem ersten kleinen Schritt bekommt jede vorhandene Anforderung in den
Einstellungen drei Stufen: **Pflicht / Freiwillig / Ausblenden**. Das betrifft die vier Impfungen,
Haftpflicht, Geburtstag und die Fotoeinwilligung. Dazu kommen fertige **Vorlagen** wie „Rettungshundestaffel“
oder „Nur Tollwut“. Das geht ohne Änderung am Datenmodell, und für Saskia ändert sich nichts, solange
sie nichts umstellt. Eine eigene Liste von Impfarten, Gruppen wie Welpen oder Staffel und neue
Nachweisarten folgen erst, wenn ein zweiter Verein sie wirklich braucht.

---

## 1. Was Hundevereine verlangen

Die Angaben stammen aus Platzordnungen, Aufnahmeanträgen und Trainingsbedingungen. Den Wortlaut habe
ich bei 13 Beispielen selbst gelesen. Bei den mit \* markierten Beispielen stammen die Angaben nur aus
Suchtreffern.

| Verein / Schule | Impfungen | Nachweis | Haftpflicht |
|---|---|---|---|
| [HSV Wittgensdorf](https://www.hsv-wittgensdorf.de/trainingszeiten/platzordnung/) | keine Krankheit genannt | beim ersten Besuch, danach auf Verlangen | Pflicht |
| [HSV Giebelstadt](https://hundesportverein-giebelstadt.de/platzordnung/) | „Schutzimpfung“ | Kopie spätestens vor der 2. Einheit an den Vorstand | Pflicht (Kopie) |
| [Hundesport Ludwigsfelde](https://www.hundesport-ludwigsfelde.de/platzordnung) | Tollwut, Staupe, Parvo | nicht genannt | Pflicht |
| [GHV Hauptstuhl](https://www.hundesport-hauptstuhl.de/training-platzordnung) | nur Tollwut | auf Verlangen | Pflicht |
| [HSV Greifswald](https://www.hundesportverein-greifswald.de/platzordnung-satzung/) | „geimpft“ | nicht genannt | nur empfohlen |
| [HSV Osterburg](https://hsvosterburg.jimdofree.com/platzordnung/) | „ordnungsgemäß“, Welpen „altersentsprechend“ | gültiger Impfausweis, sonst keine Teilnahme | Pflicht |
| [HSV Ahrtal](https://www.hsv-ahrtal-ev.de/Ueber-uns/Platzordnung/) | „geimpft“ | nicht genannt | Pflicht |
| [HSV Möttlingen](https://www.hsvmoettlingen.de/verein/platzordnung) | nur Tollwut | vor der 1. Stunde, danach jederzeit Kontrolle | Pflicht |
| [VdH Friedrichshafen](https://www.vdh-friedrichshafen.de/platzordnung/) | nur Tollwut | „Nachweis“ | Pflicht |
| [PGHV Bliedersdorf/Harsefeld](https://www.hundeverein-bliedersdorf.de/87.html) | nur Tollwut | nicht genannt | Pflicht |
| [HSC Hürth-Rheinland](https://www.hsc-huerth-rheinland.de/verein) | keine Krankheit genannt | Impfpass „zwingend“ beim ersten Mal | Pflicht |
| [PSK Osnabrück](https://www.psk-osnabrueck.de/unser-verein/mitgliedschaft/) | keine Krankheit genannt | Impfpass **bei jedem Besuch** mitbringen | Pflicht |
| [PRO-DOG Hundeschule](https://www.hundeschule-pro-dog.de/hundeschule/trainingsinfos-platzordnung/) | SHPPi + L + T + Zwingerhusten | Impfpass mitbringen | Pflicht |
| [Hundeschule Stuttgart](https://hundeschule-stuttgart.de/welpenschule/faq-welpen-impfung/) | altersentsprechende Grundimmunisierung | Heimtierausweis beim 1. Training | – |
| [OG Sachsenwald (SV)](http://www.og-sachsenwald.de/%C3%BCber-uns/)\* | SHP + L, jährlich Tollwut | beim Zuchtwart/Vorstand | Pflicht |
| [HSV Schaidt](https://storage.e.jimdo.com/file/0d6c904b-6f2f-4b58-be6a-f5fdd5983fe1/Antrag%20Mitgliedschaft.pdf)\* | SHP + L + Pi | ohne Nachweis kein Training | Pflicht |

**Gemeinsam ist den Vereinen:**
- Haftpflicht ist Pflicht.
- Gesunde, geimpfte Hunde sind Voraussetzung fürs Gelände.
- Tollwut ist die Krankheit, die am häufigsten allein genannt wird.

**Unterschiedlich sind:**
- **Umfang der Impfungen:** Die Spanne reicht von „geimpft“ bis zur vollen Liste mit Zwingerhusten
  (siehe Kurzfassung).
- **Art des Nachweises:** Die Spanne reicht von „auf Verlangen“ bis „immer mitbringen“.
- **Welpen:** Welpen sind kaum geregelt. Wenn es Regeln gibt, dann als Ausnahme: Welpen dürfen ohne
  Zwingerhusten- und Tollwutimpfung teilnehmen.

**In keiner Platzordnung gefunden:** Chip, Hundesteuer, Wesenstest, Sachkunde, Hundeführerschein,
Deckungssumme der Haftpflicht. Eine jährliche Wiedervorlage verlangt ebenfalls kein Verein. Die
Wiedervorlage im Hundemanager geht also schon weiter als das, was Vereine verlangen.

**Prüfungen und Turniere:** Auf Meldescheinen des SV und von VDH/SV bestätigt der Teilnehmer per
Unterschrift Haftpflicht und eine **gültige Tollwutimpfung**. Das gilt für Rally Obedience, Agility
und Hüten. Je nach Meldeschein ist der Impfpass am Veranstaltungstag vorzulegen. Diese Angaben stammen
aus Suchtreffern, die PDFs selbst konnte ich nicht lesen. Ob die VDH-Prüfungsordnungen selbst eine
Impfklausel enthalten, ist **nicht belegt**.

## 2. Rettungshundestaffeln und Besuchshunde

| | BRH (PO 2025.03) | DRK (PO 2024) | DLRG (Anweisung 2014) | IRO (Impfregelung) |
|---|---|---|---|---|
| Impfungen | T + Staupe, HCC, Parvo, Lepto („ständiger Impfschutz“) | Staupe, T, Parvo, Lepto, Hepatitis | „Komplettimpfung“ | T, Staupe, Hepatitis, Parvo, Lepto; Lepto **jährlich**, sonst max. 3 Jahre |
| Nachweis | Impfpass vor der Prüfung, Chip wird abgeglichen | Impfpass/Heimtierausweis vor der Prüfung, Chipkontrolle | Unterlagen bei Prüfung | bei IRO-Veranstaltungen |
| Haftpflicht | Pflicht, **jährlich** nachweisen | Kapitel vorhanden, nicht gelesen | Pflicht | – |
| Hundeführer | Erste Hilfe (DGUV) bzw. Sanitätskurs ≤ 36 Monate | Sanitätsgrundausbildung, Erste Hilfe am Hund | Erste Hilfe Mensch + Hund ≤ 2 Jahre, SAN A | – |
| Prüfung gültig | meist bis 31.12. des Folgejahres | eigenes Kapitel, nicht gelesen | jährlich bzw. alle 2 Jahre | – |

Quellen: [BRH-PO](https://www.bundesverband-rettungshunde.de/de/brh.html?file=files/intern/download/Ordnungen,+Richtlinien,+Leitf%C3%A4den/BRH-Pr%C3%BCfungsordnung_2025+03.pdf&cid=5275),
[DRK-PO 2024](https://www.bildungsinstitut-rlp.drk.de/fileadmin/downloads/Bereitschaften/Fachdienst_Rettungshunde/DRK_PO_Rettungshunde_2024.pdf),
[DLRG](https://www.dlrg.de/fileadmin/user_upload/DLRG.de/Fuer-Mitglieder/Einsatz_und_Medizin/wrd_mobil/21401105_Anweisung_Rettungshundearbeit.pdf),
[IRO](https://www.iro-dogs.org/fileadmin/user_upload/IRO_Impfregelung.pdf).
Die örtliche [DRK-Staffel Ostvorpommern](https://www.rhs-ovp.de/haeufig-gestellte-fragen.html)
verlangt zusätzlich Zwingerhusten. Staffeln können also über ihren Verband hinausgehen.

**Besuchs- und Therapiehunde:** Hier gibt es keine einheitliche Ordnung. Das DRK Hessen verlangt eine
**jährliche tierärztliche Gesundheitsbescheinigung** (Impfungen, Entwurmung bzw. Kotprobe alle
3 Monate, Chipnummer). Dazu kommen je nach Träger Haftpflicht und Erste Hilfe
([DRK Hessen](https://www.drk-hessen.de/fileadmin/Eigene_Dokumente/Gesundheit_und_Soziales/THT-Richtlinien/2023_Gesundheitszeugnis.pdf),
[DRK Dillkreis](https://www.drk-dillenburg.de/fileadmin/user_upload/Seiten/Therapiehunde/Ausbildung_zum_Therapiehunde.pdf)).

**Für die App heißt das:** Die Staffel aus Saskias Beispiel braucht laut Ordnungen
**SHP + L + T**, aber **kein BbPi**. Die Einstellung „BbPi: Ausblenden“ deckt diesen Fall also schon
ab. Prüfung, Erste Hilfe und Gesundheitszeugnis wären später neue Einträge in `NACHWEIS_ARTEN`.

## 3. Fachlicher Hintergrund

- **StIKo Vet** (Leitlinie, 6. Aufl. 2025; den Volltext konnte ich nicht abrufen, die Angaben stammen
  aus Sekundärquellen):
  - **Core-Impfungen** sind Staupe, Parvovirose und Leptospirose.
  - **Tollwut** ist seit 2021 nicht mehr Core, weil Deutschland frei von terrestrischer Tollwut ist.
    Sie bleibt Pflicht für Reisen und ist in Vereinen trotzdem die häufigste Forderung.
  - **Non-core** sind Zwingerhusten (Bordetella, Parainfluenza), Hepatitis/CAV-2 (laut einer Quelle),
    Borreliose und Leishmaniose.
  - **Auffrischung:** Staupe, Parvo und Tollwut je nach Impfstoff bis zu 3 Jahre, Leptospirose jährlich.
- **Landesrecht** (Haftpflicht, Chip, Sachkunde) ist je Bundesland verschieden. In Niedersachsen gilt
  zum Beispiel Haftpflicht und Chip für alle Hunde. In NRW gilt das nur für große Hunde. In
  Baden-Württemberg betrifft es nur gefährliche Hunde. Die Angaben stammen aus Gemeindemerkblättern
  und sind **nicht** gegen den Gesetzestext geprüft. Für die App folgt daraus nur, dass Haftpflicht
  abschaltbar sein sollte, aber standardmäßig an bleibt.

## 4. Wie andere Software das löst

| Produkt | Muster |
|---|---|
| [Time To Pet](https://help.timetopet.com/article/227-pet-vaccinations) | Liste „Vaccination Types“. Beim Anlegen wählt man: Pflicht für **alle bestehenden + neuen** Tiere, nur für **neue**, oder nur **von Hand je Tier**. Rot heißt überfällig, Orange heißt fällig in ≤ 30 Tagen. |
| [MoeGo](https://help.moego.pet/en/articles/12845387-pet-vaccine) | Je Impfstoff **Optional/Required**. „Required“ lässt sich auf einzelne **Leistungen** (Daycare, Boarding …) begrenzen. Die Ampel zeigt per Hover, *was* fehlt. |
| [DaySmart Pet](https://help.daysmartpet.com/en/articles/9301492-master-vaccination-overview) | „Master Vaccination List“ mit dem Häkchen „Required“ je Leistung. Benutzte Einträge werden **archiviert statt gelöscht**. Eine medizinische Befreiung heißt: kein Eintrag am Tier. |
| Gingr | Systemschalter „gültige Impfungen beim Check-in verlangen“, mit Override. Mail 30 Tage vor Ablauf. Die Help-Seiten waren gesperrt, die Angaben stammen nur aus Suchtreffern. |
| [easyVerein](https://hilfe.easyverein.com/en/articles/375746) | Keine Hundefunktion, aber „Individuelle Felder“ mit Typ Datei/Datum und **Freigabe durch den Admin**. |

In Deutschland habe ich nichts Vergleichbares gefunden. Anolla erwähnt „Impfkontrollen“ als Modul,
aber ohne Details. Die Vereinssoftware (campai, WISO Mein Verein, S-Verein …) hat dazu nichts belegt.

**Diese Muster lohnen sich zum Übernehmen:**
- Pflicht ist eine Eigenschaft der *Impfart*, nicht des Hundes.
- Das Ablaufdatum bleibt je Hund.
- Eine Impfart wird archiviert statt gelöscht.
- Beim Einführen einer neuen Pflicht zeigt die App vorher, wie viele Hunde dann rot werden.
- Die App warnt statt zu sperren.
- Erinnerungen bleiben manuell. Das passt zu den WhatsApp-/E-Mail-Knöpfen, die Saskia schon nutzt.

---

## 5. Plan: So könnten die EINSTELLUNGEN aussehen

### Schritt 1 – „Was verlangt euer Verein?“ (klein, empfohlen als Nächstes)

Im Einstellungsdialog kommt ein neuer Abschnitt mit einer Zeile je vorhandener Anforderung und drei
Knöpfen:

```
Was verlangt euer Verein?                 Pflicht   Freiwillig   Ausblenden
  SHP/DAP/DHP – Staupe, Hepatitis, Parvo     (●)         ( )          ( )
  L – Leptospirose                           (●)         ( )          ( )
  BbPi – Zwingerhusten                       (●)         ( )          ( )
  T – Tollwut                                (●)         ( )          ( )
  Haftpflicht-Nachweis                       (●)         ( )          ( )
  Geburtstag                                 (●)         ( )          ( )
  Einwilligung Fotoaufnahmen                 (●)         ( )          ( )

  Vorlage übernehmen: [HSV Großbottwar (bisher)] [Nur Tollwut]
                      [Rettungshundestaffel: SHP + L + T] [StIKo-Kern: SHP + L]

  ⚠ Mit dieser Auswahl hätten 3 Hunde neu Handlungsbedarf, 5 keinen mehr.
```

- **Pflicht:** Die Anforderung zählt für die Ampel, für „Handlungsbedarf“, für die Kennzahlen und für
  die WhatsApp-/E-Mail-Nachfrage. So verhält sich die App heute.
- **Freiwillig:** Die Anforderung wird angezeigt und eingetragen, die Erkennung füllt sie weiter aus.
  Sie macht aber nichts rot und wird nicht nachgefragt.
- **Ausblenden:** Die Anforderung verschwindet aus Karten, Formularen und Nachfragen. **Eingetragene
  Daten bleiben in der Datenbank** und sind wieder da, sobald man umschaltet.
- **Standard ist überall „Pflicht“.** Für Saskia ändert sich also nichts, bis sie selbst etwas umstellt.
- Die Vorschauzeile unten macht sichtbar, was eine Umstellung bewirkt. Die Idee stammt von Time To Pet.

**Technisch:**
- Die Einstellungen kommen in die vorhandene Tabelle `einstellung`, entweder als ein Schlüssel je
  Anforderung (`pflicht_gueltig_l` = `pflicht|freiwillig|aus`) oder als ein JSON-Eintrag. Leere bzw.
  Standardwerte werden wie bisher nicht gespeichert.
- Es gibt **keine neue Spalte und keine Migration**. Das Formatrisiko beim Update ist damit null.
- Wirkt in `hund_ansicht()` (Gesamtstatus), `fehlende_angaben()` / `impf_punkte()`, `KENNZAHL_FILTER`,
  `impfungen_faellig()` (`/nachweise`), `hund_form.html` und auf den Hundekarten.
- Die Fotoeinwilligung wirkt zusätzlich auf `Person.foto_status` (Kachel „foto“).
- Die Erkennung (`erkennung.py`) bleibt unverändert und schlägt weiter alle vier Impfungen vor. Ein
  Vorschlag für eine ausgeblendete Impfung wird nur nicht angezeigt.
- Tests: je Stufe ein Test für Gesamtstatus und Nachricht. Dazu ein Test, der prüft, dass beim
  Ausblenden die Daten erhalten bleiben. Danach Windows-Test wie immer.

### Schritt 2 – Vorlauf und Begriffe (klein, optional)

- **„Bald fällig“ einstellbar machen**, zum Beispiel 4 oder 6 Wochen. Im Code gibt es heute zwei Werte:
  `get_status()` rechnet mit **1 Monat**, `ERINNERUNG_VORLAUF` mit **6 Wochen**. Das sollte ohnehin
  ein Wert werden.
- **Tollwut-Ausnahme für Welpen** (Hundeschule PRO-DOG, StIKo: Tollwut frühestens mit 12 Wochen): Bis
  zum Alter X ist eine Pflichtimpfung nur „freiwillig“. Das geht nur, wenn der Geburtstag bekannt ist.

### Schritt 3 – Eigene Impfarten (nur bei echtem Bedarf)

Erst wenn ein Verein eine fünfte Impfung braucht (zum Beispiel Borreliose, Leishmaniose oder Pi getrennt
von Bb), reichen die vier festen Spalten nicht mehr. Dann gilt:
- **Neue Tabelle** `impfung (hund_id, art, gueltig_bis, nachweis_id)` und eine Stammliste der Impfarten
  in den Einstellungen (Name, Kürzel, Krankheiten, übliche Gültigkeit, Pflichtstufe, archiviert).
- Eine **eigene Migration** mit Sicherung übernimmt die vier alten Spalten. Die alten Spalten bleiben
  stehen, wie bei `haftpflicht_nachweis`.
- `impfstoffe.py` muss dann Aufkleber auf frei definierte Impfarten abbilden können. Die Erkennung
  (`erkennung.py`) setzt heute die vier festen Felder voraus.

Das ist der größte und riskanteste Umbau. Ich empfehle ihn **nicht**, solange niemand konkret danach fragt.

### Schritt 4 – Gruppen und weitere Nachweise (Zukunft)

- **Gruppen/Sparten je Hund** (Welpengruppe, Sport, Staffel, Besuchshunde), jede mit eigener Liste
  „Pflicht/Freiwillig“. Bei MoeGo und DaySmart Pet ist das die Pflicht je Leistung. In keiner der
  untersuchten Platzordnungen unterscheiden sich die Impfregeln je Sparte. Ich erwarte den Bedarf
  deshalb vor allem bei gemischten Vereinen mit Staffel.
- **Neue Nachweisarten** über `NACHWEIS_ARTEN`, ohne neue Tabelle:
  - Prüfung (gültig bis 31.12. des Folgejahres)
  - Erste-Hilfe-Kurs des Hundeführers (gültig 2–3 Jahre)
  - Tierärztliche Gesundheitsbescheinigung (jährlich)
  - Chipnummer ist schon da (Feld `chipnummer` am Nachweis), Wesenstest wäre eine weitere Art
- **Stichtag-Prüfung:** „Ist am Prüfungstag (Datum) alles gültig?“ Gingr prüft das gegen das Ende des
  Aufenthalts. Das ist nützlich für Turniere, bei denen Tollwut auf dem Meldeschein verlangt wird.

## 6. Offene Fragen an Saskia und Kai

1. **Pi / „5-fach“:** In der App gehört Pi heute zur Impfung „BbPi“ (Zwingerhusten). Ein 5-fach-Impfstoff
   wie Nobivac SHPPi + L4 deckt Pi ab, aber nicht Bordetella. Ist für die Staffel wichtig, dass Pi
   *getrennt* erfasst wird? Laut BRH-, DRK- und DLRG-Ordnung ist Pi dort nicht verlangt. Dann reicht
   „BbPi ausblenden“.
2. **Ausblenden oder nur Freiwillig?** Soll eine nicht verlangte Impfung ganz verschwinden oder
   sichtbar bleiben (grau, „freiwillig“)?
3. **Zielbild „App für andere Vereine“:** Soll Schritt 1 schon mit Blick auf andere Vereine gebaut
   werden, also mit Vorlagen, Vereinsname und Logo als Einstellung? Oder reicht es fürs Erste, dass
   Saskia es für den HSV umstellen kann?

## Grenzen dieser Recherche

- Den Stand der Vereinsseiten kenne ich nicht. Zwei Beispiele stammen nur aus Suchtreffern (in der
  Tabelle mit \* markiert).
- Nicht im Wortlaut gelesen habe ich:
  - die VDH-Prüfungsordnungen
  - den Volltext der StIKo-Vet-Leitlinie
  - die Help-Seiten von Gingr
  - die Kapitel „Gültigkeit“ und „Versicherung“ der DRK-PO 2024
  - die Landesgesetze
- Nicht gefunden habe ich Ordnungen von Malteser, Johanniter, ASB und Feuerwehr-Staffeln.
