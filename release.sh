#!/usr/bin/env bash
# release.sh - Neue Version für Saskia veröffentlichen
#
#   ./release.sh "Fotofreigabe wird jetzt in der Übersicht angezeigt"
#
# Versionsnummern: Wir bleiben bei 5.1.x und zählen nur die letzte Stelle hoch.
# Das Skript ermittelt die nächste Nummer selbst (5.1.1 -> 5.1.2 -> ...).
#
# Ablauf - bricht bei jedem Fehler ab, bevor Saskia etwas davon sieht:
#   1. Tests lokal (macOS)
#   2. VERSION setzen, committen, pushen
#   3. Auf den Windows-Test von GitHub warten - nur wenn ALLES grün ist:
#   4. Tag + GitHub-Release -> Saskias Hundemanager zeigt das Update an
set -euo pipefail
cd "$(dirname "$0")"

REPO="kai-osthoff/hundemanager"
SERIE="5.1"
NOTIZEN="${1:?Release-Notizen fehlen - die sieht Saskia unter \"Was ist neu?\". Aufruf: ./release.sh \"Was ist neu\"}"

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Es gibt nicht committete Änderungen - erst committen:" >&2
    git status --short >&2; exit 1
fi

git fetch -q --tags origin
LETZTE=$(git tag -l "v$SERIE.*" | python3 -c "import sys; t=[int(z.strip().rsplit('.',1)[1]) for z in sys.stdin if z.strip()]; print(max(t) if t else -1)")
VERSION="$SERIE.$((LETZTE + 1))"
echo "Neue Version: $VERSION"

echo "== Tests lokal =="
PYTHON=".venv/bin/python"; [[ -x "$PYTHON" ]] || PYTHON="python3"
"$PYTHON" -m unittest discover -s tests

echo "$VERSION" > VERSION
git add VERSION
git diff --cached --quiet || git commit -q -m "Version $VERSION"
git push -q origin main
SHA=$(git rev-parse HEAD)

echo "== Warte auf den Windows-Test für ${SHA:0:7} (kann einige Minuten dauern) =="
for _ in $(seq 1 90); do
    sleep 20
    STAND=$(gh api "repos/$REPO/commits/$SHA/check-runs" --jq \
        '[.total_count, ([.check_runs[] | select(.status != "completed")] | length), ([.check_runs[] | select(.conclusion != "success" and .status == "completed")] | length)] | @tsv')
    read -r GESAMT OFFEN ROT <<< "$STAND"
    if [[ "$GESAMT" -gt 0 && "$ROT" -gt 0 ]]; then
        echo "Windows-Test ROT - kein Release. Details: https://github.com/$REPO/actions" >&2
        exit 1
    fi
    if [[ "$GESAMT" -gt 0 && "$OFFEN" -eq 0 ]]; then
        echo "Windows-Test grün ($GESAMT Läufe)."
        break
    fi
    echo "  ... $OFFEN von $GESAMT Läufen noch offen"
done
[[ "${OFFEN:-1}" -eq 0 && "${GESAMT:-0}" -gt 0 ]] || { echo "Windows-Test nicht rechtzeitig fertig - kein Release." >&2; exit 1; }

git tag "v$VERSION"
git push -q origin "v$VERSION"
# REST statt "gh release create" - das nutzt GraphQL und läuft öfter ins Rate-Limit
gh api "repos/$REPO/releases" \
    -f tag_name="v$VERSION" -f name="Version $VERSION" -f body="$NOTIZEN" --jq .html_url
echo "Release v$VERSION veröffentlicht."
