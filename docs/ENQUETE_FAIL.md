# ENQUÊTE_FAIL.md — Mécanisme du FAIL H4 (bucket vol 1)

> **Question** : pourquoi la fréquence réelle de liquidation est-elle
> significativement INFÉRIEURE à la prédiction dans le bucket de volatilité
> médiane (`p̂=0.0845` vs `P̂=0.1245`, écart 0.040, tolérance ±0.0196) ?
> **Fichiers** : `scripts/05_diagnose_fail.py`, `06_diagnose_mechanism.py`,
> `07_diagnose_synthetic.py`, `08_diagnose_distribution.py` ;
> `src/validation/thesis.py` (fix fenêtres n=0).
> **Statut** : mécanisme identifié et chiffré — « exhaustion » post-trigger.

## Contexte

Le FAIL est publié dans `README.md`, `docs/HYPOTHESIS.md`, `docs/THESIS.md`,
`docs/METHODS.md` §7 et `docs/codex/07-validation-hors-echantillon.md`
(commit `c4b379c`). Cette page documente l'enquête MÉCANISTE menée ensuite
pour expliquer le résidu, avec des scripts de diagnostic qui NE MODIFIENT PAS
le contrat H1–H5.

Rappel du chiffre publié : global `p̂=0.1100` vs `P̂=0.1236` (±0.0149) OK ;
bucket vol 1 `p̂=0.0845` vs `P̂=0.1245` (±0.0196) **HORS** ; buckets 0/2 OK.
Contrôle GBM PASS, `03_ground_truth.py` PASS, 100 tests.

## Méthode

1. **Décomposition par fenêtre** (05) : pour chaque fenêtre de test, `σ̂_train`,
   `σ̂_test`, `μ̂_train`, `μ̂_test`, `n`, `k`, `p̂_w`, `P̂_w`. Résidu
   `(p̂_w − P̂_w)` fortement négatif concentré sur les fenêtres 26
   (2023-11→2024-01, pump SOL), 28 (2024-02→03), 33 (2024-09→10), 39
   (2025-05→06).
2. **Contrôle du régime** (06) : P(liq) re-calculée avec les moments RÉALISÉS
   de la fenêtre de test (D2) — divise par deux l'écart du bucket 1
   (0.040→0.022) — puis avec les moments VÉCUS de chaque position
   (`σ̂_life`, `μ̂_life`) — reste 0.0175 d'écart. Sur le contrôle GBM, la même
   méthode est saine (P(σ̂_life) ≈ p̂).
3. **Distribution marginale** (08) : à (μ, σ) identiques, barres empiriques
   réelles vs barres gaussiennes du pont brownien → `P_emp ≈ P_gauss`
   (0.1097 vs 0.1090 à σ=0.0127). Les queues épaisses seules n'expliquent pas.
4. **Test décisif — mêmes entrées** : pour chaque position RÉELLE des fenêtres
   problématiques, on rejoue le chemin AVANT à partir du même prix d'entrée,
   avec les mêmes barrières (−2% / +19.4%) :
   - barres réelles : `P(liq)=0.0875` (win 26), `0.0870` (win 28) ;
   - pont brownien à (μ̂_train, σ̂_train) : `0.2250` (win 26), `0.1725` (win 28).
   → L'écart n'est NI la sélection des entrées NI les moments : il est dans la
   STRUCTURE du chemin avant, conditionné à l'entrée.

## Hypothèses écartées (avec chiffres)

