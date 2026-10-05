#!/usr/bin/env bash
# release.sh - Neue Version für Saskia veröffentlichen
#
#   ./release.sh 5.2.0 "Fotofreigabe wird jetzt in der Übersicht angezeigt"
#
# Setzt VERSION, committet, taggt, pusht und legt das GitHub-Release an.
# Saskias Hundemanager sieht das Release innerhalb von 6 Stunden
# (oder sofort über "Nach Updates suchen").
set -euo pipefail
cd "$(dirname "$0")"

VERSION="${1:?Versionsnummer fehlt, z.B. ./release.sh 5.2.0 \"Was ist neu\"}"
NOTIZEN="${2:?Release-Notizen fehlen - die sieht Saskia unter \"Was ist neu?\"}"
VERSION="${VERSION#v}"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Version muss das Format X.Y.Z haben" >&2; exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
    echo "Es gibt nicht committete Änderungen - erst committen:" >&2
    git status --short >&2; exit 1
fi
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
    echo "Tag v$VERSION existiert bereits" >&2; exit 1
fi

python3 -m py_compile app.py updater.py start.py

echo "$VERSION" > VERSION
git add VERSION
git diff --cached --quiet || git commit -m "Version $VERSION"
git tag "v$VERSION"
git push origin main "v$VERSION"
gh release create "v$VERSION" --title "Version $VERSION" --notes "$NOTIZEN"
echo "Release v$VERSION veröffentlicht."
