"""Racine de test : garantit que `data` et `src` sont importables depuis
n'importe où. DEDUCE : l'insertion du projet dans sys.path rend les imports
stables quel que soit le cwd de lancement de pytest."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
