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
  **ASSUME** (vérification : marché).
- Funding aligné sur les barres 1h, marque = close de la barre : **ASSUME**
  (vérification : prix index). Taux 8h supposé appliqué à la barre
  correspondante ; trous signalés, jamais comblés silencieusement.
- À la liquidation, la marge de maintenance résiduelle est négligée (ordre de
  grandeur `MMR·notional`) : **ASSUME** (E5), vérification cible : compte démo
  réel.

---

## 2. Limites de la validation

### 2.1 Le test est calibré, donc pas infaillible

Le PASS ≈ 80 % du contrôle (4 tests à 95 %) est le comportement **nominal**
d'un test calibré : ~1 run isolé sur 5 échoue par design, même modèle vrai.
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

Le PnL (+176 933 USD sur 3 256 trades) est une **mesure** sur la fenêtre
testée, séparée de la thèse. Il ne prouve ni la rentabilité future, ni la
sûreté du levier. En particulier, il ne corrige pas du biais de sélection de
paramètres (le couple L/s a été choisi par le porteur du projet, pas par une
procédure publiée).

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
| Prix index pour le funding (vs close) | ASSUME | Remplacer marque par index dans E7 |
| Données 1 min sur la même fenêtre | absent | Mesurer l'erreur de modèle intra-barre |
| Autres actifs / intervalles / couples (L,s) | absent | Généraliser H4 |
| Compte démo réel (liq, frais, funding) | absent | Confronter engine à l'exécution réelle |

Le code refuse de charger des données sans provenance (`load_with_provenance`),
et les valeurs de spec vivent dans **un seul** endroit (`exchange_spec.py`) :
quand une vérification aboutit, la correction est une ligne, pas une chasse.
