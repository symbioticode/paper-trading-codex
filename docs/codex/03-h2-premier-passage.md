# 03 — H2 : le premier passage à deux barrières

> **Question** : une fois le SHORT ouvert, quelle est la probabilité de toucher
> la liquidation avant le take-profit ?
> **Fichiers** : `src/risk/two_barriers.py` ; `src/risk/monte_carlo.py` ;
> `scripts/03_ground_truth.py`.

## Le piège

« La probabilité d'être liquidé est petite si on n'est pas trop loin de la
liquidation. » C'est un sentiment, pas un nombre. Et si on essaie de le
chiffrer naïvement : « la moitié des cas » — mais sans modèle de prix, n'importe
quelle réponse est possible. Le prix bouge en continu ; la question est celle
d'un **premier passage** : le prix atteindra-t-il d'abord la barrière haute
(liquidation) ou la basse (take-profit) ?

## La méthode : un modèle qui a une réponse fermée

On modélise le log-prix par un mouvement brownien avec dérive `μ` et volatilité
`σ`. Depuis l'entrée, le SHORT est enfermé entre deux barrières
**logarithmiques** :

```
a = ln(E/TP) = −ln(1 − s)   (distance au TP, vers le bas)
b = ln(liq/E) = ln(1 + d)   (distance à la liq, vers le haut)
```

⚠️ Pourquoi `−ln(1−s)` et pas simplement `s` ? Le moteur ferme à
`TP = E·(1−s)`, donc la distance **exacte** en log est `ln(E/TP)`. À l'ordre 1,
`a ≈ s` — mais le Monte Carlo du projet (tolérance 5σ) discriminerait les deux
approximations à mieux que 1 % : la forme exacte est exigée, pas un raffinement.

La probabilité de toucher la barrière haute avant la basse est une formule
classique du mouvement brownien :

```
P(liq) = (1 − e^{2μa/σ²}) / (e^{−2μb/σ²} − e^{2μa/σ²})
```

Implémentée sous une forme **numériquement stable** (via `expm1`, qui évite la
cancellation quand `μ` est petit) :

```
P(liq) = expm1(−2μa/σ²) / expm1(−2μ(a+b)/σ²)        (μ > 0)
```

**Cas limites à connaître (ils sont le test) :**
- `μ → 0` : `P → a/(a+b)` — sans dérive, seules les distances comptent ;
- `b → 0` (liq collée à l'entrée) : `P → 1` — liquidé presque sûrement ;
- `a → 0` (TP nul) : `P → 0`.

## La preuve que la formule est exacte : un ancrage indépendant

Une formule qu'on ne vérifie que sur elle-même ne prouve rien. Le projet
simule donc N trajectoires browniennes (pas fin `dt`), barrières absorbantes,
et compare la **fréquence observée** `p̂` à la probabilité prédite `P` avec une
tolérance binomiale de **5σ** :

```
|p̂ − P| ≤ 5·√(P(1−P)/N)
```

C'est l'**ancre anti-contradiction** du projet : si H2 échoue, rien d'autre ne
peut être cru — les barrières, les moments, la validation hors-échantillon
reposent tous dessus. Résultat : PASS (formule vérifiée à 10 000 trajectoires).

## À retenir

> Avant de croire une formule de probabilité, ayez une **vérification
> indépendante** (ici, un Monte Carlo du processus) et connaissez ses cas
> limites. Une formule est un contrat, pas une opinion.
