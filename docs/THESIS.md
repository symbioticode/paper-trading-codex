# THESIS.md — La thèse : énoncé, fondements, traduction en code, robustesse

> Ce document est **exhaustif** : il répond à quatre questions.
> 1. Qu'affirme exactement la thèse ?
> 2. Sur quoi se base-t-elle (référence académique, retour d'expérience, normes
>    quantitatives) ?
> 3. Comment a-t-elle été traduite en code, et avec quelles attentes ?
> 4. Pourquoi est-ce une approche robuste ?
>
> Le document normatif (définitions, critères d'échec) reste `HYPOTHESIS.md`.
> Ici, chaque affirmation est reliée à un module, un test et une référence.

---

## 1. L'énoncé exact de la thèse

Ce projet étudie une stratégie **grid SHORT** sur un perpétuel crypto
(Binance SOLUSDT), et n'affirme **rien** sur la prédictibilité des marchés.
La thèse porte sur la **gestion du risque mesurable** :

> **T.** Pour un grid SHORT avec levier `L`, espacement de grille `s` (=
> distance take-profit), et des barrières de liquidation dérivées du spec
> exchange (H1), la probabilité qu'une position soit liquidée avant son
> take-profit est **calculable** à partir de la volatilité `σ` et de la dérive
> `μ` du log-prix (H2). Le plafond de levier sûr pour un budget de risque `α`
> en découle (H3), et la relation **prédiction → fréquence observée** est
> mesurable hors-échantillon sur des fenêtres indépendantes (H4). Tout le
> raisonnement est exprimé en USD de façon cohérente (H5).

Autrement dit : la thèse est **falsifiable en quatre maillons** —

| # | Énoncé | Se réfute par |
|---|---|---|
| H1 | Le prix de liquidation SHORT découle du spec : `liq = E·(1+1/L)/(1+MMR)`. | Algèbre + tests de cohérence. |
| H2 | Sous GBM, la probabilité de liquidation avant TP a une forme fermée exacte. | Monte Carlo continu (5σ). |
| H3 | `L*(α) = max{L : P(liq) ≤ α}` existe et est monotone. | Grille de paramètres. |
| H4 | La fréquence de liquidation observée hors-échantillon est compatible avec la prédiction, globalement et par régime de volatilité. | Wald cluster-robuste calibré. |
| H5 | PnL et ratios sont en USD, sans double comptage. | Invariance à 1e-9. |

**Ce que la thèse n'affirme pas :** que le bot est rentable, que le levier est
"sûr" en absolu, que le GBM décrit les marchés. La rentabilité est un constat
mesuré, séparé de la thèse (voir LIMITATIONS.md §3).

---

## 2. Sur quoi la thèse se base

### 2.1 Références académiques

| Élément | Référence | Usage dans le code |
|---|---|---|
| Formule de liquidation en marge isolée | Spec Binance USDT-M (docs « Risk limits ») ; équation de solde de marge | `src/market/exchange_spec.py` (H1) |
| Probabilité de premier passage à deux barrières du mouvement brownien arithmétique | Karlin & Taylor, *A First Course in Stochastic Processes* (1975), ch. 7 ; Borodin & Salminen, *Handbook of Brownian Motion — Facts and Formulae* (2002) | `src/risk/two_barriers.py` (H2) |
| Estimation μ̂, σ̂ et leurs IC | Théorème central limite, distribution de Student pour la moyenne, chi-2 pour la variance | `src/risk/moments.py` (M1–M3) |
| Intervalle de Wilson | Wilson, *Probable inference, the law of succession, and statistical inference* (1927) | `src/risk/moments.py` (M4) — **utilitaire** ; le test H4 n'utilise PAS Wilson (voir §2.3 et METHODS.md §5) |
| Extrêmes intra-barre / pont brownien | Parkinson, *The Extreme Value Method* (1980) ; Garman & Klass (1980) | `src/risk/monte_carlo.py` (barre OHLC simulée) |
| Erreurs types robustes aux clusters | Cameron & Miller, *A Practitioner's Guide to Cluster-Robust Inference* (2015) ; Liang & Zeger (1986) | `src/validation/thesis.py` (V5) |
| Validation hors-échantillon / walk-forward | Bailey, Borwein, López de Prado & Zhu, *Pseudo-Mathematics and Financial Charlatanism* (2014) | `src/validation/windows.py`, `scripts/04_validate_thesis.py` (W1–W3) |
| Falsifiabilité | Popper, *The Logic of Scientific Discovery* (1959) | `docs/HYPOTHESIS.md` §3 (critères d'échec) |

### 2.2 Retour d'expérience (pourquoi les corrections de J6 existent)

Les trois corrections de mesure les plus coûteuses du projet ne sont pas des
choix académiques : elles répondent à des **biais observés** pendant la
construction, à la manière d'un retour d'expérience de backtest.

1. **Overshoot d'entrée (exécution au niveau).** Une première version exécutait
   l'ordre au niveau de grille `L_i` (touché par le `high`). Or le prix qui
   "touche" un niveau puis redescend est déjà **plus bas** au moment où un ordre
   marché s'exécute réellement : l'entrée effective était systématiquement en
   dessous du niveau, faussant la distance à la liquidation. Correction (G3) :
   exécution **au close** de la barre déclenchante — entrée = prix courant, H2
   s'applique exactement depuis l'entrée. C'est la convention la plus importante
   de la stratégie, et elle est testée (correction documentée dans METHODS.md §4).
2. **Dépendance intra-fenêtre.** Le test binomial naïf (Wilson) supposait les
   positions indépendantes. Or les positions d'une même fenêtre de test partagent
   **le même chemin de prix** : leurs issues sont corrélées, et le test naïf
   sur-réjetait (mesuré : buckets rejetés dans ~11/20 seeds au lieu de ~5 %).
   Correction (V5) : Wald cluster-robuste, cluster = fenêtre. Voir METHODS.md §5.
3. **Granularité du monitoring.** Le moteur surveille les barrières barre à
   barre (OHLC horaire), pas en temps continu : la formule continue H2
   sous-estime le risque de liquidation mesuré. Correction (V3) : la prédiction
   H4 est le Monte Carlo **discret** aux sémantiques du moteur. Voir METHODS.md §4.
4. **Slippage de sortie TP (REV1, revue externe).** E8 documentait
   « sortie = prix cible·(1 + slip) » mais le moteur fermait le TP exactement au
   prix cible, sans appliquer `slip_bps` : le PnL net réalisé de chaque TP était
   systématiquement surestimé dès que `slip_bps > 0`. Découvert par revue
   externe (docs/rev/REV01.md), corrigé dans `engine.py` et verrouillé par
   `tests/test_engine.py::test_slippage_sortie_tp`. Aucun impact sur les
   résultats mesurés (runs à `slip_bps = 0`), mais la convention est désormais
   conforme au code et testée.

### 2.3 Normes quantitatives appliquées

- **Tout énoncé est (a) définition, (b) hypothèse testable, ou (c) constat
  mesuré.** Rien d'autre n'entre dans le README ou les leçons
  (HYPOTHESIS.md §1).
- **Chaque hypothèse pointe vers un test qui peut échouer**, avec critère
  d'échec explicite (HYPOTHESIS.md §3).
- **Calibration du test sur un contrôle où le modèle est vrai par
  construction.** Un test statistique qui se trompe ne peut pas être détecté
  par lui-même : on mesure donc son taux de faux rejets sur le contrôle GBM
  avant de l'appliquer aux données réelles (METHODS.md §5). C'est la norme qui
  justifie le PASS ≈ 80 % (4 tests indépendants à 95 %, 0.95⁴ ≈ 0.81).
- **Une hypothèse réfutée est un résultat publié**, pas un bug (H4).
- **Provenance de toute donnée** : sha256, source, intervalle, paramètres
  (`data/data_loader.py`), données synthétiques étiquetées `synthetic` et
  jamais présentées comme historique (`data/synthetic_gbm.py`).
- **Aucune valeur muette** : toute constante (frais, MMR, slippage) a un
  statut OBSERVE/ASSUME/INFER et une cible de vérification
  (`exchange_spec.py`, conventions E1–E9, G1–G7, R1–R5, W1–W3, T1–T5).

---

## 3. Traduction en code — module par module, avec attentes

Chaque ligne de code porte une attente chiffrée. Le tableau ci-dessous relie
chaque maillon de la thèse à son implémentation, son test et la valeur
attendue.

### H1 — Liquidation dérivée du spec → `src/market/exchange_spec.py`

| Implémentation | `liquidation_price_short`, `liquidation_distance_short`, `mmr_for_notional` |
|---|---|
| Test | `tests/test_exchange_spec.py`, `tests/test_liquidation.py` |
| Attente | `liq = E·(1+1/L)/(1+MMR)` exact ; cas limites exacts (`L→∞` → liq=E figé car `1/L<MMR`, `MMR→0` → `E·(1+1/L)`, `L→1` → `≈2E`) ; monotonie en L et MMR. |
| Critère d'échec | toute propriété algébrique contredite. |

### H2 — Formule exacte → `src/risk/two_barriers.py` + `src/risk/monte_carlo.py`

| Implémentation | `_prob_from_ab` (forme `expm1` numériquement stable), `prob_liquidation_short`, `simulate_two_barrier` |
|---|---|
| Test | `tests/test_two_barrier.py`, `tests/test_ground_truth.py`, `scripts/03_ground_truth.py` |
| Attente | Monte Carlo continu à N=10 000 : `|p̂ − P| ≤ 5·√(P(1−P)/N)` ; cas limites exacts (`μ→0 ⇒ a/(a+b)`, `b→0 ⇒ P→1`, `a→0 ⇒ P→0`). |
| Critère d'échec | écart hors 5σ → la formule ou sa programmation est fausse. C'est l'**ancre anti-contradiction** du projet. |

### H3 — Plafond de levier → `src/risk/two_barriers.py`

| Implémentation | `max_leverage_for_alpha` (dichotomie) |
|---|---|
| Test | `tests/test_two_barrier.py` |
| Attente | `L*` croît en `|μ|` quand `μ<0`, décroît en `σ` pour `μ≤0`, croît en `σ` pour `μ>0` ; `L*=∅` si `α` impossible. |
| Critère d'échec | toute non-monotonie dans le domaine valide (`1/L > MMR`, `s>0`). |

### H4 — Prédiction hors-échantillon → `src/validation/*` + simulateur

| Implémentation | `windows.py` (W1–W3), `thesis.py` (V1–V7), `grid_short.py` (G1–G7), `runner.py` (R1–R5), `monte_carlo.py::simulate_two_barrier_bars` (V3), `moments.py` (M1) |
|---|---|
| Test | `tests/test_windows.py`, `tests/test_thesis.py`, `scripts/04_validate_thesis.py` |
| Attente (contrôle GBM, modèle vrai par construction) | **PASS** : global et tous les buckets non vides acceptés au Wald cluster-robuste 95 %, zéro skip cash/cap. Valeurs mesurées (seed 60) : global `p̂=0.1245` vs `P̂=0.1206` (±0.014). |
| Attente (données réelles) | Le test falsifiable : **PASS** si la relation prédiction↔observation survit. Mesuré : global `p̂=0.110` vs `P̂=0.124` (±0.023) ; buckets vol `0.112/0.084/0.124` vs `0.112/0.125/0.128`. |
| Critère d'échec | fréquence observée hors marge cluster-robuste → la thèse est **réfutée** sur ce régime, résultat publié. |

### H5 — Cohérence du numéraire → `src/simulator/engine.py`

| Implémentation | `SimulationEngine` (E1–E9), `_close`, `_liquidate` |
|---|---|
| Test | `tests/test_engine.py`, `tests/test_metrics.py`, `tests/test_runner.py` |
| Attente | PnL cumulé USD identique (à 1e-9) entre comptabilisation barre à barre et fermeture en une étape ; frais d'entrée débités une seule fois ; funding net appliqué au SHORT (rate>0 ⇒ shorts reçoivent) ; slippage (E8) appliqué à l'entrée **et** à la sortie TP, liquidation non affectée. |
| Critère d'échec | désaccord de PnL → bug. |

---

## 4. Pourquoi l'approche est robuste

### 4.1 La structure est hiérarchique et chaque maillon est ancré

H1 → H2 → H3 → H4 est une chaîne : H2 ne peut pas être cru si H1 est faux
(les barrières ne seraient pas celles du spec), H4 n'a de sens que si H2 est
vrai sous le modèle. La chaîne est protégée par **deux ancres indépendantes** :
- `scripts/03_ground_truth.py` (H2) vérifie la formule contre un Monte Carlo
  du processus continu — la formule est **exacte**, pas une approximation ;
- `scripts/04_validate_thesis.py --data gbm` vérifie la **machinerie entière**
  (estimation → prédiction discrète → simulateur → test) sur un jeu où le
  modèle est vrai par construction. Si la validation échoue sur le contrôle,
  c'est la machinerie qui est en cause, pas le marché.

### 4.2 Le test est calibré, pas ad hoc

La décision la plus risquée du projet est statistique : comment comparer une
prédiction de probabilité à une fréquence observée quand les observations ne
sont pas indépendantes ? Au lieu de choisir un test « classique » (Wilson) et
de le croire, on a **mesuré son défaut sur le contrôle** (sur-rejet ~11/20 au
lieu de ~5 %), puis **construit** le test cluster-robuste, puis **re-mesuré sa
calibration** (global 0/20, buckets 4/60 ⇒ PASS global ≈ 0.95⁴). La norme est
explicite : on ne croit un test que s'il se comporte à son niveau nominal quand
le modèle est vrai.

### 4.3 Les biais de mesure sont quantifiés et corrigés, pas supposés

Overshoot d'entrée, granularité du monitoring, dépendance intra-fenêtre : les
trois corrections de J6 ont été découvertes par mesure, documentées avec leur
ampleur, et corrigées dans le code de façon **testable**. Aucune n'est une
« assomption de confort » non vérifiée.

### 4.4 Les conventions rendent le comportement reproductible

La stratégie est **pure et déterministe** (G1–G7) : `on_bar` ne dépend que de
la séquence de barres. Le runner applique toute la policy d'exécution (R1–R5),
dont le **resize** qui élimine le biais de sélection par capital (aucune
position écartée pour cash/cap — la thèse porte sur la fréquence de
liquidation, pas sur un échantillon biaisé par la solvabilité). Les données
ont une provenance sha256, les seeds sont épinglés, les versions des
dépendances sont bornées (pyproject.toml).

### 4.5 Les limites sont publiées avec les résultats

Robustesse ≠ perfection : `LIMITATIONS.md` liste les assomptions (GBM,
granularité intra-barre des données réelles, MMR, frais, slippage, funding
index) avec leur cible de vérification. La thèse survit *sur les fenêtres
testées et sous ces assomptions* — rien de plus, et c'est dit.

---

## 5. Synthèse : le contrat de la thèse

```
SI  H1 (liq du spec)  ET  H2 (formule exacte sous GBM)  ET  H3 (L* dérivé)
ET  le contrôle GBM (modèle vrai) passe la validation complète (calibrée)
ALORS  un échec de H4 sur les données réelles est un RÉSULTAT :
       la relation prédiction↔observation ne survit pas à ce régime.
```

Un PASS ne « prouve » pas la rentabilité ni la sûreté d'un levier : il prouve
que, sur ces fenêtres et sous ces assomptions, **la fréquence de liquidation
est prévisible à la précision annoncée**. C'est tout ce que la thèse prétend,
et c'est suffisant pour prendre une décision de dimensionnement en
connaissance de cause.