| Hypothèse | Test | Verdict |
|---|---|---|
| Queues épaisses / distribution marginale | 08 : P_emp vs P_gauss à (μ,σ) identiques | Écartée (`0.1097 ≈ 0.1090`) |
| Autocorrélation (mémoire) | AC(1h)=−0.019, AC(2h)=−0.018, AC(24h)=−0.020 | Écartée (≈ nulle) |
| Artefact de fenêtres vides (n=0) | fix `cluster_robust_test` | Écarté (100 tests OK, résultat inchangé) |
| Moments train ≠ réalisés | D2 : moments de la fenêtre de test | Partiel (0.040→0.022), ne suffit pas |
| Moments vécus σ̂_life ≠ σ̂_train | 06 | Écarté (médiane σ̂_life/σ̂_train ≈ 1.000) |
| Sélection des entrées | rejeu des MÊMES entrées | Écarté (l'écart persiste à entrées identiques) |
| Non-stationnarité des moments avant | moments avant RÉALISÉS des entrées | Écarté : μ_fwd ≥ μ_train et σ_fwd/σ_train = 1.25-1.30 (win 26/28) → la correction empirique AUGMENTERAIT la prédiction |

## Le mécanisme identifié : exhaustion après trigger (G3)

La stratégie entre en SHORT à la clôture de toute barre dont le **high** croise
l'ancre +2 % (G3). Ces barres sont des spikes de momentum. Or, conditionnel à
ces barres, le marché réel montre une **exhaustion systématique** :

| Statistique (depuis le close d'entrée) | Réel | Pont brownien (modèle) |
|---|---|---|
| P(min low 6h ≤ −2 % TP) | **56 %** | ~n.d. |
| P(min low 24h ≤ −2 % TP) | **76 %** | 65 % |
| P(max high 24h ≥ +19.4 % liq) | 7 % | ~1-2 % |
| Low moyen de la barre suivante | **−1.15 % à −1.55 %** (= 60-77 % de la distance TP) | ~−0.7 % (−0.65σ) |
| P(liq) à VIE (mêmes entrées, win 26) | **0.0875** | **0.2250** |

Lecture : après une barre +2 %, la barre suivante plonge en moyenne de
1.15–1.55 % — les trois quarts du chemin vers le TP −2 % en UNE barre.
L'absorption au TP est donc très rapide : 56 % des positions sont fermées en
moins de 6 h, 76 % en 24 h. Dans le modèle, les barres post-entrée ne plongent
que de ~0.65σ (~0.7 %) : l'absorption au TP est ~2× plus lente, et les
survivants (qui dans les fenêtres de pump ont un drift positif μ̂>0) dérivent
vers la barrière lointaine +19.4 % sur plusieurs jours → P(liq) à vie gonflée.

## Pourquoi le bucket 1 précisément

Le FAIL est porté par les fenêtres de pump à vol médiane (26, 28 : SOL
$50→$120), où le drift positif maximalise l'écart modèle/réel : le modèle
« continue le momentum » (μ>0 → liq), la réalité « épuise le momentum »
(trigger → pullback → TP). En bucket 0 (vol bas) l'effet est faible, en bucket 2
(vol haut) le bruit domine déjà la prédiction : la tolérance du test n'est pas
dépassée.

## Conclusion pour la thèse

Le modèle de passage à deux barrières est exact pour des entrées aléatoires
(contrôle GBM : la méthode est saine, `P(σ̂_life) ≈ p̂`). Le FAIL vient du fait
que **l'entrée de la stratégie est conditionnée à un événement qui n'est pas
Markovien** dans les barres réelles : le franchissement du high à +2 % est
suivi d'un pullback d'exhaustion qui absorbe la position au TP proche avant
toute dérive vers la liquidation. Le modèle iid-GBM-avec-pont n'a pas cette
structure conditionnelle : `E[low de la barre suivante | trigger] ≪ 0`.

Ce n'est pas une erreur de code, ni un biais d'estimation : c'est une propriété
de structure du marché que le modèle ne représente pas. Limite documentée à
ajouter à `docs/LIMITATIONS.md` (biais de sélection d'entrée de la stratégie G3
non capturé par le modèle de premier passage).

## Reproduire

```bash
python scripts/05_diagnose_fail.py        # matrice fenêtres/buckets, D1-D4
python scripts/06_diagnose_mechanism.py   # D2/D3 + test positions (σ̂_life)
python scripts/07_diagnose_synthetic.py   # contrôle synthétique (sémantique en cours d'affinage)
python scripts/08_diagnose_distribution.py# P(liq) barres gaussiennes vs empiriques
```

Le rejeu « mêmes entrées » (tableau ci-dessus) est reproduit dans
`06_diagnose_mechanism.py` (test décisif).
