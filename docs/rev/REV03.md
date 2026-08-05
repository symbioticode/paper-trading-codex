# REV03 — Dette post-REV02, isolation du résultat, ouverture de H6

**Statut** : à traiter par le Producteur
**Référence** : `docs/rev/REV02.md` (commit `a986c81`, 2026-08-05), audit `REV02_draft.md` (SOL), synthèse post-REV02
**Portée** : (1) fermer la dette de documentation/reproductibilité laissée ouverte après REV02, (2) isoler le résultat auditée sur une branche dédiée, (3) documenter H6 comme nouvelle hypothèse falsifiable distincte, (4) séparer explicitement risque et rentabilité en deux thèses. Aucune tentative de faire passer H4 au vert n'est demandée ni acceptée.

---

## 0. Rappel de principe (non négociable)

Le FAIL du bucket de volatilité médiane (`p̂=0.0845` vs `P̂=0.1245`, marge `±0.020`) **reste publié tel quel**. Il a survécu à la correction du moteur et à la recalibration du test — cela le rend *plus* crédible, pas moins. REV03 ne doit ni le retoucher, ni le nuancer dans le README, ni chercher un jeu de paramètres qui le fasse disparaître. Ce FAIL devient le point de départ de H6, pas un problème à résoudre par retouche statistique.

---

## 1. Dette de publication à fermer (TD-002 et dérives documentaires)

**FAIL constaté** (audit post-REV02) : le dépôt affirme sa propre reproductibilité et son propre comptage de tests avec des chiffres qui ne se recoupent pas entre eux.

| Fichier | Affirme | Doit dire |
|---|---|---|
| Dernier commit | 103 tests | référence unique |
| `README.md` (tableau) | 101 tests | à aligner sur le compteur réel de `pytest -q` au commit courant |
| Commentaire de commande | 100 tests | à aligner |
| `post-REV02.md` | arrêté au commit `c0282ba` | contient en réalité les résultats de `a986c81` — soit re-générer le doc à partir du bon commit, soit clarifier explicitement lequel des deux résultats est publié |

**Action** :
1. Une seule source de vérité pour le nombre de tests : générée par script (`pytest -q | tail -1` capturé dans un fichier, jamais recopiée à la main dans 3 endroits différents). Tant qu'il n'y a pas de script qui régénère ces chiffres automatiquement, il ne faut plus les écrire en dur à plus d'un endroit — un seul fichier canonique (ex. `docs/STATUS.md`), les autres documents y renvoient par lien plutôt que de dupliquer le chiffre.
2. `post-REV02.md` : corriger l'en-tête pour référencer le commit exact dont il rapporte les résultats (`a986c81`), ou scinder en deux rapports horodatés si les deux commits doivent rester traçables séparément.
3. **TD-002** (reproductibilité) : soit livrer `run_reproducible.sh`, le `MANIFEST`, et l'environnement verrouillé promis par `HYPOTHESIS.md`, soit — si ce n'est pas encore priorisé — retirer ces mentions de `HYPOTHESIS.md`/`.gitignore` et les remplacer par un TODO explicite avec date cible. **Le dépôt ne doit pas s'auto-décrire comme reproductible tant que les scripts cités n'existent pas.** C'est un FAIL de forme, pas de fond, mais c'est exactement le type d'écart que Critique a déjà sanctionné une fois (chemins `HYPOTHESIS.md` en avance sur le dépôt) — il ne doit pas réapparaître une deuxième fois sous une autre forme.

**Critère d'acceptation** : un seul chiffre de tests visible dans tout le dépôt, `post-REV02.md` référence son propre commit correctement, TD-002 est soit fermée soit explicitement replanifiée avec date.

---

## 2. Isolation du résultat audité — branche dédiée

**Objectif** : le commit `a986c81` (moteur corrigé, PnL réel `-2 336 USD`, H4 recalibrée avec plancher binomial, FAIL réel confirmé) doit devenir une **baseline figée**, protégée des futurs travaux exploratoires sur H6 et sur la thèse économique.

**Action** :
1. Créer une branche `baseline/rev02-audited` à partir de `a986c81`, taguée `v0-rev02-audited`. Cette branche ne reçoit plus que des corrections de documentation (section 1), jamais de changement de comportement du moteur, du test H4, ou des paramètres de stratégie.
2. Tout le travail sur H6 (section 3) et sur la thèse économique (section 4) se fait sur des branches séparées issues de cette baseline (`feature/h6-conditional-liq`, `feature/economic-thesis`), jamais directement sur `main` tant qu'elles ne sont pas closes et revues.
3. `main` peut avancer, mais toute divergence entre `main` et `baseline/rev02-audited` sur les résultats déjà publiés (H2, H4 réel, PnL réel) doit être documentée dans un nouveau `docs/rev/REV0X.md`, jamais silencieuse.

**Critère d'acceptation** : `git log baseline/rev02-audited` s'arrête à `a986c81` + commits de doc uniquement ; aucun commit de `src/` sur cette branche après le tag.

---

## 3. Documentation de H6 — hypothèse conditionnelle

