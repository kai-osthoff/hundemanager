#!/usr/bin/env bash
# windows-test.sh - Tests in der lokalen Windows-11-VM (Parallels), Rückmeldung in ~1 Minute
#
#   ./windows-test.sh                 alle Tests
#   ./windows-test.sh -k Haftpflicht  nur passende Tests (Optionen gehen an unittest)
#
# Für schnelle Fehlersuche auf echtem Windows 11. Der GitHub-Windows-Test bleibt die
# Sperre vor jedem Release (release.sh).
set -euo pipefail
cd "$(dirname "$0")"

VM="${HUNDEMANAGER_VM:-Windows 11}"
PY='%LOCALAPPDATA%\Programs\Python\Python313\python.exe'
ZIEL='C:\hundemanager-test'

case "$(prlctl list "$VM" -o status --no-header | tr -d ' ')" in
    paused|suspended) prlctl resume "$VM" >/dev/null ;;
    stopped) prlctl start "$VM" >/dev/null; sleep 40 ;;
esac

# Alte Stände für die Update-Tests - in der VM gibt es kein git
mkdir -p .windows-test
for tag in v5.1.0 v5.1.2; do
    git archive --format=zip -o ".windows-test/$tag.zip" "$tag"
done

# Mac-Ordner ist in der VM unter \\Mac\Home erreichbar - getestet wird auf einer Kopie auf C:
# (der geteilte Ordner verhält sich wie ein Netzlaufwerk, nicht wie NTFS)
REL="${PWD#"$HOME"/}"
QUELLE="\\\\Mac\\Home\\${REL//\//\\}"

prlctl exec "$VM" --current-user cmd /c "robocopy \"$QUELLE\" $ZIEL /MIR /XD .venv instance __pycache__ .git /NFL /NDL /NJH /NJS /NP >nul & cd /d $ZIEL && \"$PY\" -m pip install --disable-pip-version-check -q -r requirements.txt && set HUNDEMANAGER_TEST_ARCHIV=$ZIEL\\.windows-test&& \"$PY\" -m unittest discover -s tests $*"
