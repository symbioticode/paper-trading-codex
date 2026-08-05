# STATUS.md — chiffres canoniques du dépôt (source unique)

> Document **canonique** (REV03 §1) : les compteurs et résultats publiés ci-dessous
> sont la référence. Les autres documents y renvoient par lien au lieu de dupliquer
> le chiffre. La section « Tests unitaires » est **régénérée automatiquement** par
> `python scripts/update_status.py` (sortie réelle de pytest, pas recopiée) ; les
> résultats audités sont figés (REV02/REV03).

## Tests unitaires

- **Nombre de tests : 103** (11 fichiers `tests/test_*.py`), compté par `pytest --collect-only -q` (sortie réelle, pas recopiée).
- **Résultat réel capturé** (`python -m pytest tests/ -q`) : **exit 0** — tous les tests passent.
- Les 11 fichiers : `test_data_loader` (16), `test_engine` (14), `test_exchange_spec` (13), `test_funding_align` (2), `test_grid_short` (9), `test_moments` (7), `test_runner` (7), `test_synthetic_gbm` (6), `test_thesis` (8), `test_two_barrier` (17), `test_windows` (4).
- **Régénération automatique** : `python scripts/update_status.py` ; `python scripts/update_status.py --check` échoue si ce fichier n'est pas à jour. garde-fou MANUEL pour l'instant (pas de CI) — TD-005, cible de vérification datée dans docs/LIMITATIONS.md §5.

## Résultats audités publiés (REV02/REV03 — figés sur `baseline/rev02-audited`)

| Résultat | Valeur |
|---|---|
| PnL réel constaté (hors thèse) | **−2 336 USD** / 3 256 trades (capital 10 000, equity finale 7 663 USD) |
| H4 contrôle GBM (seed 60, 30 000 h) | **PASS** — global `p̂=0.1245` vs `P̂=0.1206` (±0.0144) |
| H4 données réelles (51 594 barres) | **FAIL (réfuté)** — global `p̂=0.1100` vs `P̂=0.1236` (±0.0149) OK ; bucket vol 1 `p̂=0.0845` vs `P̂=0.1245` (±0.0200) HORS |
| Calibration test H4 (REV2, contrôle non contaminé) | 5 000 h → 20/20 PASS ; 10 000 h → global 10/10, buckets 29/30 ; 30 000 h → global 20/20 (FAIL = V6 « aucun skip ») |

## Régénération

Toute sortie est régénérable via `source activate.sh` + les scripts 03/04
(`scripts/03_ground_truth.py`, `scripts/04_validate_thesis.py`) ; les données
réelles portent une provenance sha256 (`data/data_loader.py`). Le détail des
limites et de la dette (TD-001…TD-005) est dans `docs/LIMITATIONS.md`.
