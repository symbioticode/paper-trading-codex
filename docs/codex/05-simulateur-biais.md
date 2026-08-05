# 05 — Le simulateur et les biais de mesure

> **Question** : pourquoi un backtest ment, et comment l'empêcher de mentir ?
> **Fichiers** : `src/simulator/engine.py` (E1–E9), `src/strategy/grid_short.py`
> (G1–G7), `src/simulator/runner.py` (R1–R5) ; `src/risk/monte_carlo.py`.

## Le piège

Un backtest a une vertu et un vice : il est **déterministe** (même entrée, même
sortie), donc on le croit ; mais il ne vérifie rien par lui-même. Les erreurs
les plus coûteuses du projet n'ont pas été des erreurs de formule — ce sont des
**écarts entre ce qu'on croyait simuler et ce que le code faisait vraiment**.
Trois ont été trouvées et corrigées. Les voici, avec leur ampleur mesurée.

## Biais n° 1 — L'overshoot d'entrée

**Le piège** : exécuter l'ordre au niveau de grille « touché » par le high.
**Pourquoi c'est faux** : si le prix touche le niveau puis redescend, il est
*déjà plus bas* quand un ordre marché s'exécute réellement. L'entrée effective
était systématiquement en dessous du niveau, faussant la distance à la
liquidation.

**La correction (G3)** : exécution **au close** de la barre déclenchante.
L'entrée est le prix courant ; la formule H2 s'applique exactement depuis
l'entrée. C'est la convention la plus importante de la stratégie.

## Biais n° 2 — Le monitoring barre à barre vs continu

**Le piège** : utiliser la formule continue H2 comme prédiction alors que le
moteur surveille les barrières **par barre OHLC** (liq sur `high`, TP sur
`low`), pas en continu.

**Pourquoi c'est faux** : à monitoring grossier, le risque de liquidation est
sous-estimé par la formule continue.

**La correction (V3)** : la prédiction H4 est le Monte Carlo **discret**
`simulate_two_barrier_bars`, avec les sémantiques exactes du moteur (une barre =
un rendement + un pont brownien intra-barre donnant les extrêmes). **Mesuré** :
à `L=5, s=2%, σ=2,5%`, formule continue ≈ 0.108 vs observé ≈ 0.111. La formule
continue reste la référence du processus continu, testée séparément.

## Biais n° 3 — Le redimensionnement ou le biais de sélection

**Le piège** : ignorer les signaux non exécutables (pas assez de cash, notionnel
trop gros) → l'échantillon de positions analysé n'est pas celui que la stratégie
aurait réellement produit.

**La correction (R5)** : le runner **réduit la taille** `qty` (jamais la
géométrie L/s — les barrières ne dépendent que de L et s, pas de la taille)
pour rendre le signal exécutable. Skip uniquement si la taille résultante est
nulle. Résultat mesuré : zéro skip sur tous les runs — pas de biais de
sélection par solvabilité.

## La règle qui a permis de les trouver

Les trois biais ont été découverts parce que les conventions étaient
**écrites** (E1–E9, G1–G7, R1–R5) et que chaque convention avait un test ou une
mesure. La revue externe (REV1) a ensuite trouvé un quatrième écart — le
slippage de sortie TP non appliqué malgré E8 — précisément en confrontant la
doc au code. **Un simulateur ne ment pas quand ses conventions sont écrites et
qu'on vérifie le code contre elles.**

## À retenir

> Écrivez d'abord ce que le simulateur est censé faire, puis vérifiez le code
> contre l'écrit. Les trois pires biais du projet étaient des écarts
> doc↔code, pas des erreurs de mathématiques.
