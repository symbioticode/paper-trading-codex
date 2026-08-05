# ECONOMICS.md — Le constat économique (séparé de la thèse de risque)

> REV03 §4 — deux thèses, deux verdicts, jamais un seul :
>
> - **Risque** (`docs/THESIS.md`, `docs/HYPOTHESIS.md`) : la probabilité de
>   liquidation est-elle dérivable et prévisible hors-échantillon ? C'est la
>   thèse falsifiable H1–H6.
> - **Économie** (ce document) : le portefeuille grid SHORT a gagné ou perdu
>   de l'argent, combien, pourquoi, et par rapport à quoi ?
>
> Le PnL est un **constat mesuré** sur une fenêtre, jamais une promesse et
> jamais un argument de validation (règle posée dans `docs/THESIS.md`).

---

## 0. Protocole de mesure (reproductible)

- **Commande** : `python scripts/09_economic_benchmarks.py` (venv `activate.sh`).
- **Jeu** : Binance SOLUSDT perp, barres 1h, **51 594** barres,
  `2020-09-14 → 2026-08-04` (provenance sha256 vérifiée).
- **Capital** : 10 000 USD. Frais maker/taker 0.02 % / 0.04 %, **slippage 0**,
  **funding 0** (ASSUME : le funding n'est pas appliqué au constat — limite
  documentée, §7). Rendement du sous-jacent sur la période : **+2 070 %**.
