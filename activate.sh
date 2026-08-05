#!/usr/bin/env bash
# ============================================================================
# activate.sh — Active l'environnement sol-grid-lab
# ============================================================================
# Le venv est construit sur un Python NixOS ; les extensions C (numpy, pandas)
# ont besoin des librairies dynamiques du store Nix au runtime.
# Ce script assemble LD_LIBRARY_PATH puis source le venv.
#
# Usage :  source activate.sh
# ============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NIX_LIBS=(
  "/nix/store/7vafhlh0lmcvi75jfyy09qwr4m3x1ks3-gcc-15.2.0-lib/lib"   # libstdc++
  "/nix/store/ljvfprd5yw4xvj4iw2kvmmaa5xxs6vq6-zlib-ng-2.2.4/lib"    # libz
  "/nix/store/0niqm9mvpf0yrlpicgqi9bdvknykidqg-ld-library-path/share/nix-ld/lib"  # bundle standard
  "/nix/store/8shigvs0alcz29qy763lx5xwg17ls0kz-lz4-1.10.0-lib/lib"   # liblz4
)

LD_LIBRARY_PATH=""
for d in "${NIX_LIBS[@]}"; do
  if [ -d "$d" ]; then
    LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+${LD_LIBRARY_PATH}:}${d}"
  fi
done
export LD_LIBRARY_PATH

if [ ! -x "$PROJECT_DIR/.venv/bin/python" ]; then
  echo "[activate] venv introuvable, création..." >&2
  python3 -m venv "$PROJECT_DIR/.venv"
  "$PROJECT_DIR/.venv/bin/pip" install --upgrade pip
  "$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
fi

# shellcheck disable=SC1091
source "$PROJECT_DIR/.venv/bin/activate"

echo "[activate] sol-grid-lab — Python $(python --version 2>&1 | sed 's/Python //')"
python -c "import pandas, numpy; print(f'[activate] pandas {pandas.__version__} | numpy {numpy.__version__}')" 2>/dev/null || \
  echo "[activate] ATTENTION : pandas/numpy ne s'importent pas — vérifier LD_LIBRARY_PATH."
