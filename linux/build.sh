#!/usr/bin/env bash
#
# Builds ClaudePet and petsend with PyInstaller.
#
# Both are one-dir builds, deliberately. One-file builds unpack themselves to
# a temp directory on every launch, which costs roughly a second — irrelevant
# for the app, but petsend runs on *every Claude Code tool call*, so that
# latency would land on every hook invocation.
#
# Output lands in dist/ClaudePet/, with petsend nested inside it so the app
# can copy it out to ~/.claudepet/bin on launch.
#
# Usage: ./build.sh [--clean]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$ROOT")"
ASSETS="$REPO_ROOT/Assets"
PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "No venv found at $PYTHON. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi
if [[ ! -d "$ASSETS" ]]; then
    echo "Assets folder not found at $ASSETS" >&2
    exit 1
fi

if [[ "${1:-}" == "--clean" ]]; then
    rm -rf "$ROOT/build" "$ROOT/dist"
fi

cd "$ROOT"

echo "Building petsend..."
"$PYTHON" -m PyInstaller \
    --noconfirm \
    --onedir \
    --console \
    --name petsend \
    --distpath "$ROOT/dist" \
    --workpath "$ROOT/build" \
    --specpath "$ROOT/build" \
    "$ROOT/petsend/petsend.py"

echo "Building ClaudePet..."
"$PYTHON" -m PyInstaller \
    --noconfirm \
    --onedir \
    --windowed \
    --name ClaudePet \
    --add-data "$ASSETS:Assets" \
    --paths "$ROOT" \
    --distpath "$ROOT/dist" \
    --workpath "$ROOT/build" \
    --specpath "$ROOT/build" \
    "$ROOT/run_claudepet.py"

# Nest petsend inside the app folder so install_petsend() can find and copy it.
PETSEND_SRC="$ROOT/dist/petsend"
PETSEND_DST="$ROOT/dist/ClaudePet/petsend"
rm -rf "$PETSEND_DST"
cp -r "$PETSEND_SRC" "$PETSEND_DST"

echo
echo "Done. Run: dist/ClaudePet/ClaudePet"
