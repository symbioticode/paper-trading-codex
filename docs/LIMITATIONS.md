# LIMITATIONS.md — Ce que la thèse ne prétend pas, et les cibles de vérification

> Document des **limites déclarées**. Une limite est une assomption, une
> inconnue ou une simplification **explicitement étiquetée** avec sa cible de
> vérification. Ce document existe pour que personne ne lise les résultats au-
> delà de leur portée réelle.

---

## 1. Assomptions de modèle (par ordre de criticité)

### 1.1 GBM comme modèle de marché (H2/H4)

`P(liq)` est dérivée sous **GBM** : rendements logs iid gaussiens. C'est le
modèle du *contrôle* (où il est vrai par construction) et la référence de la
formule. Sur les données réelles, H4 teste précisément si cette relation
survit à un marché non-gaussien, à queues lourdes, à la volatilité variable.

- **Portée** : un PASS sur les données réelles ne signifie pas que SOL suit un
  GBM ; il signifie que la fréquence de liquidation reste prévisible à la
  précision annoncée sous le modèle.
- **Cible de vérification** : tests d'adéquation statistique du pipeline sur
  d'autres actifs/intervalles (hors périmètre actuel).

### 1.2 Volatilité constante par fenêtre (H4)

`(μ̂, σ̂)` sont estimés sur la fenêtre d'apprentissage (2000 h) et supposés
constants sur la fenêtre de test (1000 h). Le bucketing par tercile de
volatilité atténue mais ne supprime pas les régimes intra-fenêtre.

### 1.3 Granularité intra-barre des données réelles

Les données réelles sont des barres OHLC **horaires** : le moteur ne voit que
`high/low/close`. La prédiction discrète suppose un modèle de **pont
brownien** intra-barre (`steps_per_hour=30`). Les excursions intraday réelles
peuvent avoir des queues plus lourdes que le pont gaussien.

- **Portée** : le choix `steps_per_hour` est une **assomption déclarée**, pas
  une donnée observée.
- **Cible de vérification** : données de plus haute fréquence (1 min) sur la
  même fenêtre pour mesurer l'erreur de modèle intra-barre.

### 1.4 Marge de maintenance (MMR)

`TIER_1_MMR = 0.0050` (0.50 %) pour SOLUSPT est une **assomption** (statut
ASSUME dans `exchange_spec.py`), pas une valeur vérifiée.

- **Cible de vérification** : endpoint `/fapi/v1/leverageBracket?symbol=SOLUSDT`
  (requiert une clé API — 401 sans clé au 2026-08-04). Le code lit la valeur
  depuis une constante et l'écrit dans la provenance des résultats : toute
  analyse qui change de valeur doit re-pointer ici, jamais ailleurs.
- Notionnels plafonnés à `notional_cap` (défaut 49 000 USD) pour rester dans
  la tranche MMR 0.50 %.

### 1.5 Frais, slippage, funding

- Frais maker/taker VIP 0 sans rabais BNB : **ASSUME** (page « Futures fees »).
- Slippage constant, indépendant de la taille, paramétrable (défaut 0) :
  **ASSUME** (vérification : marché). Appliqué à l'entrée (ordre marché) **et**
  à la sortie TP (E8) ; la liquidation n'est pas affectée. Note REV1 : le
  slippage de sortie TP a été corrigé et verrouillé par test ; les résultats
  mesurés utilisent `slip_bps = 0`, donc non affectés.
- **ADL (Auto-Deleveraging).** En cas d'insolvabilité d'un contrepartiste,
  Binance peut appliquer un délevérage automatique qui liquide des positions
  en miroir à un prix différant de la liquidation "théorique". Ce mécanisme
  est **hors modèle** : H1/H5 supposent une liquidation complète à
  `liq_price`, sans liquidation partielle ni ADL. Revu en REV1 : β=N, non
  vérifié, non représenté — toute liquidation partielle en cascade réelle
  reste hors de la portée de cette thèse.
- Funding aligné sur les barres 1h, marque = close de la barre : **ASSUME**
  (vérification : prix index). Taux 8h supposé appliqué à la barre
  correspondante ; trous signalés, jamais comblés silencieusement.
- À la liquidation, la marge de maintenance résiduelle est négligée (ordre de
  grandeur `MMR·notional`) : **ASSUME** (E5), vérification cible : compte démo
  réel.

---

## 2. Limites de la validation

### 2.1 Le test est calibré, donc pas infaillible

Le PASS ≈ 80 % du contrôle initial (4 tests à 95 % = `0.95⁴`) a été invalidé
par REV2 puis **re-calibré** (TD-004, plancher `V_floor`) : contrôle non
contaminé → global 10/10 (10 000 h), 20/20 (5 000 h), buckets 29/30 (~nominal).
Le comportement **nominal** d'un test calibré demeure : ~1 run isolé sur 20
échoue par design au global, ~5 % des buckets — même modèle vrai.
**Un FAIL ne doit jamais être interprété seul** ; c'est la distribution sur
plusieurs runs (ou seeds) qui porte l'information.

### 2.2 Un seul jeu de données réel

