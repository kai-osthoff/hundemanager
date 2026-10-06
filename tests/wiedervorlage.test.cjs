// Ohne Browser/zusätzliche Pakete: echte Countdown-Datei mit kontrollierter Uhr ausführen.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const code = fs.readFileSync(path.join(__dirname, '..', 'static', 'wiedervorlage.js'), 'utf8');

function umgebung(vorher = {}, antwort = async () => ({ok: true, json: async () => ({datum: '20.10.2026'})})) {
    let jetzt = 0;
    let tick;
    let daten = JSON.stringify(vorher);
    const aufrufe = [];
    function element(dataset = {}) {
        return {dataset, hidden: false, textContent: '', events: {},
            addEventListener(art, fn) { this.events[art] = fn; }};
    }
    const felder = Object.fromEntries(['status', 'countdown', 'text', 'balken', 'abbrechen', 'ok']
        .map(name => [`[data-wiedervorlage-${name}]`, element()]));
    felder['[data-wiedervorlage-status]'].textContent = 'Wiedervorlage am 10.10.2026';
    const karte = element({wiedervorlage: '1', url: '/hund/1/wiedervorlage'});
    karte.querySelector = name => felder[name];
    const links = [element({wiedervorlageLink: '1'}), element({wiedervorlageLink: '1'})];
    const context = {
        document: {
            getElementById: () => element({wartezeit: '30'}),
            querySelectorAll: name => name === '[data-wiedervorlage]' ? [karte] : links,
        },
        sessionStorage: {getItem: () => daten, setItem: (_, wert) => {daten = wert;}},
        Date: {now: () => jetzt},
        setInterval: fn => {tick = fn;},
        fetch: async (url, options) => {aufrufe.push({url, options}); return antwort();},
    };
    vm.runInNewContext(code, context);
    return {felder, aufrufe, links, daten: () => JSON.parse(daten),
        warten(ms) {jetzt += ms; tick();},
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
