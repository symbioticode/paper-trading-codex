# 06 — Calibrer le test avant de croire

> **Question** : comment savoir si une fréquence observée est « cohérente » avec
> une probabilité prédite ?
> **Fichiers** : `src/validation/thesis.py::cluster_robust_test` ;
> `tests/test_thesis.py`.

## Le piège

Le réflexe « standard » : la fréquence de liquidation `p̂` suit une loi
binomiale, donc on compare à la probabilité prédite `P̂` avec un intervalle de
Wilson. Le projet a fait ça — et le test **rejetait massivement un modèle
pourtant vrai par construction** : sur le contrôle GBM, des buckets étaient
rejetés dans ~11 seeds sur 20, au lieu des ~5 % attendus.

## Pourquoi le test naïf ment : la non-indépendance

Un test binomial suppose des essais **indépendants**. Or les positions d'une
même fenêtre de test partagent **le même chemin de prix** : quand le prix monte,
toutes les positions de la fenêtre sont simultanément plus proches de la
liquidation. Leurs issues sont corrélées. La variance réelle de `p̂` est plus
grande que celle qu'assume le binomial → le test rejette trop souvent.

## La correction : Wald cluster-robuste, cluster = fenêtre

On regroupe les positions **par fenêtre** (les unités réellement indépendantes)
et on estime la variance de la **dispersion observée entre fenêtres** :

```
V_rob = (W/(W−1)) · Σ_w (n_w/N)² · (p̂_w − p̂)²
acceptation si  |p̂ − P̂| ≤ t(0.975, W−1) · √V_rob
```

Deux détails qui comptent :

1. **La variance mesure la dispersion OBSERVÉE** `p̂_w − p̂`, pas les résidus
   `p̂_w − P̂_w`. Pourquoi ? Un sandwich sur les résidus est **aveugle à un biais
   systématique** : si le modèle se trompe de la même façon partout, chaque
   résidu est petit, la variance est petite, et le test accepte un modèle
   faussé. La dispersion observée, elle, gonfle `|p̂ − P̂|` sans gonfler `V` :
   le test devient **puissant contre un biais constant**. (Cette variante
   « évidente » a été délibérément rejetée en J6 — c'est documenté.)
2. **Les degrés de liberté** : `t(0.975, W−1)`, avec `W` fenêtres — la
   correction de Student pour petit échantillon de clusters.

## La méthode qui rend le test fiable : le calibrer sur un contrôle

Comment savoir si un test statistique se comporte correctement ? **On mesure
son taux de faux rejets sur un jeu où le modèle est vrai par construction** (le
contrôle GBM). Résultat de la calibration sur 20 seeds :

```
global : 0 rejet sur 20
buckets : 4 rejets sur 60
PASS global ≈ 80 %  =  0.95⁴  (4 tests indépendants à 95 %)
```

Le test se comporte **à son niveau nominal** : quand le modèle est vrai, il
accepte ~80 % du temps (4 tests à 5 % indépendants → 0.95⁴ ≈ 0.81). La
conséquence est un peu contre-intuitive : **~1 run isolé sur 5 échoue par
design**, même avec un modèle parfait. C'est le prix d'un test calibré, pas un
défaut du modèle — et c'est pourquoi on ne lit jamais un FAIL isolé comme une
preuve.

## À retenir

> Avant de faire confiance à un test statistique, mesurez son taux de faux
> rejets sur un contrôle où la vérité est connue. Et méfiez-vous de
> l'indépendance : des positions qui partagent le même chemin de prix ne sont
> pas des essais indépendants.
