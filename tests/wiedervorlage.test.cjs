// Ohne Browser/zusätzliche Pakete: echte Countdown-Datei mit kontrollierter Uhr ausführen.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const code = fs.readFileSync(path.join(__dirname, '..', 'static', 'wiedervorlage.js'), 'utf8');

function umgebung(vorher = {}, antwort = async () => ({ok: true, json: async () => (
    {datum: '20.10.2026', datum_iso: '2026-10-20', faellig: false})}), uebersicht = false) {
    let jetzt = 0;
    let tick;
    let daten = JSON.stringify(vorher);
    const aufrufe = [];
    let neuladen = 0;
    function element(dataset = {}) {
        return {dataset, hidden: false, disabled: false, textContent: '', events: {},
            setAttribute(name, wert) {this[name] = wert;},
            addEventListener(art, fn) { this.events[art] = fn; }};
    }
    const felder = Object.fromEntries(['status', 'countdown', 'text', 'balken', 'abbrechen', 'ok',
        'bearbeiten', 'editor', 'form', 'datum', 'verwerfen', 'loeschen', 'fehler']
        .map(name => [`[data-wiedervorlage-${name}]`, element()]));
    felder['[data-wiedervorlage-status]'].textContent = 'Wiedervorlage am 10.10.2026';
    felder['[data-wiedervorlage-datum]'].value = '2026-10-10';
    felder['[data-wiedervorlage-editor]'].hidden = true;
    felder['[data-wiedervorlage-fehler]'].hidden = true;
    const karte = element({wiedervorlage: '1', url: '/hund/1/wiedervorlage',
        datum: '2026-10-10', standard: '2026-10-22'});
    karte.querySelector = name => felder[name];
    karte.querySelectorAll = () => Object.values(felder);
    const links = [element({wiedervorlageLink: '1'}), element({wiedervorlageLink: '1'})];
    const context = {
        document: {
            getElementById: () => element({wartezeit: '30'}),
            querySelector: () => uebersicht ? element() : null,
            querySelectorAll: name => name === '[data-wiedervorlage]' ? [karte] : links,
        },
        sessionStorage: {getItem: () => daten, setItem: (_, wert) => {daten = wert;}},
        Date: {now: () => jetzt},
        URLSearchParams,
        location: {reload: () => {neuladen++;}},
        setInterval: fn => {tick = fn;},
        fetch: async (url, options) => {aufrufe.push({url, options}); return antwort(url, options);},
    };
    vm.runInNewContext(code, context);
    return {felder, aufrufe, links, daten: () => JSON.parse(daten), neuladen: () => neuladen,
        warten(ms) {jetzt += ms; tick();},
        setzen(datum) {
            felder['[data-wiedervorlage-datum]'].value = datum;
            return felder['[data-wiedervorlage-form]'].events.submit({preventDefault() {}});
        },
        klick(name) {return felder[`[data-wiedervorlage-${name}]`].events.click();}};
}
const fertig = () => new Promise(resolve => setImmediate(resolve));

test('WhatsApp und Mail starten Countdown; Balken schrumpft und speichert genau einmal', async () => {
    const u = umgebung();
    u.links[0].events.click();
    assert.equal(u.aufrufe.length, 0);
    assert.equal(u.felder['[data-wiedervorlage-balken]'].value, 30000);
    u.warten(10000);
    assert.equal(u.felder['[data-wiedervorlage-balken]'].value, 20000);
    u.links[1].events.click(); // neue Anfrage beginnt erneut mit 30 Sekunden
    u.warten(29999);
    assert.equal(u.aufrufe.length, 0);
    u.warten(1);
    u.warten(200);
    await fertig();
    assert.equal(u.aufrufe.length, 1);
    assert.equal(u.aufrufe[0].options.method, 'POST');
    assert.deepEqual(u.daten(), {});
    assert.equal(u.felder['[data-wiedervorlage-status]'].textContent, 'Wiedervorlage am 20.10.2026');
});

test('Abbrechen speichert nichts und behält die bestehende Wiedervorlage', async () => {
    const u = umgebung();
    u.links[0].events.click();
    u.klick('abbrechen');
    u.warten(60000);
    await fertig();
    assert.equal(u.aufrufe.length, 0);
    assert.equal(u.felder['[data-wiedervorlage-countdown]'].hidden, true);
    assert.equal(u.felder['[data-wiedervorlage-status]'].textContent, 'Wiedervorlage am 10.10.2026');
    assert.deepEqual(u.daten(), {});
});

