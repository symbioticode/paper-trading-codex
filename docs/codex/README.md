# Codex pédagogique 01..08

> Sept leçons, une par journée du projet. Chaque leçon est autonome : une
> question, la méthode, le piège qui s'est réellement présenté (avec sa
> correction), et ce qu'il faut retenir. Le PnL n'y apparaît que comme un
> **constat mesuré**, jamais comme un argument de performance.
>
> Contexte complet : `docs/THESIS.md` (fondements) et `docs/METHODS.md`
> (dérivations). Les fichiers cités sont dans `src/`, `scripts/` et `tests/`.

| # | Leçon | Question traitée |
|---|---|---|
| 01 | [Le contrat falsifiable](01-le-contrat-falsifiable.md) | Comment écrire un projet de trading qu'on ne peut pas se mentir à soi-même ? |
| 02 | [H1 : la liquidation, dérivée pas mémorisée](02-h1-liquidation.md) | D'où vient réellement le prix de liquidation ? |
| 03 | [H2 : le premier passage à deux barrières](03-h2-premier-passage.md) | Quelle est la probabilité de toucher une barrière avant l'autre ? |
| 04 | [H3 : le plafond de levier, l'inverse de la probabilité](04-h3-plafond-levier.md) | Comment choisir le levier pour un budget de risque donné ? |
| 05 | [Le simulateur et les biais de mesure](05-simulateur-biais.md) | Pourquoi un backtest ment, et comment l'empêcher de mentir ? |
| 06 | [Calibrer le test avant de croire](06-calibrer-le-test.md) | Pourquoi le test « classique » rejetait 3× trop souvent ? |
| 07 | [La validation hors-échantillon](07-validation-hors-echantillon.md) | Que prouve réellement un PASS ? Et un FAIL ? |
| 08 | [H6 : pré-enregistrer une hypothèse conditionnelle](08-h6-conditionnelle.md) | Que faire d'un FAIL robuste, sans réparer H4 ni tricher ? |

## Comment lire le codex

Chaque leçon commence par un **piège** — un raisonnement naïf plausible qui
s'est révélé faux. La méthode est ensuite construite *contre* ce piège. La
section **Mesuré dans le projet** donne les chiffres réels (pas des exemples
inventés). La section **À retenir** tient en une phrase.

**Prérequis minimal** : fractions, logarithme, moyenne/écart-type, notion de
probabilité et d'intervalle de confiance. Le reste est dérivé dans la leçon.