La validation H4 porte sur **un** actif (SOLUSDT perp), **un** intervalle (1h),
**un** couple (L=5, s=2 %) et une fenêtre temporelle. La thèse survit sur ces
fenêtres et sous ces assomptions — rien de plus. Sa généralisation est une
**question ouverte** (voir §4).

### 2.3 Les fenêtres, pas le marché entier

Le découpage `train=2000 h / test=1000 h` couvre une partie de l'historique
(51 594 barres réelles). Les positions ouvertes en fin de jeu sont censurées
(V7) : elles ne participent pas au dénominateur.

### 2.4 Le PnL est un constat, pas une promesse

Le PnL (**−2 336 USD sur 3 256 trades**, equity finale 7 663 USD, capital
10 000) est une **mesure** sur la fenêtre testée, séparée de la thèse. Il ne
prouve ni la rentabilité future, ni la sûreté du levier. En particulier, il ne
corrige pas du biais de sélection de paramètres (le couple L/s a été choisi par
le porteur du projet, pas par une procédure publiée).

**Correction REV2.** Une première version de ce rapport publiait « +176 933 USD »
: la formule d'évaluation du moteur multipliait le PnL par le levier (le PnL
latent comme le PnL de TP l'étaient déjà par la définition du trade), doublant
l'exposition. Corrigée, la mesure est **négative** — le constat mesuré, lui,
reste conforme au contrat : chiffré, régénérable, daté.

**Effet de bord REV2 — solvabilité du contrôle GBM.** REV02 affirmait « H4
n'est pas affecté ». C'est **vrai sur les données réelles** (aucun skip cash,
chiffres H4 identiques avant/après correction) mais **faux sur le contrôle
GBM** : la boucle de backtest redimensionne/saute les positions selon le cash
disponible (R5). Sur GBM à dérive positive, la grille SHORT perd (à juste
titre) de l'argent : à capital 10 000, elle se vide, R5 tronque l'échantillon
et le contrôle échoue (bucket vol 2) — une **contamination de portefeuille,
pas un défaut de machinerie**. Preuve : à capital ≥ 1 M, R5 ne se déclenche
jamais et le contrôle reproduit **exactement** le PASS publié (seed 60 :
n=6649, p̂=0.1245 vs P̂=0.1206, tous buckets OK). Le contrôle GBM de
`04_validate_thesis.py` utilise donc par défaut un capital abondant pour
isoler H4 (géométrie L/s) de la solvabilité (voir docstring du script) ;
les données réelles gardent le capital du constat (10 000, aucun skip).

**Pas de benchmark Buy&Hold (REV1, β=N).** Ce livrable ne contient **aucun**
benchmark Buy&Hold ni plafond de référence : le PnL constaté n'est comparé à
aucune stratégie alternative. C'est une absence déclarée, pas un oubli masqué —
le PnL constaté ne doit donc être lu que comme une mesure absolue sur la
fenêtre testée.

---

## 3. Ce qui n'est PAS affirmé (et ne le sera jamais)

- « Ce bot est rentable » — seul le constat mesuré existe.
- « Le levier 8x est sûr quand σ < 3.5 % » — remplacé par H3/H4 paramétrés par
  `α` et testés hors-échantillon.
- Toute assertion sur des données synthétiques non marquées `synthetic`.
- Une prédiction du prix ou un alpha de trading.

---

## 4. Vérifications cibles (filet de sécurité)

| Cible | Statut | Action si le doute se confirme |
|---|---|---|
| `/fapi/v1/leverageBracket` (MMR réel SOLUSDT) | ASSUME | Corriger `TIER_1_MMR`, régénérer, re-publier |
| Page Binance « Futures fees » (frais) | ASSUME | Corriger `MAKER_FEE`/`TAKER_FEE` |
| Mécanisme ADL (délevérage automatique) | hors modèle | Documenter l'écart réel liq théorique vs liq ADL |
| Prix index pour le funding (vs close) | ASSUME | Remplacer marque par index dans E7 |
| Données 1 min sur la même fenêtre | absent | Mesurer l'erreur de modèle intra-barre |
| Autres actifs / intervalles / couples (L,s) | absent | Généraliser H4 |
| Benchmark Buy&Hold / plafond | absent | Ajouter une référence avant de commenter la rentabilité |
| Compte démo réel (liq, frais, funding) | absent | Confronter engine à l'exécution réelle |

Le code refuse de charger des données sans provenance (`load_with_provenance`),
et les valeurs de spec vivent dans **un seul** endroit (`exchange_spec.py`) :
quand une vérification aboutit, la correction est une ligne, pas une chasse.

### 4.1 Tableau ASSUME → vérifié / toujours ASSUME (REV03 §5)

À mettre à jour **au fil des vérifications** (endpoint Binance, compte démo,
données 1 min), pas seulement à la fin. Aucun ASSUME ne passe à « vérifié »
sans la preuve correspondante ; sinon il reste « toujours ASSUME ».