test('OK speichert sofort; Neuladen setzt die ursprüngliche Frist fort', async () => {
    const u = umgebung();
    u.links[0].events.click();
    const neu = umgebung(u.daten());
    neu.warten(10000);
    assert.equal(neu.felder['[data-wiedervorlage-balken]'].value, 20000);
    await neu.klick('ok');
    assert.equal(neu.aufrufe.length, 1);
    neu.warten(60000);
    assert.equal(neu.aufrufe.length, 1);
});

test('Fehlgeschlagenes Speichern wird angezeigt und kann mit OK wiederholt werden', async () => {
    let versuche = 0;
    const u = umgebung({}, async () => ({ok: ++versuche > 1, json: async () => ({datum: null})}));
    u.links[0].events.click();
    u.warten(30000);
    await fertig();
    assert.match(u.felder['[data-wiedervorlage-text]'].textContent, /fehlgeschlagen/);
    u.warten(60000);
    assert.equal(u.aufrufe.length, 1);
    await u.klick('ok');
    assert.equal(u.aufrufe.length, 2);
    assert.deepEqual(u.daten(), {});
    assert.match(u.felder['[data-wiedervorlage-status]'].textContent, /Alles erledigt/);
});

test('Datum ändern beendet den Countdown; Abbrechen behält den gespeicherten Termin', async () => {
    const u = umgebung();
    u.links[0].events.click();
    u.klick('bearbeiten');
    assert.equal(u.felder['[data-wiedervorlage-editor]'].hidden, false);
    assert.equal(u.felder['[data-wiedervorlage-datum]'].value, '2026-10-10');
    u.felder['[data-wiedervorlage-datum]'].value = '2026-11-05';
    u.klick('verwerfen');
    u.warten(60000);
    await fertig();
    assert.equal(u.aufrufe.length, 0);
    assert.deepEqual(u.daten(), {});
    assert.equal(u.felder['[data-wiedervorlage-status]'].textContent, 'Wiedervorlage am 10.10.2026');
    u.klick('bearbeiten');
    assert.equal(u.felder['[data-wiedervorlage-datum]'].value, '2026-10-10');
    const neu = umgebung(u.daten());
    neu.warten(60000);
    assert.equal(neu.aufrufe.length, 0);
});

test('Eigenes Datum wird sofort gespeichert und überlebt den alten Countdown', async () => {
    const u = umgebung({}, async () => ({ok: true, json: async () => (
        {datum: '05.11.2026', datum_iso: '2026-11-05', faellig: false})}));
    u.links[0].events.click();
    await u.setzen('2026-11-05');
    assert.equal(u.aufrufe.length, 1);
    assert.equal(u.aufrufe[0].url, '/hund/1/wiedervorlage');
    assert.equal(u.aufrufe[0].options.body.get('aktion'), 'setzen');
    assert.equal(u.aufrufe[0].options.body.get('datum'), '2026-11-05');
    assert.equal(u.felder['[data-wiedervorlage-status]'].textContent, 'Wiedervorlage am 05.11.2026');
    assert.equal(u.felder['[data-wiedervorlage-editor]'].hidden, true);
    assert.equal(u.felder['[data-wiedervorlage-datum]'].value, '2026-11-05');
    u.warten(60000);
    const neu = umgebung(u.daten());
    neu.warten(60000);
    await fertig();
    assert.equal(u.aufrufe.length, 1);
    assert.equal(neu.aufrufe.length, 0);
});

test('Löschen beendet Countdown; erst eine neue Anfrage legt wieder einen Termin an', async () => {
    const u = umgebung({}, async () => ({ok: true, json: async () => (
        {datum: null, datum_iso: null, faellig: false})}));
    u.links[0].events.click();
    await u.klick('loeschen');
    assert.equal(u.aufrufe[0].options.body.get('aktion'), 'loeschen');
    assert.match(u.felder['[data-wiedervorlage-status]'].textContent, /entfernt/);
    assert.equal(u.felder['[data-wiedervorlage-loeschen]'].hidden, true);
    assert.equal(u.felder['[data-wiedervorlage-bearbeiten]'].textContent, 'Datum setzen');
    u.klick('bearbeiten');
    assert.equal(u.felder['[data-wiedervorlage-datum]'].value, '2026-10-22');
    u.klick('verwerfen');
    u.warten(60000);
    const neu = umgebung(u.daten());
    neu.warten(60000);
    await fertig();
    assert.equal(neu.aufrufe.length, 0);
    assert.equal(u.aufrufe.length, 1);
    u.links[1].events.click();
    await u.klick('ok');
    assert.equal(u.aufrufe.length, 2);
    assert.equal(u.aufrufe[1].options.body, undefined);
});

