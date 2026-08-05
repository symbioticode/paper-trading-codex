# POST-REV02 — Bilan des corrections : AVANT vs APRÈS

Date : REV02 traitée et poussée sur GitHub. **Ce document rapporte les
résultats du commit `a986c81`** (moteur corrigé, PnL −2 336 USD, calibration
re-faite avec plancher `V_floor`, TD-004 clôturé) — état audité figé sur
`baseline/rev02-audited` (tag `v0-rev02-audited`).
Source : `docs/rev/REV02.md`. Rôle : enregistrer, de façon synthétique et
compréhensible, ce que la révision a entraîné — pour relire l'historique sans
re-fouiller les commits.

## Correction principale : le PnL était doublé (item 1, bloquant)

| | AVANT | APRÈS |
|---|---|---|
| Formule | `unrealized() = (entry − price) · qty · leverage` — **double levier** (qty est déjà l'exposition pleine, cf. H1) | `(entry − price) · qty` (E10), frais de sortie sur `qty · exit` (E11), funding figé **documenté** (E7) |
| Test | encodait la formule buggée (`100.0 = (100−98)·10·5`) | écrit **depuis H1** ; anti-régression `test_pnl_take_profit_exact` (gross = 20.0) |
| PnL réel publié | **+176 933 USD** (gonflé) | **−2 336 USD** (3 256 trades, equity finale 7 663.28, capital 10 000) |

La stratégie SHORT grille perd sur le jeu réel : +176 933 → −2 336 USD.

## Censure V7 (item 2) : un compteur mentait

| | AVANT | APRÈS |
|---|---|---|
| Compteur | `n_censored` additionnait (a) les trades **résolus** hors fenêtres de test et (b) la vraie censure — qui n'était **pas du tout comptée** | `n_open_at_end` = positions encore **ouvertes** en fin de run (vraie censure W3/V7, jamais au dénominateur) ; `n_hors_fenetres` = trades résolus dont la fenêtre d'ouverture ∉ wid_set |
| Test | — | `test_validate_thesis_w3v7_censure_positions_ouvertes` écrit **depuis le texte** W3/V7 |

## Précisions (items 3–5)

- **Funding** : « notionnel courant » documenté, figé implémenté → le choix figé est désormais une **ASSUME déclarée**.
- **Frais de sortie** : corrigés sur `qty · exit_price · taker_fee`.
- **Resize (item 5)** : **à REJETER** — R5 documentait déjà « skip uniquement si qty nulle » ; comportement conforme, non corrigé.

## Dettes (item 6)

- **TD-001** (PnL) : **CORRIGÉ**.
- **TD-002** (reproductibilité : `run_reproducible.sh` / `MANIFEST` / `flake.nix` absents du repo) : **OUVERT** — condition : avant publication externe.
- **TD-003** (censure) : **CORRIGÉ**.
- **TD-004** (re-calibration du test H4) : **CORRIGÉ** — voir ci-dessous.

## Conséquence majeure : la calibration H4 publiée était invalide

La calibration REV1 (« global 0/20, buckets 4/60, PASS global ≈ 80 % ») avait été
mesurée sur le moteur **buggé** : le PnL gonflé gardait la grille solvable, donc
aucun skip cash (R5). Avec le moteur corrigé, re-mesure sur **capital abondant**
(1 000 000 USD — H4 mesure la géométrie L/s, pas la solvabilité ; sur GBM à
dérive positive la grille SHORT saigne, le skip cash tronquait l'échantillon) :

| Mesure | AVANT (REV1, publié) | APRÈS (REV2, re-mesuré) |
|---|---|---|
| Global | 0/20 rejets (100 % pass) | **5/20** (25 % pass) — sur-rejet |
| Buckets | 4/60 | **3/60** (5 % = nominal) |

Deux causes de la sur-rejection globale identifiées :
1. **Contamination de portefeuille** — la grille SHORT saigne sur GBM à dérive
   positive (prix ×400 à 30 000 h) ; R5 (skip cash / cap notional) tronque
   l'échantillon.
2. **Pathologie `V_rob` (TD-004)** — quand 2–3 fenêtres d'un bucket ont des
   fréquences quasi identiques, `V_rob ≈ 0` et toute dérive rejette (ex. seed 0,
   bucket vol 1 : `p̂=0.1527` vs `P̂=0.1207`, margin = 0.0011 contre un bruit
   binomial ~0.024 par fenêtre).

## TD-004 — corrigé (plancher `V_floor`) et re-calibration publiée

Diagnostic établi : au contrôle 10 000 h / capital 1 M, le **global passe 10/10**
(calibré) et **tous** les échecs (5 seeds / 10) sont des **buckets** dont la
dispersion inter-fenêtres s'effondre quand les `p̂_w` coïncident.

**Correctif implémenté** dans `cluster_robust_test` (thesis.py) : **plancher
binomial intra-fenêtre**
`V_floor = Σ_w (n_w/N)²·p̂_w(1−p̂_w)/(n_w−1)`, variance testée =
`max(V_rob, V_floor)`. Tests de non-régression ajoutés
(`test_cluster_robust_plancher_binomial_pas_d_effondrement`,
`test_cluster_robust_plancher_ne_desarme_pas_la_puissance`).

**Calibration re-mesurée (contrôle non contaminé, capital 1 M, skips=0) :**

| Config | Résultat |
|---|---|
| 5 000 h, 20 seeds | **20/20 PASS** (global 20/20 ; buckets non testables, 3 fenêtres) |
| 10 000 h, 10 seeds | **9/10 PASS** — global **10/10**, buckets **29/30** (≈ nominal) |
| 30 000 h, 20 seeds | global **20/20**, buckets 57/59 ; PASS 5/20 — les 15 échecs sont UNIQUEMENT la condition V6 « aucun skip » (contamination portefeuille) |

Avant le correctif, le contrôle 10 000 h échouait 5/10 (pathologie `V_rob`) ;
après, 1/10 (un rejet ≈ 5 % nominal). Le **réel est inchangé : FAIL bucket
vol 1** (`p̂=0.0845` vs `P̂=0.1245`, ±0.0200) — déviation **réelle** du modèle
(~32 % de sous-prédiction en vol moyenne), pas un artefact du test : le
correctif ne masque pas une erreur de modèle.

**Point de vigilance documenté** : à W=2 le facteur t(1)≈12.7 rend le bucket
quasi non-testable (marge ~12.7·SE) ; c'est le prix honnête de l'absence
d'information inter-fenêtres — le global (W=8+) porte la puissance. C'est le
compromis retenu face au `z` (plancher binomial pur), qui aurait re-introduit
la sur-rejection mesurée du Wilson (corrélation intra-fenêtre non corrigée).

**Clôture** : TD-004 marqué CORRIGÉ dans LIMITATIONS.md §5 ; calibration
republiée dans HYPOTHESIS §H4, METHODS §5.2/§7, THESIS, codex/06.
