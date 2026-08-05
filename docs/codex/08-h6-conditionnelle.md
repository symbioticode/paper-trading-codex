# 08 — H6 : pré-enregistrer une hypothèse conditionnelle avant de calculer

> **Question** : que faire d'un FAIL robuste ? Comment ouvrir une nouvelle
> hypothèse sans se mentir (ni refaire H4 au vert) ?
> **Fichiers** : `docs/HYPOTHESIS.md` §H6 (pré-enregistrement) ;
> `docs/ENQUETE_FAIL.md` ; branche `feature/h6-conditional-liq`.

## Le piège

Après un FAIL crédible, la tentation est double :
- chercher un jeu de paramètres `(L, s)` ou une fenêtre qui fait **passer** H4 ;
- ou au contraire considérer le FAIL comme définitif et arrêter.

REV03 interdit explicitement la première (le FAIL du bucket vol 1 est publié
tel quel, il a survécu à la correction du moteur ET à la recalibration — il est
*plus* crédible, pas moins). La bonne sortie est la seconde direction, mais
scientifique : **formuler ce que le FAIL suggère** comme une nouvelle hypothèse
testable, H6, et la **pré-enregistrer** avant le moindre calcul.

## Ce que le FAIL réel suggère

L'entrée de la stratégie n'est pas un instant neutre : elle suit
systématiquement un trigger de momentum (G3). Or, conditionnel à ce trigger, le
marché réel montre une **exhaustion** : la barre qui suit plonge en moyenne de
1,15–1,55 % (60–77 % de la distance au TP), 56 % des positions sont fermées au
TP en moins de 6 h, 76 % en 24 h. Le modèle iid-GBM-avec-pont ne contient pas
cette structure : il « continue le momentum » (μ>0 → liquidation) là où la
réalité « épuise le momentum » (trigger → pullback → TP). C'est la lecture la
plus probable du FAIL du bucket médian (`p̂=0.0845` vs `P̂=0.1245`).

## La règle : pré-enregistrer AVANT de calculer

Une hypothèse conditionnelle peut se mentir à elle-même de mille façons :
- choisir les variables **après** avoir vu lesquelles fonctionnent ;
- tester 20 variantes et ne publier que la meilleure (cherry-picking) ;
- comparer H6 à un H4 affaibli pour « gagner » à coup sûr.

Le pré-enregistrement (dans HYPOTHESIS.md §H6, en commit **avant** tout calcul)
fige d'avance :
1. **Variables candidates** — une liste fermée, décrétée avant de regarder les
   données (taille du spike, position du close, mèches, momentum pré-trigger,
   distance à l'ancre, μ/σ locaux, fréquence des triggers, barre suivante).
2. **Découpage train/test** — fenêtres non chevauchantes, paramètres estimés sur
   train uniquement, prédiction sur test hors-échantillon (même esprit que H4).
3. **Métrique** — l'amélioration de la calibration du Wald cluster-robuste sur
   le MÊME bucket vol 1 qui a échoué ; le global reste inchangé.
4. **Budget de variantes** — 3 maximum ; au-delà, correction de Bonferroni.

Tout écart à ce contrat (nouvelle variable, nouvelle métrique, 4ᵉ variante)
n'est pas un « ajustement », c'est une **nouvelle hypothèse** qui mérite sa
propre REV — exactement comme H6 est née de H4.

## Pourquoi H6 n'efface pas H4

H6 est une **extension** : `src/risk/conditional.py` ne touche ni
`two_barriers.py` ni le pipeline H4. Si H6 réussit, le FAIL H4 reste publié et
H6 explique *pourquoi* il avait lieu (le modèle conditionnel est mieux calibré).
Si H6 échoue, le FAIL H4 reste le résultat — et le mécanisme d'exhaustion,
pourtant chiffré, ne suffit pas à prédire la liquidation. Dans les deux cas le
projet gagne : on ne « répare » pas une hypothèse, on la **remplace par une
autre plus informée**, et on le dit.

## À retenir

> Quand un FAIL est robuste, ne le réparez pas : **lisez-le**. Ce qu'il suggère
> devient une hypothèse nouvelle, et cette hypothèse est **pré-enregistrée avant
> tout calcul** — variables, découpage, métrique et budget de variantes fixés à
> l'avance. La réussite de cette étape se mesure à la qualité du contrat, pas à
> un README plus flatteur.
