# METHODS.md — Méthodes quantitatives : dérivations complètes

> Ce document contient les mathématiques nécessaires pour **refaire** les
> résultats. Chaque section termine par la référence de code et de test.
> Le document normatif des énoncés est `HYPOTHESIS.md`.

---

## 1. Notations et unités

| Symbole | Définition | Unité |
|---|---|---|
| `E` | Prix d'entrée d'un SHORT | USD |
| `L` | Levier = notionnel / marge isolée | sans |
| `MMR` | Maintenance margin rate (fraction du notionnel) | sans |
| `s` | Espacement de grille = distance TP fractionnaire | sans |
| `d` | Distance de liquidation fractionnaire `(liq−E)/E` | sans |
| `a, b` | Distances logarithmiques `a = −ln(1−s)`, `b = ln(1+d)` | log |
| `μ, σ` | Dérive et vol du log-prix | `[1/t]`, `[1/√t]` |
| `α` | Budget de risque cible (probabilité max de liq) | sans |

**Convention T1** : `μ` et `σ` sont dans la même unité de temps. `P(liq)` ne
dépend que du rapport `μ/σ²`, qui est invariant par changement d'unité.

---

## 2. Intervalle de confiance des moments (M1–M3)

Sur `n` rendements logs `r_i` d'un GBM :

```
μ̂ = mean(r),   σ̂² = (1/(n−1)) Σ (r_i − μ̂)²      (ddof=1, non biaisé pour σ̂²)
IC(μ)  = μ̂ ± t(1−α/2, n−1) · σ̂/√n
IC(σ²) = ( (n−1)σ̂²/χ²_{1−α/2, n−1} , (n−1)σ̂²/χ²_{α/2, n−1} )   → IC(σ) = √(·)
```

**Référence** : TCL pour μ̂, distribution chi-2 pour σ̂² (variance gaussienne).
**Code** : `src/risk/moments.py::estimate_moments`. **Test** : `tests/test_moments.py`.

---

## 3. H1 — Prix de liquidation dérivé du spec

**Dérivation.** En marge isolée, à la liquidation, le solde (marge isolée +
PnL non réalisé) doit égaler la marge de maintenance :

```
marge + PnL_non_réalisé = liq · qty · MMR
E·qty/L + (E − liq)·qty = liq·qty·MMR
```

On simplifie `qty`, on isole `liq` :

```
E/L + E − liq = liq·MMR
E·(1 + 1/L) = liq·(1 + MMR)
liq = E·(1 + 1/L) / (1 + MMR)
```

**Distance de liquidation** : `d = (liq − E)/E = (1/L − MMR)/(1 + MMR)`.

**Cas limites (DEDUCE, testés).**
- `MMR → 0` : `liq → E·(1 + 1/L)` (repère sans maintenance).
- `L → 1` : `liq ≈ 2E` — le prix doit doubler pour perdre toute la marge.
- Si `1/L < MMR` : la marge initiale est inférieure à la marge de maintenance
  à l'entrée → la position ne peut pas exister → `liq = E` (figé). Ce seuil
  définit le domaine valide de H2/H3 : `L < 1/MMR`.

**Référence** : spec Binance USDT-M « Risk limits » (structure des tiers),
formule d'équilibre de solde de marge.
**Code** : `src/market/exchange_spec.py::liquidation_price_short`.
**Test** : `tests/test_exchange_spec.py`, `tests/test_liquidation.py`.

---

## 4. H2 — Probabilité de premier passage à deux barrières

### 4.1 Forme continue (formule fermée)

Le log-prix est un mouvement brownien arithmétique `X_t = X_0 + μt + σW_t`.
Un SHORT entre à `E`. La liquidation (barrière HAUTE) est à
`liq = E·(1+d)`, le take-profit (barrière BASSE) à `TP = E·(1−s)`.
Distances logarithmiques **exactes** :

