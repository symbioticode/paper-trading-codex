# 01 — Le contrat falsifiable

> **Question** : comment écrire un projet de trading qu'on ne peut pas se
> mentir à soi-même ?
> **Fichiers** : `docs/HYPOTHESIS.md` §1 ; `tests/` ; `scripts/`.

## Le piège

« Ce bot est rentable. » « Le levier 8x est sûr quand la volatilité est basse. »
Ce sont des phrases *confortables* : elles se vérifient par l'intonation, pas
par un programme. Le problème n'est pas qu'elles soient fausses — c'est qu'elles
ne peuvent pas être **démontrées fausses**. Une affirmation qui ne peut échouer
à aucun test n'apporte aucune information : elle est compatible avec tout.

Le retour d'expérience des petits bots est cruel : un backtest « qui marche »
peut rester mauvais pendant des mois, jusqu'à ce qu'on découvre un bug de frais
compté deux fois, un décalage d'index, ou une entrée exécutée à un prix que
personne n'aurait obtenu.

## La méthode : trois catégories, rien d'autre

Toute affirmation du projet doit être classable dans **exactement une** de ces
trois cases :

| Catégorie | Définition | Exemple du projet |
|---|---|---|
| (a) Définition | Convention posée, non discutable dans le projet | « Marge isolée = notionnel / levier » |
| (b) Hypothèse | Énoncé testable **avec un critère d'échec** | « La fréquence de liquidation est prévisible à ±t·√V » |
| (c) Constat mesuré | Résultat d'une mesure, daté, régénérable | « PnL −2 336 USD sur 3 256 trades » |

La règle d'or : **une hypothèse n'existe que si on peut écrire à l'avance ce
qui la réfuterait.** Dans ce projet, chaque hypothèse H1…H5 porte un test, et
le test a une condition de rejet chiffrée. Un échec est un **résultat publié**,
pas un bug qu'on va réparer en cachette.

## Mesuré dans le projet

La meilleure preuve que la règle n'est pas cosmétique : quand la revue externe
(REV1) a trouvé que le moteur fermait le take-profit sans appliquer le slippage
pourtant documenté, la correction a été **documentée, chiffrée comme sans impact
(slip=0), et verrouillée par un test** — pas appliquée discrètement. Le
protocole a fonctionné parce que la phrase « sortie = prix cible·(1+slip) »
était une *convention écrite* qui pouvait être confrontée au code.

## À retenir

> Une affirmation qui ne peut pas échouer n'apporte aucune information.
> Écrire d'abord ce qui la réfuterait, ensuite seulement la mesurer.
