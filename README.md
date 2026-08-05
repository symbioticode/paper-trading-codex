# sol-grid-lab

Laboratoire de **grid SHORT** sur perpétuel (Binance SOLUSDT) : une thèse de
risque **falsifiable, reproductible**, testée hors-échantillon sur données
réelles.

> Le document normatif est [`docs/HYPOTHESIS.md`](docs/HYPOTHESIS.md) : toute
> affirmation de ce repo est (a) une définition, (b) une hypothèse testable
> avec critère d'échec explicite, ou (c) un constat mesuré. La documentation
> complète est dans [`docs/`](docs/README.md).

## La thèse en une phrase

La probabilité qu'un SHORT de grille soit liquidé avant son take-profit est
calculable depuis le spec exchange, la volatilité et la dérive (H1–H3), et
cette relation **prédiction → fréquence observée** est mesurable
hors-échantillon avec des intervalles de confiance calibrés (H4), en USD
cohérent (H5).

## Résultats (régénérables)

| Validation | Résultat |
|---|---|
| Contrôle GBM (modèle vrai par construction) | **PASS** — global `p̂=0.1245` vs `P̂=0.1206` (±0.014) |
| Données réelles SOLUSDT perp 1h (51 594 barres) | **FAIL** (réfuté) — global `p̂=0.110` vs `P̂=0.124` OK, mais bucket vol 1 `p̂=0.0845` vs `P̂=0.1245` (±0.020) HORS |
| Tests unitaires | **100 verts** (`python -m pytest tests/ -q`, venv sol-grid-lab) |
| PnL constaté (réel, hors thèse — mesure) | +176 933 USD / 3 256 trades, capital 10 000 |

Un échec de validation est un **résultat publié** (l'hypothèse en défaut,
l'écart, la significativité), pas un bug. Le FAIL réel est publié dans
`docs/HYPOTHESIS.md` §H4 et `docs/THESIS.md` §3/§5 : la thèse H4 est réfutée
sur le régime de volatilité médiane, pas sur le global ni les autres régimes.

## Refuter le projet

```bash
source activate.sh                     # env NixOS (LD_LIBRARY_PATH)
python scripts/03_ground_truth.py      # H2 : formule exacte sous GBM
python scripts/04_validate_thesis.py   # H4 : contrôle GBM (doit PASSER)
python scripts/04_validate_thesis.py --data real   # H4 : données réelles (FAIL connu, bucket vol 1)
python -m pytest tests/ -q             # 100 tests
```

## Références

- [`docs/HYPOTHESIS.md`](docs/HYPOTHESIS.md) — énoncés H1–H5, critères d'échec, corrections J6
- [`docs/THESIS.md`](docs/THESIS.md) — fondements (références académiques, retour d'expérience, normes quantitatives), traduction en code, robustesse
- [`docs/METHODS.md`](docs/METHODS.md) — dérivations complètes et méthodes statistiques
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) — limites déclarées et cibles de vérification
- [`docs/codex/`](docs/codex/README.md) — codex pédagogique 01..07 (une leçon par journée du projet)