```
a = ln(E/TP) = −ln(1−s)          (vers le TP, vers le bas)
b = ln(liq/E) = ln(1+d)          (vers la liq, vers le haut)
```

**Pourquoi `−ln(1−s)` et pas `s` ?** Le moteur ferme à `TP = E·(1−s)`, donc la
distance en log est exactement `ln(E/TP)`. À l'ordre 1 en `s`, `a ≈ s` ; la
forme exacte est exigée par le Monte Carlo (`03_ground_truth.py`) qui
discriminerait les deux à mieux que 1 %.

La probabilité de toucher la barrière haute avant la basse est la formule
classique du premier passage à deux barrières :

```
P(liq) = (1 − e^{2μa/σ²}) / (e^{−2μb/σ²} − e^{2μa/σ²})
```

**Forme numériquement stable** (implémentée) :

```
P(liq) = expm1(−2μa/σ²) / expm1(−2μ(a+b)/σ²)      (μ > 0)
P(liq) = e^{2μb/σ²} · expm1(2μa/σ²) / expm1(2μ(a+b)/σ²)   (μ < 0)
```

**Cas limites exacts (T3).**
- `μ → 0` : `P → a/(a+b)` — la dérive s'annule, seules les distances comptent.
- `b → 0` (levier maximal, liq à l'entrée) : `P → 1`.
- `a → 0` (TP nul) : `P → 0`.

**Référence** : Karlin & Taylor (1975) ch. 7 ; Borodin & Salminen (2002) —
probabilité de premier passage à deux barrières du mouvement brownien
arithmétique. **Code** : `src/risk/two_barriers.py::_prob_from_ab`.
**Test** : `tests/test_two_barrier.py` (cas limites, monotonies) et
`tests/test_ground_truth.py` (Monte Carlo continu, tolérance 5σ).

### 4.2 Vérité terrain par Monte Carlo continu (H2)

`simulate_two_barrier` simule `X_t` en pas discret `dt` (défaut 0.01 h) avec
barrières absorbantes à `+b` et `−a`, détection par croisement du pas, `cap`
trajectoires. Le pas fin rend le biais de discrétisation négligeable devant la
tolérance binomiale 5σ. Critère : `|p̂ − P| ≤ 5·√(P(1−P)/N)`.

**Code** : `src/risk/monte_carlo.py::simulate_two_barrier`.
**Script** : `scripts/03_ground_truth.py` (résultat : PASS).

### 4.3 H3 — Plafond de levier (l'inverse de H2)

`L*(α, s, μ, σ) = max{ L : P(liq)(L, s, μ, σ) ≤ α }`, résolu par dichotomie sur
le domaine valide `L ∈ [1+, 1/MMR−)` (T4). `P(liq)` est monotone croissante en
`L` dans le domaine (plus de levier → marge plus petite → liq plus proche) ;
si `P(liq)(L→1⁺) > α`, aucun levier ne respecte le budget → `L* = None` (T5).

Monotonies **constatées** :
- `L*` croît en `|μ|` quand `μ < 0` (un bear market protège structurellement
  un SHORT) ;
- `L*` décroît en `σ` pour `μ ≤ 0`, mais **croît** en `σ` pour `μ > 0` : à
  dérive positive, c'est à faible volatilité que la liq est la plus probable
  (la dérive domine le bruit). À `μ = 0`, `L*` est constant en `σ` car
  `P = a/(a+b)` n'en dépend pas.

**Code** : `src/risk/two_barriers.py::max_leverage_for_alpha`.
**Test** : `tests/test_two_barrier.py`.

---

## 5. H4 — Prédiction hors-échantillon : les deux corrections de mesure

### 5.1 Correction n° 1 — Prédiction discrète (granularité horaire)

Le moteur surveille les barrières **barre à barre** (OHLC horaire, engine E6 :
liq si `high ≥ liq_price` d'abord, puis TP si `low ≤ tp_price`), pas en temps
continu. La formule continue H2 sous-estime le risque de liquidation à
monitoring grossier (mesuré sur le contrôle GBM : `P_continue ≈ 0.108` vs
`P_observé ≈ 0.111` à `L=5, s=2%, σ=2.5%`).

La prédiction H4 est donc le Monte Carlo **discret**
`simulate_two_barrier_bars`, aux sémantiques exactes du moteur :
- une barre = un rendement log `Δ ~ N(μ, σ)` + un **pont brownien** intra-barre
  simulé en `steps_per_hour` sous-pas, donnant les extrêmes `high/low` ;
- liquidation si `X + max_barre ≥ b`, sinon TP si `X + min_barre ≤ −a` (la liq
  gagne en cas de double touch, E6) ;
- `X` = log-écart cumulé depuis l'entrée.

Le pont est construit par `bridge = U − (j/m)·U_m` avec `U_j` cumul de
`N(0, 1/m)` : c'est un pont **standard** de variance `(j/m)(1−j/m)`, et
`logpath = (j/m)·Δ + σ·bridge` a bien la covariance d'un brownien discret
(`Var = σ²·(j/m)`). L'erreur classique — rescale `σ/√m`, qui divisait la
variance intra-barre par `m` — a été **corrigée en J6** (bug réel, corrigé).

**Convergence** : à `(μ, σ)` fixes, la prédiction discrète converge vers la
valeur continue quand `steps_per_hour → ∞` (vérifié 1→300 : 0.167→0.114).
La formule continue H2 reste la référence du processus continu, testée par
`03_ground_truth.py`.

**Code** : `src/risk/monte_carlo.py::simulate_two_barrier_bars`,
`src/validation/thesis.py::predict_discrete`.

### 5.2 Correction n° 2 — Wald cluster-robuste (dépendance intra-fenêtre)

**Le problème (mesuré).** Les positions d'une même fenêtre de test partagent le
même chemin de prix : leurs issues ne sont pas indépendantes. Le CI binomial
naïf (Wilson) sur-réjetait massivement : mesuré sur 20 seeds du contrôle GBM,
buckets rejetés dans ~11/20 cas au lieu de ~5 %.

**La solution.** Test d'hypothèse `H0 : E[p̂_w] = P̂_w` par **Wald
cluster-robuste, cluster = fenêtre**, avec la variance sandwich de la
**dispersion observée** entre fenêtres :

```
V_rob = (W/(W−1)) · Σ_w (n_w/N)² · (p̂_w − p̂)²
acceptation si  |p̂ − P̂| ≤ t(0.975, W−1) · √V_rob
avec  p̂ = Σ k_w/N,  P̂ = Σ n_w·P̂_w/N
```

**Pourquoi la dispersion observée et pas les résidus `p̂_w − P̂_w` ?** Un
sandwich sur les résidus serait **aveugle à un biais systématique** : si le
modèle se trompe de la même façon partout, chaque résidu `p̂_w − P̂_w` est
petit, la variance sandwich est petite, et le test accepte un modèle faussé.
La dispersion observée `p̂_w − p̂` mesure l'hétérogénéité réelle des fenêtres
indépendamment du modèle : un biais constant gonfle `|p̂ − P̂|` sans gonfler
`V`, donc le test devient **puissant contre un biais systématique**. Ce choix
est documenté comme un rejet délibéré d'une alternative (J6).

**Calibration (la norme §2.3 de THESIS.md).** Sur 20 seeds du contrôle GBM :
global 0/20, buckets 4/60, soit **PASS global ≈ 80 %**, cohérent avec 4 tests
indépendants à 95 % (`0.95⁴ ≈ 0.81`). Un run isolé peut donc échouer par
design (~1/5) : c'est le prix d'un test calibré, pas un défaut du modèle.

**Référence** : Cameron & Miller (2015) ; Liang & Zeger (1986).
**Code** : `src/validation/thesis.py::cluster_robust_test`.
**Tests** : `tests/test_thesis.py` (dont calibration et contrôle GBM).

### 5.3 Protocole complet (V1–V7)

1. **V1** — La stratégie tourne en continu sur toutes les barres (grid SHORT,
   `L`, `s` fixés). Chaque position est attribuée à la fenêtre de test où elle
   **s'ouvre** (W3). Le runner **redimensionne** les signaux (R5) : aucune
   position écartée pour cash/cap → pas de biais de sélection.
2. **V2** — Pour chaque fenêtre de test, `(μ̂, σ̂)` est estimé sur la fenêtre
   d'apprentissage précédente (M1, données strictement antérieures — W2).
3. **V3** — Prédiction discrète par fenêtre (5.1).
4. **V4** — Buckets de régime par tercile de volatilité d'apprentissage.
5. **V5** — Test Wald cluster-robuste global et par bucket (5.2).
6. **V6** — PASS si global accepté ET chaque bucket non vide accepté ET zéro
   skip cash/cap. Buckets non testables (n=0 ou W<2) : signalés.
7. **V7** — Positions jamais résolues en fin de jeu : **censurées**, comptées
   (`n_censored`), jamais ajoutées au dénominateur.

**Fenêtres (W1–W3).** Tests non chevauchants, adjacents (pas = `n_test`) :
chaque barre appartient à au plus une fenêtre de test → les fenêtres sont les
unités d'indépendance du test cluster-robuste. Apprentissage = `[test_start −
n_train, test_start)`. Par défaut : `n_train=2000 h`, `n_test=1000 h`.

**Code** : `src/validation/windows.py`, `src/validation/thesis.py`.
**Script** : `scripts/04_validate_thesis.py`.

---

## 6. H5 — Cohérence du numéraire

Tout l'accounting est en USD (E1). Marge isolée par position
`margin = notional/L` (E2), débitée avec les frais maker à l'ouverture (E3),
restituée avec le PnL net à la clôture (E4). Liquidation : PnL réalisé =
`−margin + funding net` (E5, marge de maintenance résiduelle négligée —
vérification cible : compte démo). Ordre dans la barre : liq (high) **avant**
TP (low) (E6, conservateur). Funding : pour un SHORT, `rate > 0` ⇒ shorts
reçoivent (E7). Slippage paramétrique en bps (E8) : entrée short =
`close·(1−slip)`, sortie = cible·`(1+slip)`, liquidation non affectée.

**Test** : invariance des PnL cumulés USD entre comptabilisation barre à barre
et fermeture en une étape ; PnL d'une position fermée = PnL brut − frais
d'entrée − frais de sortie − funding payé. Désaccord à `1e-9` → bug.
**Code** : `src/simulator/engine.py`. **Tests** : `tests/test_engine.py`,
`tests/test_metrics.py`, `tests/test_runner.py`.

---

## 7. Registre des résultats mesurés (régénérables)

| Mesure | Valeur | Script |
|---|---|---|
| H2 continu (L=5, s=2%, μ=0.0005/h, σ=0.03/h) | `p̂` vs `P` dans 5σ | `03_ground_truth.py` |
| Biais de granularité (contrôle, L=5, s=2%, σ=2.5%) | continue ≈ 0.108 vs observé ≈ 0.111 | mesuré via `04_validate_thesis.py` |
| Calibration (20 seeds, contrôle) | global 0/20, buckets 4/60, PASS ≈ 80 % | `tests/test_thesis.py` |
| H4 contrôle GBM (seed 60) | global `p̂=0.1245` vs `P̂=0.1206` (±0.014), **PASS** | `04_validate_thesis.py` |
| H4 données réelles (51 594 barres) | global `p̂=0.110` vs `P̂=0.124` (±0.023), **PASS** | `04_validate_thesis.py --data real` |
| PnL constaté (réel, hors thèse) | +176 933 USD / 3 256 trades (capital 10 000), 3 positions ouvertes | `04_validate_thesis.py --data real` |
