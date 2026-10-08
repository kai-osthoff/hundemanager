// Frist auch nach Seitenwechsel/Neuladen fortsetzen; die App bestätigt keinen Versand.
(() => {
    const config = document.getElementById('wiedervorlage-config');
    const wartezeit = Number(config.dataset.wartezeit);
    const schluessel = 'hundemanager-wiedervorlagen';
    const offen = JSON.parse(sessionStorage.getItem(schluessel) || '{}');
    const speichernStatus = () => sessionStorage.setItem(schluessel, JSON.stringify(offen));
    const laufend = new Set();
    let neuladen = false;
    const karten = new Map(Array.from(document.querySelectorAll('[data-wiedervorlage]'))
        .map(karte => [karte.dataset.wiedervorlage, karte]));

    function abbrechen(id) {
        delete offen[id];
        speichernStatus();
        const karte = karten.get(id);
        if (karte) karte.querySelector('[data-wiedervorlage-countdown]').hidden = true;
    }

    function editorSchliessen(karte) {
        karte.querySelector('[data-wiedervorlage-editor]').hidden = true;
        karte.querySelector('[data-wiedervorlage-bearbeiten]').setAttribute('aria-expanded', 'false');
    }

    function beiBedarfNeuLaden() {
        const bearbeitung = Array.from(karten.values()).some(karte =>
            !karte.querySelector('[data-wiedervorlage-editor]').hidden ||
            !karte.querySelector('[data-wiedervorlage-fehler]').hidden);
        if (neuladen && laufend.size === 0 && !bearbeitung) location.reload();
    }

    async function speichern(id, aktion, datum) {
        if ((!aktion && !offen[id]) || laufend.has(id)) return;
        const karte = karten.get(id);
        const url = aktion ? karte.dataset.url : offen[id].url;
        if (aktion) abbrechen(id);
        laufend.add(id);
        const status = karte && karte.querySelector('[data-wiedervorlage-status]');
        const vorher = status && status.textContent;
        if (karte) {
            karte.querySelectorAll('button, input').forEach(feld => {feld.disabled = true;});
            karte.querySelector('[data-wiedervorlage-fehler]').hidden = true;
            karte.querySelector('[data-wiedervorlage-countdown]').hidden = true;
            status.textContent = 'Wiedervorlage wird gespeichert …';
        }
        try {
            const optionen = {method: 'POST'};
            if (aktion) optionen.body = new URLSearchParams({aktion, ...(datum ? {datum} : {})});
            const antwort = await fetch(url, optionen);
            if (!antwort.ok) {
                const fehler = await antwort.json().catch(() => ({}));
                throw new Error(fehler.fehler || 'Bitte erneut versuchen.');
            }
            const ergebnis = await antwort.json();
            delete offen[id];
            speichernStatus();
            if (karte) {
                status.textContent = ergebnis.datum
                    ? `${ergebnis.faellig ? 'Wiedervorlage fällig seit' : 'Wiedervorlage am'} ${ergebnis.datum}`
                    : aktion === 'loeschen' ? 'Wiedervorlage entfernt.' : 'Alles erledigt – keine Wiedervorlage nötig.';
                status.className = ergebnis.faellig ? 'status-cell status-abgelaufen' : '';
                karte.dataset.datum = ergebnis.datum_iso || '';
                karte.querySelector('[data-wiedervorlage-datum]').value = karte.dataset.datum || karte.dataset.standard;
                karte.querySelector('[data-wiedervorlage-loeschen]').hidden = !ergebnis.datum;
                karte.querySelector('[data-wiedervorlage-bearbeiten]').textContent = ergebnis.datum ? 'Datum ändern' : 'Datum setzen';
                editorSchliessen(karte);
            }
            if (document.querySelector('[data-wiedervorlage-neuladen]')) neuladen = true;
        } catch (fehler) {
            // Keine stille Wiederholung: Saskia entscheidet über einen neuen Versuch.
            if (!aktion) {
                offen[id].fehler = true;
                speichernStatus();
            }
            if (karte) {
                status.textContent = vorher;
                if (aktion) {
                    const meldung = karte.querySelector('[data-wiedervorlage-fehler]');
                    meldung.hidden = false;
                    meldung.textContent = `Speichern fehlgeschlagen. ${fehler.message}`;
                } else {
                    karte.querySelector('[data-wiedervorlage-countdown]').hidden = false;
                    karte.querySelector('[data-wiedervorlage-text]').textContent = 'Speichern fehlgeschlagen. Mit OK erneut versuchen.';
                }
            }
        } finally {
            laufend.delete(id);
            if (karte) karte.querySelectorAll('button, input').forEach(feld => {feld.disabled = false;});
            beiBedarfNeuLaden();
        }
    }

    function aktualisieren() {
        for (const [id, eintrag] of Object.entries(offen)) {
            if (laufend.has(id)) continue;
            const karte = karten.get(id);
            if (eintrag.fehler) {
                if (karte) {
                    karte.querySelector('[data-wiedervorlage-countdown]').hidden = false;
                    karte.querySelector('[data-wiedervorlage-text]').textContent = 'Speichern fehlgeschlagen. Mit OK erneut versuchen.';
                }
                continue;
            }
            const rest = Math.max(0, eintrag.ende - Date.now());
            if (karte) {
                karte.querySelector('[data-wiedervorlage-countdown]').hidden = false;
                karte.querySelector('[data-wiedervorlage-text]').textContent = `Wiedervorlage wird in ${Math.ceil(rest / 1000)} Sekunden gespeichert …`;
                const balken = karte.querySelector('[data-wiedervorlage-balken]');
                balken.max = eintrag.dauer;
                balken.value = rest;
            }
            if (rest === 0) speichern(id);
        }
    }

    for (const [id, karte] of karten) {
        karte.querySelector('[data-wiedervorlage-abbrechen]').addEventListener('click', () => {
            if (laufend.has(id)) return;
            abbrechen(id);
        });
        karte.querySelector('[data-wiedervorlage-ok]').addEventListener('click', () => speichern(id));
        karte.querySelector('[data-wiedervorlage-bearbeiten]').addEventListener('click', () => {
            if (laufend.has(id)) return;
            abbrechen(id);
            karte.querySelector('[data-wiedervorlage-fehler]').hidden = true;
            const editor = karte.querySelector('[data-wiedervorlage-editor]');
            if (!editor.hidden) {
                editorSchliessen(karte);
                beiBedarfNeuLaden();
                return;
            }
            editor.hidden = false;
            karte.querySelector('[data-wiedervorlage-bearbeiten]').setAttribute('aria-expanded', 'true');
            karte.querySelector('[data-wiedervorlage-datum]').value = karte.dataset.datum || karte.dataset.standard;
        });
        karte.querySelector('[data-wiedervorlage-verwerfen]').addEventListener('click', () => {
            if (laufend.has(id)) return;
            karte.querySelector('[data-wiedervorlage-fehler]').hidden = true;
            editorSchliessen(karte);
            beiBedarfNeuLaden();
        });
        karte.querySelector('[data-wiedervorlage-form]').addEventListener('submit', event => {
            event.preventDefault();
            return speichern(id, 'setzen', karte.querySelector('[data-wiedervorlage-datum]').value);
        });
        karte.querySelector('[data-wiedervorlage-loeschen]').addEventListener('click', () => speichern(id, 'loeschen'));
    }
    document.querySelectorAll('[data-wiedervorlage-link]').forEach(link => {
        link.addEventListener('click', () => {
            const id = link.dataset.wiedervorlageLink;
            const karte = karten.get(id);
            if (laufend.has(id)) return;
            editorSchliessen(karte);
            karte.querySelector('[data-wiedervorlage-fehler]').hidden = true;
            offen[id] = {ende: Date.now() + wartezeit * 1000, dauer: wartezeit * 1000, url: karte.dataset.url};
            speichernStatus();
            aktualisieren();
            beiBedarfNeuLaden();
        });
    });
    aktualisieren();
    setInterval(aktualisieren, 200);
})();