**Constat déclencheur** (à citer tel quel dans `docs/HYPOTHESIS.md`, ne pas reformuler pour l'édulcorer) : l'entrée en position n'est pas un instant neutre — elle suit systématiquement un trigger de momentum (G3), et les données réelles montrent un pullback d'exhaustion majoritaire après ce trigger (56 % de TP atteint sous 6h, 76 % sous 24h). Le modèle iid actuel (`P(liq | μ, σ, L, s)`) ne capture pas cette structure conditionnelle, ce qui est la lecture la plus probable du FAIL du bucket médian.

**À ajouter dans `docs/HYPOTHESIS.md`** (nouvelle section H6, même format que H1–H5 : énoncé, dérivation ou protocole, critère de falsification) :

> **H6** — La probabilité de liquidation conditionnelle à la morphologie du trigger G3 et au régime précédent est mieux calibrée hors-échantillon que la prédiction fondée uniquement sur `μ` et `σ`.

**Pré-enregistrement obligatoire avant tout calcul** (règle producteur : jamais de sélection de variable après avoir vu le résultat) :
- Variables candidates autorisées, fixées à l'avance : taille du spike déclencheur, position du close dans la chandelle, taille des mèches, momentum des heures précédentes, distance à l'ancre, `μ`/`σ` locaux, fréquence récente des triggers, comportement de la barre suivant le trigger.
- Découpage temporel (train/test) identique en esprit à H4 : fenêtres non chevauchantes, paramètres estimés sur train uniquement.
- Métrique de comparaison H4 vs H6 : à définir avant de lancer un seul calcul (ex. amélioration de la calibration Wald cluster-robuste sur le même bucket médian qui a échoué).
- Nombre maximal de variantes testées à fixer à l'avance, avec correction pour comparaisons multiples si plus d'une variante est essayée.

**À créer** :
- `docs/codex/08-h6-conditionnelle.md` (même style pédagogique que 01–07), rédigé *après* le pré-enregistrement, pas avant.
- `src/risk/conditional.py` ou équivalent, séparé de `two_barriers.py` — H6 est une extension, pas un remplacement in-place de H2/H4 (qui restent la baseline falsifiée et publiée telle quelle).
- `tests/test_conditional.py`, écrit depuis le protocole pré-enregistré, pas depuis l'implémentation.

**Critère d'acceptation** : le pré-enregistrement existe en commit avant tout résultat H6 ; H4/H2 ne sont ni modifiés ni supprimés ; le FAIL réel reste visible dans le README à côté du nouveau travail H6, pas remplacé par lui.

---

## 4. Séparation risque / rentabilité — deux thèses, pas une

**Constat** : `-2 336 USD` est aujourd'hui un chiffre unique sans contexte comparatif — ni benchmark, ni décomposition, ni mesure de robustesse. Publier ce nombre seul en fait un argument de rentabilité par défaut (négatif, certes, mais toujours un raccourci).

**Action** — créer `docs/ECONOMICS.md` (nouveau document, séparé de `THESIS.md` qui reste dédié au risque de liquidation), couvrant au minimum :
- espérance par trade, décomposée (contribution TP / liquidations / frais / funding) ;
- taux de liquidation d'équilibre (calcul explicite du seuil ~9,1 % déjà dérivé dans l'audit, comme référence documentée plutôt que mention en passant) ;
- drawdown maximal, utilisation du cash, exposition simultanée, positions ouvertes en fin de période ;
- comparaison Buy & Hold, cash pur, et stratégie sans levier sur le même historique ;
- sensibilité à `L`, `s`, frais, slippage — sur couche d'entraînement séparée du jeu final, avec le même interdit que H4 : pas de sélection du meilleur `(L,s)` sur les données qui servent ensuite à publier un résultat hors-échantillon.

**Critère d'acceptation** : `ECONOMICS.md` existe, contient au moins un benchmark passif, et le README distingue clairement "résultat de risque (H1–H6)" de "résultat économique (ECONOMICS.md)" — ce sont deux verdicts, pas un seul.

---

## 5. Vérification exchange (avant tout paper trading proche production)

**À traiter en parallèle, pas bloquant pour 1–4, mais à ne pas oublier** : les `ASSUME` suivants doivent être confrontés à Binance ou à un compte démo avant qu'aucune version ne soit présentée comme prête pour du paper trading réel :
- MMR réelle et brackets (déjà marqué ASSUME, endpoint nécessite authentification) ;
- frais exacts ;
- source du mark/index price pour le funding ;
- comportement réel de liquidation et ADL ;
- données 1 minute pour vérifier l'ordre intra-barre (le modèle actuel infère, ne vérifie pas) ;
- slippage dépendant de la taille.

**Critère d'acceptation** : un tableau `ASSUME → vérifié/toujours ASSUME` dans `LIMITATIONS.md`, mis à jour au fur et à mesure, pas une simple mention.

---

## 6. Ordre de traitement recommandé

1. Section 1 (dette doc) — rapide, débloque la confiance dans tout le reste.
2. Section 2 (branche baseline) — à faire avant de toucher quoi que ce soit d'autre, protège le résultat audité.
3. Section 3 (H6, pré-enregistrement d'abord) et Section 4 (ECONOMICS.md) — en parallèle, sur branches séparées.
4. Section 5 — en tâche de fond, non bloquante.

**Rappel final au Producteur** : REV03 n'est pas une invitation à faire disparaître le FAIL H4. C'est le contraire — le FAIL est maintenant assez solide pour porter une vraie question de recherche (H6). Le succès de REV03 se mesure à la qualité du pré-enregistrement H6 et à la séparation propre risque/rentabilité, pas à un README plus flatteur.