| Assomption (REV03 §5) | Statut | Preuve / cible | Quand vérifier |
|---|---|---|---|
| MMR réelle et brackets (`TIER_1_MMR = 0.50 %`) | toujours ASSUME | `GET /fapi/v1/leverageBracket?symbol=SOLUSDT` (401 sans clé API au 2026-08-04) | avant tout paper trading proche production |
| Frais exacts (maker/taker VIP 0, sans BNB) | toujours ASSUME | Page Binance « Futures fees » / compte réel | avant paper trading |
| Source du mark/index pour le funding | toujours ASSUME | Comparer close vs index sur les barres de funding | avant paper trading |
| Comportement réel de liquidation et ADL | toujours ASSUME | Compte démo / docs Binance ; documenter l'écart liq théorique vs liq ADL | avant paper trading |
| Ordre intra-barre (données 1 min) | toujours ASSUME | Ré-échantillonner 1 min sur la même fenêtre ; mesurer l'erreur du pont | quand les données sont disponibles |
| Slippage dépendant de la taille | toujours ASSUME | Carnet d'ordres / exécution réelle (liquidity) | quand exécution réelle |

---

## 5. Dettes tracées (REV2 / REV03 / REV03-1)

| Dette | Statut | Détail |
|---|---|---|
| **TD-001** — PnL multiplié par le levier (`unrealized()`) | **CORRIGÉ** (REV2) | `unrealized()` → `(entry−price)·qty` ; frais de sortie sur `qty·exit` (E11) ; funding sur notionnel d'ouverture figé (E7) ; tests réécrits depuis H1. Chiffres PnL régénérés : **−2 336 USD / 3 256 trades** (ancien +176 933 USD). |
| **TD-002** — reproductibilité déclarée en avance sur le repo | **PLANIFIÉ** (cible : 2026-09-30) | `run_reproducible.sh`, `MANIFEST`, `flake.nix`, `validate_thesis.py` référencés dans la doc, absents du repo (REV02 #6). REV03 §1 : replanifié avec date — TODO explicite, à livrer AVANT toute publication externe ; en attendant, reproductibilité via `activate.sh` + `pytest` + scripts 03/04 (`docs/STATUS.md` est la source canonique de comptage). |
| **TD-003** — compteur `n_censored` (sémantique W3/V7) | **CORRIGÉ** (REV2) | Scindé en `n_open_at_end` (positions réellement ouvertes en fin de jeu, censure V7) et `n_hors_fenetres` (résolus hors fenêtres). Test écrit depuis le texte W3/V7. |
| **TD-004** — calibration H4 invalidée par REV2 | **CORRIGÉ** (REV2) | La calibration « global 0/20 → ≈ 80 % » (moteur AVANT la correction du double levier) était invalide. Causes de la sur-rejection re-mesurée : contamination de portefeuille (R5 tronque l'échantillon quand la grille SHORT saigne sur le GBM à dérive positive) + effondrement de `V_rob` (fenêtres d'un bucket à fréquences quasi identiques, margin ~0.001 vs bruit ~0.024). **Correctif** : plancher binomial intra-fenêtre `V = max(V_rob, V_floor)` dans `cluster_robust_test`. **Re-calibré**, contrôle non contaminé (capital 1 M, skips=0) : 5 000 h → 20/20 PASS ; 10 000 h → global 10/10, buckets 29/30, 9/10 PASS ; 30 000 h → global 20/20 (FAIL = uniquement condition V6 « aucun skip »). Réel inchangé : FAIL bucket vol 1 (`p̂=0.0845` vs `P̂=0.1245`, ±0.0200) = déviation RÉELLE du modèle. Limite documentée : buckets à W=2 quasi non-testables (t(1)≈12.7·SE). |
| **TD-005** — garde-fou `update_status.py --check` manuel (pas de CI) | **PLANIFIÉ** (cible : au plus tard 2026-10-31, ou avant tout prochain audit externe) | REV03-1 §1 : `scripts/update_status.py` régénère la section Tests de `docs/STATUS.md` depuis la sortie réelle de pytest (`--collect-only -q`, exit code de `pytest -q`) ; `--check` échoue si le fichier commité dérive (vérifié : 103 tests, drift 104 → FAIL). Aucune CI dans le dépôt → le garde-fou est manuel ; le brancher sur une CI si elle apparaît. |

---

## 6. Notes de révision

- **REV2 #5 (resize) : à rejeter.** `n_skipped_cash/cap` est documenté dans R5
  de `runner.py` (« skip uniquement si la qty résultante est nulle ») ; le
  comportement actuel est conforme à la doc. Aucune correction — noté pour ne
  pas relancer une fausse alerte.
- **TD-004 : pathologie `V_rob` corrigée (plancher `V_floor`).** La dispersion
  inter-fenêtres `(p̂_w − p̂)²` peut s'effondrer ~0 quand 2–3 fenêtres d'un
  bucket ont des fréquences quasi identiques → margin ~0.001 et rejet de tout
  écart. Correctif : `V = max(V_rob, V_floor)` avec le plancher binomial
  intra-fenêtre. Conséquence documentée : buckets à W=2 quasi non-testables
  (t(1) ≈ 12.7·SE) — le global porte la puissance.
