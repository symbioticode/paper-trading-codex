{ pkgs ? import <nixpkgs> {} }:

let
  pythonEnv = pkgs.python312.withPackages (ps: with ps; [
    # Core scientifique (le code de la thèse)
    numpy
    pandas
    scipy
    matplotlib
    pyyaml
    requests
    pytest

    # Dépendances transitives utiles (dates, fuseaux)
    python-dateutil
    pytz
  ]);
in
pkgs.mkShell {
  buildInputs = [
    pythonEnv
    pkgs.gcc              # Compilateur pour packages natifs
    pkgs.pkg-config       # Pour trouver les bibliothèques
    pkgs.gcc-unwrapped.lib  # libstdc++/libgcc runtime

    # Dépendances C runtime des wheels (numpy/pandas/scipy)
    pkgs.stdenv.cc.cc.lib
    pkgs.zlib
    pkgs.openssl
    pkgs.libffi
    pkgs.lz4
  ];

  shellHook = ''
    echo "🛠  Initialisation de l'environnement sol-grid-lab (Nix)..."

    # ===================================================================
    # 1. CONFIGURATION DES CHEMINS DE BIBLIOTHÈQUES C
    # ===================================================================
    export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib:${pkgs.lz4}/lib:${pkgs.openssl.out}/lib:${pkgs.libffi}/lib:${pkgs.gcc-unwrapped.lib}/lib:$LD_LIBRARY_PATH"
    export PKG_CONFIG_PATH="${pkgs.openssl.dev}/lib/pkgconfig:${pkgs.zlib}/lib/pkgconfig:$PKG_CONFIG_PATH"

    # ===================================================================
    # 2. CRÉATION D'UN ENVIRONNEMENT VIRTUEL LOCAL (PIP)
    # ===================================================================
    VENV_DIR=".venv"

    if [ ! -d "$VENV_DIR" ]; then
      echo "📦 Création de l'environnement virtuel Python..."
      python -m venv "$VENV_DIR"
    fi

    source "$VENV_DIR/bin/activate"

    # ===================================================================
    # 3. INSTALLATION / SYNCHRONISATION DES DÉPENDANCES
    # ===================================================================
    if [ -f requirements.txt ]; then
      pip install --upgrade pip setuptools wheel --quiet
      echo "📦 Synchronisation des dépendances (requirements.txt)..."
      pip install -r requirements.txt --quiet
    fi

    # ===================================================================
    # 4. VÉRIFICATIONS
    # ===================================================================
    echo ""
    echo "✅ Environnement sol-grid-lab prêt!"
    echo "🐍 Python: $(python --version)"

    python -c "import numpy; print('   ✓ numpy:', numpy.__version__)" 2>/dev/null || echo "   ✗ numpy manquant"
    python -c "import pandas; print('   ✓ pandas:', pandas.__version__)" 2>/dev/null || echo "   ✗ pandas manquant"
    python -c "import scipy; print('   ✓ scipy:', scipy.__version__)" 2>/dev/null || echo "   ✗ scipy manquant"
    python -c "import matplotlib; print('   ✓ matplotlib:', matplotlib.__version__)" 2>/dev/null || echo "   ✗ matplotlib manquant"
    python -c "import yaml; print('   ✓ PyYAML:', yaml.__version__)" 2>/dev/null || echo "   ✗ PyYAML manquant"
    python -c "import requests; print('   ✓ requests:', requests.__version__)" 2>/dev/null || echo "   ✗ requests manquant"
    python -c "import pytest; print('   ✓ pytest:', pytest.__version__)" 2>/dev/null || echo "   ✗ pytest manquant"

    echo ""
    echo -e "🚀 Lancez les tests avec:\n   python -m pytest tests/ -q"
    echo "   💡 Pour sortir : deactivate"
    echo ""
  '';

  # Variables d'environnement permanentes
  PYTHON_KEYRING_BACKEND = "keyring.backends.null.Keyring";  # Évite les erreurs keyring
}
