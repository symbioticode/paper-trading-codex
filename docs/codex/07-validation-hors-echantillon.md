# 07 — La validation hors-échantillon et ses limites

> **Question** : que prouve réellement un PASS ? Et un FAIL ?
> **Fichiers** : `scripts/04_validate_thesis.py` ; `src/validation/windows.py` ;
> `docs/LIMITATIONS.md`.

## Le piège

Deux erreurs symétriques possibles :
- croire qu'un PASS **prouve** que la stratégie est bonne (rentable, sûre) ;
- ou croire qu'un FAIL **invalide** tout le travail.

Ni l'un ni l'autre. Un test de validation ne dit pas « bonne » ou « mauvaise »
stratégie : il teste une **relation statistique précise**, dans un cadre précis.

## Ce qui est réellement testé

L'énoncé H4 : la **fréquence de liquidation observée** hors-échantillon est
cohérente avec la **probabilité prédite**, globalement et par régime de
volatilité. Rien d'autre.

### Le protocole (W1–W3, V1–V7)

1. **Fenêtres indépendantes** : tests non chevauchants et adjacents ; chaque
   barre appartient à au plus une fenêtre de test → les fenêtres sont les unités
   d'indépendance du test (leçon 06).
2. **Pas de fuite** : `(μ̂, σ̂)` d'une fenêtre sont estimés sur les barres
   d'apprentissage **strictement antérieures** ; une position est attribuée à la
   fenêtre où elle **s'ouvre**, suivie jusqu'à résolution même au-delà. Les
   positions jamais résolues en fin de jeu sont **censurées** (comptées, jamais
   mises au dénominateur).
3. **Prédiction discrète** (leçon 05) et **test cluster-robuste calibré**
   (leçon 06).
4. **PASS** exige : global accepté ET chaque bucket non vide accepté ET **zéro
   skip** cash/cap (leçon 05, pas de biais de sélection).

### Le contrôle d'abord, les données ensuite

La discipline : **le modèle est vrai par construction sur le contrôle GBM**,
donc la validation complète DOIT y passer (seed 60 : PASS, `p̂=0.1245` vs
`P̂=0.1206` ±0.014). Si elle échouait sur le contrôle, ce serait la machinerie
(estimation, simulateur, test) qui serait en cause, pas le marché. Note REV2 :
le contrôle s'exécute avec un **capital abondant** (1 M USD) — H4 mesure la
fréquence de liquidation (géométrie L/s), pas la solvabilité du portefeuille.
À capital 10 000, la grille SHORT se vide sur le GBM à dérive positive (le
PnL corrigé est négatif) et le skip cash (R5) tronque l'échantillon : le
contrôle échouerait pour une raison de portefeuille, pas de machinerie. Ce
n'est qu'ensuite qu'on applique le test aux **données réelles** (SOLUSDT perp 1h,
51 594 barres) : résultat **FAIL publié** — global `p̂=0.1100` vs `P̂=0.1236`
±0.0149 OK, mais bucket de volatilité médiane `p̂=0.0845` vs `P̂=0.1245`
±0.0196 **HORS** (écart 0.040) ; buckets 0 et 2 OK. **H4 est réfutée sur le
régime de volatilité médiane** : les positions de ce régime se liquident moins
que prédit. C'est exactement la sortie qu'un test falsifiable doit produire —
pas un bug, un résultat qui borne le domaine de validité du modèle.

## Que prouve un PASS, exactement ?

Que **sur ces fenêtres, sous ces assomptions** (GBM comme modèle de référence,
volatilité constante par fenêtre, MMR, frais, funding, granularité intra-barre
modélisée par un pont), la fréquence de liquidation est prévisible à la
précision annoncée. Un PASS ne prouve **ni** la rentabilité **ni** la sûreté
d'un levier. C'est pourquoi le PnL est un **constat séparé** (mesure −2 336 USD
sur 3 256 trades, capital 10 000 — hors thèse), jamais un argument de
validation. Note REV2 : le PnL publié a été corrigé — l'ancienne formule du
moteur multipliait le PnL par le levier (double comptage), gonflant un résultat
négatif en +176 933 USD.

## Que signifie un FAIL ?

Que la relation prédiction↔observation ne survit pas à ce régime — un
**résultat publié** avec l'hypothèse en défaut, l'écart et la significativité.
Rappel du leçon 06 : ~1 run sur 5 échoue par design (test calibré à 95 % par
test) ; on lit donc la distribution sur plusieurs runs, pas un isolé.

**Exemple réel, en l'état du projet** : le FAIL sur données réelles (bucket de
volatilité médiane) est un tel résultat — documenté dans HYPOTHESIS.md, le
global et les régimes 0/2 passant, ce qui localise le défaut du modèle plutôt
que de l'effacer.

## Ce que le projet ne prétend pas (et le garde-fou)

Liste déclarée dans `docs/LIMITATIONS.md` : pas d'ADL (délevérage automatique),
pas de benchmark Buy&Hold, pas de généralisation à d'autres actifs/intervalles,
MMR et frais en ASSUME. **La robustesse du projet n'est pas de couvrir tout —
c'est de dire précisément ce qui est couvert, et de publier le reste comme
limite.** La vérification ultime reste la même depuis la leçon 01 : chaque
affirmation peut être réfutée par un programme, et le programme est dans le
repo.

## À retenir

> Un PASS dit « la relation survit sur ces fenêtres, sous ces assomptions » —
> rien de plus, rien de moins. Publiez ce qui est couvert, déclarez ce qui ne
> l'est pas, et gardez un contrôle où le modèle est vrai pour que la
> machinerie elle-même soit testable.
