# docs/ — Documentation du projet

> Entrée de la documentation. Ce dossier **explique** le projet ; le dossier
> racine pointe ici. Le document normatif des énoncés est `HYPOTHESIS.md` :
> tout ce qui suit en est une lecture justifiée, jamais une affirmation nouvelle.

## Index

| Document | Contenu |
|---|---|
| [`HYPOTHESIS.md`](HYPOTHESIS.md) | **Normatif.** La thèse (H1–H5), leurs énoncés testables, leurs critères d'échec, les corrections de mesure J6, les résultats. À lire en premier. |
| [`THESIS.md`](THESIS.md) | **Exhaustif.** Ce que la thèse affirme exactement, sur quoi elle se base (références académiques, retour d'expérience, normes quantitatives), comment elle est traduite en code avec les attentes de chaque module, et pourquoi l'approche est robuste. |
| [`METHODS.md`](METHODS.md) | **Méthodes.** Dérivations complètes (formule de liquidation H1, formule à deux barrières H2, plafond H3), les deux corrections de mesure de H4 (prédiction discrète, Wald cluster-robuste) et la calibration des tests. |
| [`LIMITATIONS.md`](LIMITATIONS.md) | **Limites déclarées.** Assomptions, inconnues, cibles de vérification et ce que la thèse ne prétend PAS. |
| `producteur-papercodex.md` | Symlink vers le skill Producteur (règles de production : rattachement à une hypothèse, conventions documentées, aucune valeur muette). |

## Comment lire ce projet

1. `HYPOTHESIS.md` — les énoncés et comment les réfuter.
2. `THESIS.md` — le « pourquoi » : fondements et traduction en code.
3. `METHODS.md` — les mathématiques, au niveau nécessaire pour les refaire.
4. `LIMITATIONS.md` — ce qu'il ne faut pas croire au-delà de la preuve.

## Comment réfuter ce projet

```
source activate.sh        # env NixOS (LD_LIBRARY_PATH)
python scripts/03_ground_truth.py      # H2 : formule exacte sous GBM
python scripts/04_validate_thesis.py   # H4 : contrôle GBM (doit PASSER)
python scripts/04_validate_thesis.py --data real   # H4 : données réelles
pytest tests/ -q          # 99 tests : toutes les hypothèses + conventions
```

Tout test qui échoue nomme précisément l'hypothèse (H1…H5) en défaut, l'écart
mesuré et la significativité. Un échec est un **résultat publié**, pas un bug.
