# 02 — H1 : la liquidation, dérivée pas mémorisée

> **Question** : d'où vient réellement le prix de liquidation d'un SHORT ?
> **Fichiers** : `src/market/exchange_spec.py` ; `tests/test_exchange_spec.py`.

## Le piège

La formule qu'on trouve partout sur les forums est une **approximation** :

```
liq ≈ E·(1 + 1/L − MMR)
```

Elle est « presque juste » et personne ne se demande ce qu'elle suppose.
Résultat : elle plante sur les cas limites (petit levier, MMR élevé), et quand
elle est fausse, personne ne sait *pourquoi*. Un projet falsifiable ne peut pas
reposer sur une formule recopiée sans savoir d'où elle sort.

## La méthode : dériver depuis l'équilibre de solde

En marge isolée, une position est liquidée quand son **solde** (marge + PnL non
réalisé) tombe au niveau de la **marge de maintenance**. On écrit cet équilibre
pour un SHORT entré à `E` :

```
marge + PnL_non_réalisé = liq · qty · MMR
E·qty/L + (E − liq)·qty = liq·qty·MMR
```

On simplifie `qty` et on isole `liq` :

```
liq = E·(1 + 1/L) / (1 + MMR)
```

C'est la formule **exacte** de `src/market/exchange_spec.py`. L'approximation
des forums est le développement au premier ordre en `MMR`. La distance de
liquidation (hausse tolérée) en découle :

```
d = (liq − E)/E = (1/L − MMR)/(1 + MMR)
```

## Les cas limites ne sont pas du détail — ils sont le test

- **`MMR → 0`** : `liq → E·(1 + 1/L)`. Sans maintenance, liquider le double
  du levier, comme attendu.
- **`L → 1`** : `liq ≈ 2E`. Il faut que le prix **double** pour perdre toute la
  marge — cohérent avec « sans levier, une position n'est pas liquide avant
  −100 % ».
- **`1/L < MMR`** : la marge initiale est déjà inférieure à la maintenance.
  La position ne peut pas exister → on fige `liq = E`. Ce seuil n'est pas un
  cas d'école : il définit le **domaine valide** de tout le reste de la thèse
  (voir leçon 04) : `L < 1/MMR`.

## Mesuré dans le projet

`tests/test_exchange_spec.py` vérifie ces propriétés algébriques (monotonie en L
et MMR, bornes, seuil de non-viabilité) **et** la cohérence avec
l'approximation au premier ordre. Le statut des valeurs est explicite :
`TIER_1_MMR = 0.0050` est marqué `ASSUME` (à vérifier via
`/fapi/v1/leverageBracket`, 401 sans clé au 2026-08-04), pas `OBSERVE` — un
projet honnête distingue ce qu'il a vu de ce qu'il suppose.

## À retenir

> Ne mémorisez pas une formule : dérivez-la depuis un équilibre, puis testez
> ses cas limites. C'est le cas limite qui révèle où la formule cesse d'être
> vraie.