test('Manuelle Fehler behalten den Termin und erlauben eine bewusste Wiederholung', async () => {
    let versuche = 0;
    const u = umgebung({}, async () => ({ok: ++versuche > 1, json: async () => (
        versuche === 1 ? {fehler: 'Bitte ein gültiges Datum auswählen.'} :
            {datum: '05.11.2026', datum_iso: '2026-11-05', faellig: false})}));
    u.links[0].events.click();
    u.klick('bearbeiten');
    await u.setzen('2026-11-05');
    assert.equal(u.felder['[data-wiedervorlage-status]'].textContent, 'Wiedervorlage am 10.10.2026');
    assert.equal(u.felder['[data-wiedervorlage-fehler]'].hidden, false);
    assert.match(u.felder['[data-wiedervorlage-fehler]'].textContent, /gültiges Datum/);
    u.warten(60000);
    assert.equal(u.aufrufe.length, 1);
    assert.deepEqual(u.daten(), {});
    await u.setzen('2026-11-05');
    assert.equal(u.aufrufe.length, 2);
    assert.equal(u.felder['[data-wiedervorlage-fehler]'].hidden, true);
    assert.equal(u.felder['[data-wiedervorlage-status]'].textContent, 'Wiedervorlage am 05.11.2026');
});

test('Laufender POST sperrt weitere Aktionen; Übersicht lädt erst nach der Antwort neu', async () => {
    let antworten;
    const u = umgebung({}, () => new Promise(resolve => {antworten = resolve;}), true);
    u.links[0].events.click();
    const speichern = u.klick('ok');
    assert.equal(u.felder['[data-wiedervorlage-loeschen]'].disabled, true);
    await u.klick('loeschen');
    await u.setzen('2026-11-05');
    u.klick('bearbeiten');
    u.links[1].events.click();
    u.warten(60000);
    assert.equal(u.aufrufe.length, 1);
    assert.equal(u.neuladen(), 0);
    antworten({ok: true, json: async () => ({datum: '20.10.2026', datum_iso: '2026-10-20'})});
    await speichern;
    assert.equal(u.neuladen(), 1);
    assert.equal(u.felder['[data-wiedervorlage-loeschen]'].disabled, false);
    assert.deepEqual(u.daten(), {});
});

test('Neuladen wartet auch auf einen bereits laufenden POST eines anderen Hundes', async () => {
    let antworten;
    const u = umgebung({'2': {url: '/hund/2/wiedervorlage', ende: 0, dauer: 30000}},
        url => url.includes('/2/') ? new Promise(resolve => {antworten = resolve;}) :
            Promise.resolve({ok: true, json: async () => ({datum: null, datum_iso: null})}), true);
    await u.klick('loeschen');
    assert.equal(u.aufrufe.length, 2);
    assert.equal(u.neuladen(), 0);
    antworten({ok: true, json: async () => ({datum: '20.10.2026', datum_iso: '2026-10-20'})});
    await fertig();
    assert.equal(u.neuladen(), 1);
    assert.deepEqual(u.daten(), {});
});

test('Neuladen verwirft keinen offenen Datumseditor nach dem Speichern eines anderen Hundes', async () => {
    let antworten;
    const u = umgebung({'2': {url: '/hund/2/wiedervorlage', ende: 0, dauer: 30000}},
        () => new Promise(resolve => {antworten = resolve;}), true);
    u.klick('bearbeiten');
    u.felder['[data-wiedervorlage-datum]'].value = '2026-11-05';
    antworten({ok: true, json: async () => ({datum: '20.10.2026', datum_iso: '2026-10-20'})});
    await fertig();
    assert.equal(u.neuladen(), 0);
    assert.equal(u.felder['[data-wiedervorlage-datum]'].value, '2026-11-05');
    u.klick('verwerfen');
    assert.equal(u.neuladen(), 1);
});

test('Neuladen erhält einen manuellen Löschfehler bis zur bewussten Wiederholung', async () => {
    let antworten;
    let versuche = 0;
    const u = umgebung({'2': {url: '/hund/2/wiedervorlage', ende: 0, dauer: 30000}},
        url => url.includes('/2/') ? new Promise(resolve => {antworten = resolve;}) :
            Promise.resolve({ok: ++versuche > 1, json: async () => ({datum: null, datum_iso: null})}), true);
    await u.klick('loeschen');
    antworten({ok: true, json: async () => ({datum: '20.10.2026', datum_iso: '2026-10-20'})});
    await fertig();
    assert.equal(u.neuladen(), 0);
    assert.equal(u.felder['[data-wiedervorlage-fehler]'].hidden, false);
    assert.equal(u.felder['[data-wiedervorlage-status]'].textContent, 'Wiedervorlage am 10.10.2026');
    u.warten(60000);
    assert.equal(u.aufrufe.length, 2);
    await u.klick('loeschen');
    assert.equal(u.neuladen(), 1);
});
