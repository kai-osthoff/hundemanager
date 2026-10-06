// Frist auch nach Seitenwechsel/Neuladen fortsetzen; die App bestätigt keinen Versand.
(() => {
    const config = document.getElementById('wiedervorlage-config');
    const wartezeit = Number(config.dataset.wartezeit);
    const schluessel = 'hundemanager-wiedervorlagen';
    const offen = JSON.parse(sessionStorage.getItem(schluessel) || '{}');
    const speichernStatus = () => sessionStorage.setItem(schluessel, JSON.stringify(offen));
    const laufend = new Set();
    const karten = new Map(Array.from(document.querySelectorAll('[data-wiedervorlage]'))
        .map(karte => [karte.dataset.wiedervorlage, karte]));

    async function speichern(id) {
        if (!offen[id] || laufend.has(id)) return;
        laufend.add(id);
        const karte = karten.get(id);
        if (karte) {
            karte.querySelector('[data-wiedervorlage-countdown]').hidden = true;
            karte.querySelector('[data-wiedervorlage-status]').textContent = 'Wiedervorlage wird gespeichert …';
        }
        try {
            const antwort = await fetch(offen[id].url, {method: 'POST'});
            if (!antwort.ok) throw new Error('Speichern fehlgeschlagen');
            const ergebnis = await antwort.json();
            delete offen[id];
            speichernStatus();
            if (karte) {
                const status = karte.querySelector('[data-wiedervorlage-status]');
                status.textContent = ergebnis.datum
                    ? `${ergebnis.faellig ? 'Wiedervorlage fällig seit' : 'Wiedervorlage am'} ${ergebnis.datum}`
                    : 'Alles erledigt – keine Wiedervorlage nötig.';
                status.className = ergebnis.faellig ? 'status-cell status-abgelaufen' : '';
            }
        } catch (fehler) {
            // Keine stille Wiederholung: Saskia entscheidet mit OK über einen neuen Versuch.
            offen[id].fehler = true;
            speichernStatus();
            if (karte) {
                karte.querySelector('[data-wiedervorlage-countdown]').hidden = false;
                karte.querySelector('[data-wiedervorlage-text]').textContent = 'Speichern fehlgeschlagen. Mit OK erneut versuchen.';
                karte.querySelector('[data-wiedervorlage-status]').textContent = '';
            }
        } finally {
            laufend.delete(id);
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
            delete offen[id];
            speichernStatus();
            karte.querySelector('[data-wiedervorlage-countdown]').hidden = true;
        });
        karte.querySelector('[data-wiedervorlage-ok]').addEventListener('click', () => speichern(id));
    }
    document.querySelectorAll('[data-wiedervorlage-link]').forEach(link => {
        link.addEventListener('click', () => {
            const id = link.dataset.wiedervorlageLink;
            const karte = karten.get(id);
            if (laufend.has(id)) return;
            offen[id] = {ende: Date.now() + wartezeit * 1000, dauer: wartezeit * 1000, url: karte.dataset.url};
            speichernStatus();
            aktualisieren();
        });
    });
    aktualisieren();
    setInterval(aktualisieren, 200);
})();
