# POST-REV02 — Bilan des corrections : AVANT vs APRÈS

Date : REV02 traitée et poussée sur GitHub (main, jusqu'au commit `c0282ba`).
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
- **TD-004** (re-calibration du test H4) : **OUVERT** — voir ci-dessous.

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

## TD-004 — état de l'investigation (OUVERT, en cours)

Diagnostic établi : au contrôle 10 000 h / capital 1 M, le **global passe 10/10**
(calibré) et **tous** les échecs (5 seeds / 10) sont des **buckets** dont la
dispersion inter-fenêtres s'effondre quand les `p̂_w` coïncident.

Correctif en cours : **plancher binomial intra-fenêtre**
`V_floor = Σ_w (n_w/N)²·p̂_w(1−p̂_w)/(n_w−1)`, variance testée =
`max(V_rob, V_floor)`. Mesuré : 30 buckets → 29/30 rejetés comme avant, le
pathologique passe (4/5 flips), 1 rejet restant ≈ taux nominal 5 %.

Point de vigilance non tranché : à W=2 le facteur t(1)≈12.7 rend le bucket quasi
aveugle (marge ~0.21 pour un écart réel ~0.03) — comparaison en cours entre
`t(W−1)` sur le plancher (conservateur) et un `z` sur la composante
intra-fenêtre bien estimée (plus puissant). Validation finale : re-mesure de la
calibration sur le contrôle GBM non contaminé, puis publication (docs codex/06,
HYPOTHESIS §H4, METHODS, THESIS) et clôture de TD-004.
