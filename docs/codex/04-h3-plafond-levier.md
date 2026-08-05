# 04 — H3 : le plafond de levier, l'inverse de la probabilité

> **Question** : quel levier peut-on se permettre pour un budget de risque
> donné ?
> **Fichiers** : `src/risk/two_barriers.py::max_leverage_for_alpha` ;
> `tests/test_two_barrier.py`.

## Le piège

« Le levier 8x est sûr quand la volatilité est sous 3,5 %. » Une règle avec un
seuil fixe recopie une expérience passée dans une phrase. Elle est fausse dès
que le marché change de régime (dérive, volatilité), et surtout elle n'a
**aucun paramètre pour le risque** : rien ne dit *combien de risque* on accepte
de prendre.

## La méthode : définir le budget de risque d'abord

On inverse la question. Au lieu de demander « quel levier est sûr ? », on
demande : **pour une probabilité de liquidation cible `α`, quel est le plus
grand levier admissible ?**

```
L*(α, s, μ, σ) = max{ L : P(liq)(L, s, μ, σ) ≤ α }
```

Résolu par **dichotomie** sur le domaine valide (`1/L > MMR`, sinon la position
n'existe pas, leçon 02). Si même au levier minimal le budget est dépassé, on
renvoie `L* = ∅` : aucun levier ne convient — c'est un résultat utile, pas une
erreur.

## Les monotonies qui surprennent (et qui sont testées)

Le projet a posé une question fine : comment `L*` varie avec `σ` ?

- **`μ ≤ 0`** (dérive baissière ou nulle) : plus la volatilité monte, plus le
  plafond baisse. Le SHORT est protégé par le bear market, mais le bruit finit
  par dominer.
- **`μ > 0`** : c'est l'inverse ! Le plafond **croît** avec la volatilité.
  Pourquoi ? À forte dérive haussière, la liquidation (au-dessus de l'entrée)
  est probable *surtout quand le bruit est faible* : c'est la dérive qui pousse
  le prix vers la liq, pas la volatilité. À `μ = 0`, `L*` est même constant en
  `σ` (car `P(liq) = a/(a+b)` n'en dépend pas).

La monotonie en `σ` **change de signe avec `μ`**. C'est exactement le genre de
chose qu'un seuil figé (« 8x sûr si σ < 3,5 % ») ne peut pas capturer.

## Mesuré dans le projet

`tests/test_two_barrier.py` vérifie ces monotonies sur une grille de
paramètres, la cohérence de `L*` avec H2, et le cas `L* = ∅`. La leçon
opérationnelle : **le dimensionnement doit être une fonction de `(α, s, μ̂, σ̂)`,
pas une constante**.

## À retenir

> Inversez la question du risque : choisissez d'abord la probabilité d'échec
> que vous acceptez, puis dérivez le levier. Et méfiez-vous des seuils fixes —
> une dérive positive inverse la dépendance à la volatilité.