- **Constat publié** : grille SHORT `L=5`, `s=2 %`, `qty=10 SOL`, telle que
  publiée dans `docs/STATUS.md` (le couple est celui du porteur de projet, pas
  d'une procédure — `docs/LIMITATIONS.md` §2.4).

---

## 1. Constat publié (L=5, s=2 %)

| Métrique | Valeur mesurée |
|---|---|
| Trades fermés | **3 256** (TP 2 907 / liq 349 ; 3 ouvertes en fin de jeu) |
| Taux de liq réalisé (sur résolus) | **0.1072** (H4 fenêtres : p̂ global = 0.1100) |
| PnL net total | **−2 336,29 USD** (−0,72 USD par trade fermé) |
| Equity finale réalisée | **7 663,28 USD** (−23,4 %) — figure publiée |
| Equity finale marquée (incl. non réalisé) | 7 642,18 USD (−23,6 %) |
| Drawdown maximal | 65,96 % |
| Cash minimum (fraction du capital) | 0,22 |
| Positions simultanées max / exposition max | 8 / 15 336 USD (≈1,5× le capital) |

### Décomposition de l'espérance par trade

| Contribution | n | PnL net | Par trade |
|---|---|---|---|
| Take-profit | 2 907 | +43 495 USD | **+14,96 USD** |
| Liquidations | 349 | −45 831 USD | **−131,32 USD** |
| Frais (entrée + sortie) | — | −1 372,51 USD | −0,42 USD |
| Funding | — | 0,00 USD (ASSUME) | 0,00 USD |
| **Net** | 3 256 | **−2 336,29 USD** | **−0,72 USD** |

Lecture : un TP rapporte ~15 USD, une liquidation coûte ~131 USD — un ratio
d'environ **8,8** (théorique `1/(s·L) = 10` avant frais). Le levier n'augmente
pas le gain d'un TP (relatif à `s`), il augmente **ce qu'on perd à la
liquidation** (`notional/L` intégralement). C'est toute l'asymétrie de la
grille SHORT levée.

---

## 2. Taux de liquidation d'équilibre (référence documentée)

Espérance de PnL par trade, sans frais ni funding, avec `p = P(liq)` :

```
E = (1−p)·s·N − p·(N/L)     N = notionnel
```

`E = 0` donne le **taux de liquidation d'équilibre** :

```
p* = s·L / (1 + s·L) = 0.02·5 / (1 + 0.02·5) = 0.10 / 1.10 ≈ 0.0909   (9,1 %)
```

- Si `p < p*` : le TP compense les liquidations → espérance positive.
- Si `p > p*` : chaque trade rapporte en attente **moins que zéro**.
- Les frais ne font que **baisser** `p*` (le TP net doit couvrir deux frais) :
  l'équilibre réel est sous 9,1 %.

**Confrontation mesurée** : taux de liq réalisé **0.1072 > p\*** → l'espérance
négative observée (−0,72 USD/trade) est **cohérente** avec le modèle de
comptage. Ce n'est pas une validation (H4 reste le test falsifiable) : c'est la
même mécanique comptable, vue sous l'angle « combien ».

---

## 3. Benchmarks passifs (même capital, même période)

| Stratégie | PnL net | Equity fin | Rendement |
|---|---|---|---|
| Buy & Hold long (1er close → dernier close) | +207 014 USD | 217 014 USD | **+2 070 %** |
| Cash pur | 0 USD | 10 000 USD | 0 % |
| **Grille SHORT levée L=5 (constat publié)** | −2 336 USD | 7 663 USD | **−23,4 %** |
| Grille SHORT **sans levier** (L≈1,01 ; marge/position identique) | +877 USD | 10 876 USD | **+8,8 %** |

Définition du « sans levier » : même logique d'entrée (G3), même `s=2 %`,
même **marge à risque par position** que le constat (qty réduite à 2,02 SOL pour
que `marge = notionnel/L` soit identique) ; à L≈1,01 la liquidation est quasi
impossible (≈ +98 %). Le TP gagne alors `s·(notionnel réduit)` — 5× moins par
trade — mais rien n'est jamais amplifié.

**Lecture (sur cette fenêtre)** :
- Le short levé est le **pire** des quatre : il perd de l'argent dans un marché
  qui a été multiplié par ~21. Le levier amplifie les pertes de liquidation
  sans jamais grossir le gain relatif d'un TP.
- Le short **sans levier** ressort légèrement positif (+8,8 %), mais très loin
  du B&H : la stratégie est structurellement « vendre de la volatilité » dans
  un marché directionnel haussier.
- Aucun de ces chiffres n'est une promesse : fenêtre unique, biais de
  sélection non publié, funding absent.

---

## 4. Sensibilité exploratoire — contexte, JAMAIS une sélection

Règles REV03 §4 : les chiffres ci-dessous sont **exploratoires**, ils ne
servent à rien d'autre qu'à borner la robustesse du constat. **Aucun (L, s)
n'est retenu ici** : le constat publié reste `L=5, s=2 %`. La même interdiction
que H4 s'applique — choisir un couple sur ces lignes pour re-publier un
résultat serait une tricherie.

| Paramètre | Trades | PnL net | Equity fin | Liq rate | DD max |
|---|---|---|---|---|---|
| L=3 (s=2 %) | 3 254 | +2 053 USD | 11 862 | 0.0688 | 73 % |
| L=5 (constat) | 3 256 | −2 336 USD | 7 663 | 0.1072 | 66 % |
| L=8 (s=2 %) | 3 257 | −5 469 USD | 4 533 | 0.1566 | 76 % |
| s=1 % (L=5) | 8 442 | −675 USD | 9 305 | 0.0525 | 75 % |
| s=3 % (L=5) | 1 689 | −1 803 USD | 8 201 | 0.1557 | 58 % |
| frais ×0,5 | 3 256 | −1 650 USD | 8 329 | 0.1072 | 61 % |
| frais ×2 | 3 256 | −3 709 USD | 6 269 | 0.1072 | 76 % |
| slip 10 bps | 3 191 | −10 000 USD | 0 | 0.1125 | 100 % |
| slip 30 bps | 2 451 | −10 000 USD | 0 | 0.1297 | 100 % |

Lectures (à lire comme des constats, pas des recommandations) :
- Le résultat publié est **très sensible** à `L`, `s`, aux frais et au
  slippage. Le point `L=3` est le seul couple levé positif de la grille.
- Le **slippage est dévastateur** : sur une grille à TP serrés (`s=2 %`), chaque
  TP paie le slippage de sortie ; 10 bps suffisent à ruiner le portefeuille.
  Le constat publié utilise `slip=0` — c'est une **hypothèse généreuse**.
- `s=1 %` augmente fortement le nombre de trades (8 442) mais reste négatif.

---

## 5. Ce que ce document ne dit pas

- Que la stratégie est « rentable » ou « non rentable » en général — elle est
  mesurée **négative sur cette fenêtre**.
- Que `L=3` serait « le bon couple » — c'est un point exploratoire, pas une
  recommandation (et le choisir maintenant serait une sélection de paramètres).
- Que le B&H est « la bonne stratégie » — c'est un benchmark passif de
  référence, pas une thèse.

La séparation risque/éco est totale : même si ECONOMICS.md changeait de
chiffres, H1–H6 et le FAIL H4 resteraient intacts — la géométrie de la
liquidation ne dépend pas de la rentabilité.

---

## 6. Références

- Script : `scripts/09_economic_benchmarks.py`.
- Constat PnL audité : `docs/STATUS.md` ; correction REV2 (`unrealized()`) :
  `docs/LIMITATIONS.md` §2.4.
- FAIL H4 (le risque, pas l'économie) : `docs/HYPOTHESIS.md` §H4.
- Limitations (MMR, frais, funding, slippage ASSUME) : `docs/LIMITATIONS.md` §1.
