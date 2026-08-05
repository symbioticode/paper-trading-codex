
## REV02 — Révision actionnable pour Big Pickle (Producteur)

Chaque item suit le format du skill Critique (`PASS/FAIL/β=N`), avec correction des sur-affirmations de REV02 quand le code les contredit.

### 🔴 BLOQUANT — 1. Doublement du levier dans le PnL

**Point** : `Position.unrealized()` (`engine.py`) calcule `(entry − price) · qty · leverage`.
**Évidence contradictoire** : la dérivation H1 elle-même (`exchange_spec.py`, `docs/METHODS.md §3`) pose `E·qty/L + (E−liq)·qty = liq·qty·MMR` — **sans** multiplication par `L` sur le terme de PnL. `notional = qty·entry`, `margin = notional/L` confirment que `qty` est déjà l'exposition pleine (SOL) ; le PnL d'un future ne se multiplie pas une seconde fois par le levier.
**Le test ment aussi** : `test_pnl_take_profit_exact` encode `100.0` comme attendu `(100−98)·10·5` au lieu de `20.0` `(100−98)·10` — ce test a été écrit *depuis le code*, pas depuis H1 (violation producteur §6).
**Portée du dommage** : H5 (cohérence numéraire) passe quand même car ses tests ne vérifient qu'une auto-cohérence (equity = capital + Σnet_pnl), jamais une référence externe. **H4 n'est pas affecté** (la fréquence de liquidation ne dépend que de L et s, pas de qty). Mais tout PnL publié (+176 933 USD, README, THESIS §5) est invalide en l'état.
**Action Big Pickle** :
1. Trancher explicitement le sens de `qty` (déjà fait implicitement par H1 : coins, pas unités de marge).
2. Corriger `unrealized()` → `(entry − price) · qty` (retirer `· leverage`).
3. Réécrire les tests concernés **depuis H1**, pas depuis l'ancien code — y compris un test de non-régression qui aurait échoué sur l'ancienne formule.
4. Régénérer et republier tous les chiffres PnL (`04_validate_thesis.py --data real`, README, THESIS.md §5).
5. Marquer `TD-001` dans `docs/LIMITATIONS.md` le temps de la correction.

### 🟠 BLOQUANT MODÉRÉ — 2. `n_censored` ne mesure pas ce que W3/V7 promettent

**Point** : `validate_thesis` (thesis.py) itère uniquement sur `engine.trades` (positions déjà résolues) ; `n_censored` s'incrémente quand la fenêtre d'ouverture d'un trade *résolu* est hors de `wid_set` — pas quand une position reste ouverte en fin de run.
**Évidence** : les positions encore dans `engine.positions` à la fin (vraie censure au sens W3/V7) ne sont jamais comptées nulle part dans `ThesisReport`.
**Action Big Pickle** :
1. Ajouter un compteur distinct pour les positions réellement non résolues (`len(engine.positions)` en fin de run).
2. Renommer l'actuel `n_censored` en quelque chose comme `n_hors_fenetres` s'il garde son rôle actuel.
3. Écrire le test **depuis le texte de W3/V7**, avant de relire le code.

### 🟡 MINEUR — 3. Funding : "notionnel courant" documenté, notionnel figé implémenté

**Point** : E7 dit *"PnL funding = rate × notionnel courant"* ; le code utilise `pos.notional`, figé à l'ouverture, jamais réévalué au mark.
**Action** : soit corriger la docstring (*"notionnel d'ouverture, figé"*), soit implémenter le mark-to-market si c'est l'intention réelle — et déclarer le choix en `ASSUME` explicite (producteur §8), pas silencieusement.

### 🟡 MINEUR — 4. Frais de sortie sur notionnel d'entrée

**Point** : `exit_fee = pos.notional * taker_fee` utilise le notionnel d'entrée, pas `qty·exit_price`.
**Action** : déclarer l'approximation explicitement (producteur §8) avec borne d'impact chiffrée, ou corriger vers `qty·exit_price·taker_fee` si la fidélité au réel importe plus que la simplicité.

### ⚪ À REJETER — 5. "Resize non compté" (REV02 se trompe ici)

**Point** : REV02 affirme une contradiction doc/code sur `n_skipped_cash/cap`.
**Évidence contraire** : le docstring R5 de `runner.py` dit déjà explicitement *"skip uniquement si la qty résultante est nulle"* — le comportement actuel est documenté, pas un bug. **Ne pas corriger.** Optionnel : ajouter un compteur `n_resized` pour la transparence, non prioritaire.

### 🟢 DEBT VISIBILITY — 6. Docs en avance sur le repo

**Point** : `HYPOTHESIS.md`/README référencent `scripts/run_reproducible.sh`, `MANIFEST`, `flake.nix`, `scripts/validate_thesis.py`, `tests/test_liquidation.py`, `tests/test_ground_truth.py`, `tests/test_metrics.py` — absents de l'arborescence fournie (seuls existent `03_ground_truth.py`, `04_validate_thesis.py`, `test_exchange_spec.py`, `test_two_barrier.py`, `test_engine.py`).
**Action** : par principe #18 (Debt Visibility), soit renommer les références pour matcher l'existant, soit créer les artefacts manquants, soit marquer `TD-002 : reproductibilité déclarée en avance sur le repo — cible vXX — condition : avant publication externe`.

---

**Priorité d'exécution recommandée** : #1 (bloque toute crédibilité PnL) → #2 (bloque la lecture correcte de H4) → #6 (dette de traçabilité) → #3/#4 (précision) → #5 (aucune action requise, juste noter pour éviter une fausse alerte future).