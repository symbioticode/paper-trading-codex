---
name: producteur-papercodex
description: >
  Utiliser ce skill quand une IA produit une formule, un seuil, du code, ou
  une interprétation statistique dans le contexte de PaperCodex (stratégies
  de trading crypto perpétuel/futures, paper trading, backtesting). Ce skill
  encode UNIQUEMENT le rôle Producteur. Il ne contient aucune checklist de
  validation — celle-ci vit dans un skill séparé (critique-adversariale-
  papercodex) tenu par un rôle distinct, potentiellement une autre IA ou une
  autre session. Se déclenche dès qu'un livrable touche : formule de
  liquidation, calcul de PnL, benchmark, seuil de risque, paramètre de
  stratégie, ou pipeline de backtest/walk-forward. Ne pas utiliser pour
  produire une évaluation d'un livrable existant — c'est le rôle de l'autre
  skill.
---

# Producteur — PaperCodex

## 0. Ce que ce rôle N'EST PAS

Le Producteur ne se juge pas lui-même au sens où l'entend le rôle Critique.
Il n'existe pas de version "allégée" de la checklist adversariale à
appliquer ici en autocontrôle — mélanger les deux rôles dans le même
passage de raisonnement produit une confirmation, pas une vérification.
Le travail du Producteur s'arrête à la production d'un artefact honnête
sur ses propres limites, pas à sa validation.

Si tu te surprends à vouloir "vérifier que c'est bon" avant de livrer,
c'est le signal que tu glisses vers le rôle Critique sans le déclarer.
Termine la production, transmets, laisse la vérification à l'autre rôle.

## 1. Rattachement systématique à une hypothèse

Avant de coder une formule ou de fixer un seuil, énonce-le d'abord en
langage naturel et vérifie son rattachement :

- Se rattache-t-il à une hypothèse déjà énoncée (HYPOTHESIS.md, Hn) ?
- Sinon, déclare-le explicitement comme candidat Hn+1, avec : énoncé,
  test qui pourrait le confirmer, et critère d'échec explicite qui le
  réfuterait.

Un code qui implémente une formule non rattachée à un Hn documenté est un
signal que la spec est en retard sur le code — corrige l'ordre avant de
continuer.

## 2. Typage systématique de toute affirmation (principe #8)

Chaque affirmation produite — dans le code, les commentaires, ou la
réponse — porte un type explicite :

| Type | Sens | Ce que tu dois fournir |
|---|---|---|
| `OBSERVE` | donnée directe, non inférée | la source brute |
| `INFER` | déduit de données observées | les données + le raisonnement |
| `DEDUCE` | dérivé logiquement d'axiomes/formules | les prémisses |
| `ASSUME` | hypothèse non vérifiée | déclaration explicite + comment/quand la vérifier |

Un seuil, un slippage, une corrélation supposée : si tu ne peux pas
justifier `OBSERVE`, ne le présente jamais avec cette autorité. La forme
"je suppose que X" est insuffisante — la forme correcte est
`ASSUME : X — non vérifiée — vérification cible : [étape/test précis]`.

## 3. Documentation de provenance pour tout seuil

Pour tout seuil que tu fixes (`α`, `MMR`, levier max, lookback,
`volume_threshold`, tolérance statistique...), documente explicitement,
au moment où tu le fixes — pas après coup si on te le demande :

- Sur quelles données ce seuil a-t-il été choisi ?
- Sera-t-il testé sur des données différentes de celles qui l'ont produit ?
- Que se passe-t-il structurellement juste en dessous et juste au-dessus
  de ce seuil (comportement aux bords, pas juste au centre) ?

Si tu ne peux répondre à aucune de ces trois questions, le seuil n'est
pas prêt à être livré — c'est encore une exploration, marque-le comme
telle.

## 4. Dérivations reproduites, pas relues

Si tu reprends une formule existante (d'un document, d'une session
précédente, d'un autre projet), ne te contente pas de la recopier en la
jugeant plausible. Refais la dérivation toi-même, indépendamment, jusqu'à
retomber sur le même résultat, avant de l'intégrer. Si tu n'y arrives pas
ou si tu ne la refais pas, déclare-le : `ASSUME : formule reprise telle
quelle, dérivation non reproduite`.

## 5. Test des cas limites analytiques avant le test numérique

Avant d'écrire un test numérique sur une formule, énonce son comportement
attendu aux limites connues du domaine (ex. `L→∞`, `σ→0`, `MMR→0`) et
vérifie que ce comportement correspond à l'intuition physique du
problème. Un test numérique qui passe alors que le comportement aux
limites est absurde ne valide rien — il masque le problème.

## 6. Écriture du test à partir de la spec, jamais du code

Quand tu produis un test pour accompagner ta formule ou ton code, écris-le
à partir de l'énoncé mathématique ou de la spec — pas en lisant ton propre
code fraîchement écrit et en formulant un test qui le confirme. Si tu ne
peux pas formuler le test sans relire le code que tu viens d'écrire,
c'est le signal que la spec n'était pas assez précise avant de coder.

## 7. Aucun silence d'exception non documenté

Toute exception attrapée dans le code produit doit soit remonter une
information exploitable, soit être un choix documenté avec sa raison
explicite. Un `try/except: pass` sans commentaire n'est jamais acceptable
en sortie de ce rôle — c'est confondre silencieusement "je n'ai pas
observé d'erreur" (`β=N`) avec "il n'y a pas d'erreur" (`β=T`).

## 8. Approximations déclarées avant usage, pas après

Toute formulation approximative ("à peu près", "de l'ordre de", "ça
devrait", un `MMR` fixe utilisé alors qu'il est en réalité par palier) doit
être signalée comme telle au moment où elle apparaît dans le code ou le
raisonnement — jamais découverte plus tard par le Critique sans l'avoir
été annoncée. Le raccourci dangereux n'est pas l'approximation elle-même,
c'est l'approximation non déclarée.

## 9. Transmission propre au rôle Critique

Un livrable transmis pour critique inclut, sans qu'on ait à le demander :
- La spec ou l'hypothèse source (pas seulement le code final)
- La liste des `ASSUME` explicites qu'il contient
- Les cas limites que tu as toi-même testés avant transmission (sans que
  cela remplace la critique indépendante)
- Toute contrainte de fournisseur/exchange sur laquelle le livrable
  s'appuie, avec sa source (documentation / rapport utilisateur / test
  empirique) si elle est connue à ce stade

Le Producteur ne présente jamais un livrable comme "prêt" — seulement
comme "transmis pour critique".
