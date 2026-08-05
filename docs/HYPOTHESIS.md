# HYPOTHESIS.md — La thèse, ses énoncés testables, et comment la réfuter

> Ce document est **normatif** : toute affirmation de ce projet est soit (a) une
> définition, soit (b) une hypothèse testable, soit (c) un constat mesuré.
> Rien d'autre n'a le droit d'apparaître dans un README ou une leçon.
> Chaque hypothèse pointe vers un test qui peut **échouer**.

---

## 1. Objet du projet

Laboratoire pédagogique d'un **grid bot SHORT** sur perpétuel (Binance SOLUSDT),
dont l'ambition n'est pas de prédire les marchés mais de démontrer, avec une
méthode falsifiable, une proposition de **gestion du risque** :

> La distance d'une position SHORT à sa liquidation est calculable à partir du
> spec exchange. Le plafond de levier "sûr" qui en découle dépend de la
> volatilité, de la dérive et de la géométrie de la grille. Cette relation peut
> être **mesurée hors-échantillon** et confirmée ou réfutée avec des
> intervalles de confiance.

Le but pédagogique est atteint **si et seulement si** chaque étape du raisonnement
est vérifiable par un programme qui peut dire "non".

---

## 2. Nomenclature

| Terme | Définition |
|---|---|
| `E` | Prix d'entrée d'une position |
| `L` | Levier (notionnel / marge isolée) |
| `MMR` | Maintenance margin rate, taux de marge de maintenance (% du notionnel) |
| `s` | Espacement de grille (fraction du prix) = distance TP pour une position |
| `d` | Distance de liquidation au-dessus de l'entrée pour un SHORT, `d = (liq − E)/E` |
| `α` | Probabilité de liquidation cible (budget de risque) |
| `P(liq)` | Probabilité qu'une position SHORT soit liquidée avant son take-profit |
| `μ, σ` | Dérive et volatilité journalières du log-prix, estimées |
| `H` | Horizon de vie attendu d'une position |

---

## 3. Hypothèses testables

Chaque hypothèse a un identifiant, un test précis, et un critère d'échec
explicite. **Une hypothèse est confirmée quand le test passe ; sinon elle est
réfutée — c'est un résultat, pas un bug.**

### H1 — Formule de liquidation dérivée du spec exchange

> **Énoncé.** En marge isolée, pour un SHORT, le prix de liquidation exact est
>
> ```
> liq = max( E·(1 + 1/L) / (1 + MMR),  E )
> ```
>
> et la distance de liquidation est `d = (1/L − MMR) / (1 + MMR)`.

**Dérivation (docs/METHODS.md §3).** À la liquidation, le solde de marge
(marge initiale + PnL non réalisé) doit égaler la marge de maintenance :
`E·qty/L + (E − liq)·qty = liq·qty·MMR`.

**Test.** `tests/test_exchange_spec.py` :
- propriétés algébriques (monotonie en `L` et `MMR`, bornes, cas limites `L→∞`, `MMR→0`) ;
- cohérence avec la formule "approx" historique `E(1 + 1/L − MMR)` à l'ordre 1 en `MMR` ;
- seuil de non-viabilité : si `1/L < MMR`, la position ne peut pas exister (liq = E).

**Critère d'échec.** toute propriété contredite par le code.

### H2 — Vérité terrain : la formule de probabilité est exacte sous GBM

> **Énoncé.** Soit un prix suivant un mouvement brownien géométrique de
> paramètres `(μ, σ)` (journaliers). Une position SHORT ouverte avec barrière de
> TP à `s` en dessous et de liquidation à `d` au-dessus a une probabilité de
> liquidation
>
> ```
> P(liq) = (1 − e^{2μa/σ²}) / (e^{−2μb/σ²} − e^{2μa/σ²}),   a = −ln(1−s), b = ln(1+d)
> ```
>
> (probabilité de toucher la barrière haute avant la basse — forme fermée du
> premier passage à deux barrières du mouvement brownien arithmétique).
> `a = −ln(1−s) = ln(E/TP)` est la distance logarithmique EXACTE au TP (le moteur
> ferme à `TP = E·(1−s)`) ; à l'ordre 1 en `s`, `a ≈ s`. La forme exacte est
> exigée par le test de Monte Carlo (`test_two_barrier.py`) qui discriminerait
> les deux à mieux que 1 %.

**Test.** `tests/test_two_barrier.py` (Monte Carlo) et `scripts/03_ground_truth.py` :
- Monte Carlo de `N = 10 000` trajectoires GBM avec barrières absorbantes ;
- fréquence observée `p̂` vs `P(liq)` prédit ;
- test binomial bilatéral : rejet si `|p̂ − P| > 5·√(P(1−P)/N)` (≈ 5σ).

**Critère d'échec.** écart hors tolérance → la formule ou sa programmation est
fausse. C'est l'**ancre anti-contradiction** : si H2 échoue, rien d'autre ne peut
être cru.

### H3 — Le plafond de levier est l'inverse de H2

> **Énoncé.** Pour un budget de risque `α` donné, le plafond de levier sûr est
>
> ```
> L*(α, s, μ, σ) = max{ L : P(liq)(L, s, μ, σ) ≤ α }
> ```
>
> (défini sur le domaine valide `1/L > MMR` ; `L* = ∅` si même `L→1⁺` dépasse
> le budget). Monotonies **constatées** et testées :
> - **croissant en `|μ|` quand la dérive est baissière** (`μ < 0`) : le SHORT est
>   structurellement protégé par un bear market ;
> - **décroissant en `σ` pour `μ ≤ 0`** (dérive baissière ou nulle) ; pour
>   `μ > 0`, au contraire, `L*` **croît** en `σ` : la dérive positive rend la
>   liquidation plus probable à faible volatilité, où elle domine le bruit. La
>   monotonie en `σ` change donc de signe avec `μ` (à `μ = 0`, `L*` est constant
>   en `σ` car `P(liq) = a/(a+b)` n'en dépend pas).

**Test.** `tests/test_two_barrier.py` : monotonies vérifiées sur grille de
paramètres (pour `μ ≤ 0` puis `μ > 0` séparément) ; résolution numérique de
`L*` cohérente avec H2 ; cas `L* = ∅`.

**Critère d'échec.** toute non-monotonie dans la zone de paramètres valide
(`1/L > MMR`, `s > 0`).

### H4 — Prédiction hors-échantillon (la thèse au sens strict)

> **Énoncé.** Sur des données réelles découpées en fenêtres glissantes
> indépendantes (W1–W3), si l'on estime `(μ̂, σ̂)` sur une fenêtre
> d'apprentissage puis que l'on fait tourner la stratégie sur la fenêtre de test
> suivante avec le levier `L` fixé, la **fréquence de liquidation observée**
> doit être cohérente avec la probabilité prédite `P(liq)`, globalement et par
> bucket de régime.

**Deux corrections de mesure apportées en J6 (documentées, mesurées) :**

1. **PRÉDICTION DISCRÈTE (granularité horaire).** Le simulateur surveille les
   barrières barre à barre (`high`/`low` OHLC horaires, engine E6), pas en
   temps continu. La formule continue H2 sous-estime le risque à monitoring
   grossier (mesuré sur le contrôle GBM : `P_continue ≈ 0.108` vs
   `P_observé ≈ 0.111` à `L=5, s=2%, σ=2,5%`). La prédiction H4 est donc le
   Monte Carlo **discret** `simulate_two_barrier_bars` (pont brownien
   intra-barre, sémantiques exactes du moteur) — la formule continue H2 reste
   la référence du processus continu, testée séparément par
   `03_ground_truth.py`.
2. **TEST CLUSTER-ROBUSTE (dépendance intra-fenêtre).** Les positions d'une
   même fenêtre partagent le MÊME chemin de prix : leurs issues ne sont pas
   indépendantes, et le CI binomial naïf (Wilson) sur-réjette. Mesuré sur 20
   seeds du contrôle GBM : buckets rejetés dans ~11/20 cas au lieu de ~5%.
   Le test H4 est un **Wald cluster-robuste, cluster = fenêtre**, avec la
   variance sandwich de la dispersion OBSERVÉE (indépendante du modèle — un
   sandwich sur les résidus `p̂_w − P̂_w` serait aveugle à un biais
   systématique) :
   `V_rob = (W/(W−1))·Σ_w (n_w/N)²·(p̂_w − p̂)²`, acceptation si
   `|p̂ − P̂| ≤ t(0,975, W−1)·√V_rob`.
    **Calibration REV2 (test corrigé, TD-004 clôturé).** La calibration initiale
    (J6, moteur AVANT la correction REV2 du PnL : global 0/20, buckets 4/60,
    PASS ≈ 80 % = `0.95⁴`) était **invalide** : le PnL gonflé gardait la grille
    solvable, l'échantillon du contrôle n'était jamais tronqué. Moteur corrigé,
    la sur-rejection re-mesurée avait deux causes distinctes :
    (1) **contamination de portefeuille** — la grille SHORT perd sur le GBM à
    dérive positive ; à 30 000 h le prix croît ≈ 400×, R5 (cash/notionnel)
    tronque l'échantillon ; (2) **effondrement de `V_rob`** — avec 2–3 fenêtres
    par bucket aux fréquences quasi identiques, `V_rob ≈ 0` et toute dérive
    rejette (margin 0.001 contre un bruit binomial ~0.024).
    **Correctif (TD-004) : plancher binomial intra-fenêtre**
    `V = max(V_rob, V_floor)` avec `V_floor = Σ_w (n_w/N)²·p̂_w(1−p̂_w)/(n_w−1)`
    (composante d'échantillonnage intra-fenêtre, bien estimée, N−W ddl).
    **Calibration re-mesurée, contrôle non contaminé (capital 1 M, skips=0) :**
    - 5 000 h, 20 seeds : **20/20 PASS** (global 20/20 ; buckets non testables,
      3 fenêtres → W<2 par bucket) ;
    - 10 000 h, 10 seeds : **9/10 PASS** (global 10/10, buckets 29/30 ≈ nominal) ;
    - 30 000 h, 20 seeds : global **20/20**, buckets 57/59, mais PASS 5/20 —
      les 15 échecs sont UNIQUEMENT la condition V6 « aucun skip » (contamination
      de portefeuille) ; le test de géométrie passe 20/20 malgré la troncature.
    Un FAIL du global (ou d'un bucket sans skip) est donc re-calibré à ~95 % ;
    un FAIL dû aux skips signale une contamination de portefeuille à traiter
    à part. Conséquence documentée : les buckets à W=2 (marge = t(1)·√V_floor
    ≈ 12.7·SE) sont quasi non-testables — le global (W=8+) porte la puissance.

**Test.** `scripts/04_validate_thesis.py` :
- construction des fenêtres indépendantes (W1–W3) ; estimation `(μ̂, σ̂)` sur
  l'apprentissage (M1) ; prédiction discrète par fenêtre (V3) ;
- agrégation par bucket de volatilité d'apprentissage (terciles, V4) ;
- comparaison observé vs prédit par **Wald cluster-robuste à 95%** (V5) ;
- sortie `PASS` / `FAIL` chiffrée ; PASS exige global ET tous les buckets
  non vides acceptés ET aucun skip cash/cap (R5).

**Résultats (régénérés par le script, venv sol-grid-lab) :**
- Contrôle GBM (modèle vrai par construction), seed 60 : **PASS** — global
  `p̂=0.1245` vs `P̂=0.1206` (±0.014) ;
- Données réelles Binance SOLUSDT perp 1h (51 594 barres) : **FAIL — H4
  réfutée sur le régime de volatilité médiane**. Global `p̂=0.1100` vs
  `P̂=0.1236` (±0.0149) OK ; buckets vol `0.1115/0.0845/0.1242` vs prédits
  `0.1123/0.1245/0.1277` : bucket vol 1 **HORS** (`|p̂−P̂| = 0.040` > marge
  cluster-robuste `0.0196`), buckets 0 et 2 OK. Résultat reproductible
  (2 exécutions identiques, exit 1). Les positions du régime de volatilité
  médiane se liquident **nettement moins** que prédit.

**Critère d'échec.** fréquence observée hors de la marge cluster-robuste →
la thèse est réfutée sur ce régime, et ceci est **publié comme résultat**, pas
masqué. **Le FAIL réel l'active** : H4 est réfutée sur le bucket de volatilité
médiane des données réelles ; elle survit sur le global et les régimes 0 et 2.
C'est un résultat publié, qui pointe la piste d'investigation suivante
(dépendance conditionnelle au trigger → **H6**, pré-enregistrée ; modèle de
pont intra-barre, sélection du couple L/s — hors périmètre de REV03).

### H5 — Cohérence du numéraire

> **Énoncé.** Tous les PnL et ratios de risque sont calculés en **USD**. Les
> rendements exprimés dans une autre unité (SOL) ne sont jamais utilisés comme
> métrique principale. Le PnL en USD d'un portefeuille est invariant au choix
> de la période de comptabilisation (pas de double comptage de frais/funding).

**Test.** `tests/test_runner.py` et `tests/test_engine.py` : invariance des PnL cumulés USD entre
comptabilisation barre à barre et fermeture en une seule étape ; le PnL d'une
position fermée = PnL brut − frais d'entrée − frais de sortie − funding payé.

**Critère d'échec.** désaccord de PnL à `1e-9` près → bug.

### H6 — La liquidation est conditionnelle à la morphologie du trigger, pas seulement à `(μ, σ)`

> **Énoncé (REV03 §3).** La probabilité de liquidation conditionnelle à la
> morphologie du trigger G3 et au régime précédent est mieux calibrée
> hors-échantillon que la prédiction fondée uniquement sur `μ` et `σ`.

**Constat déclencheur (cité tel quel de `docs/ENQUETE_FAIL.md`, ne pas
édulcorer).** *« L'entrée en position n'est pas un instant neutre — elle suit
systématiquement un trigger de momentum (G3), et les données réelles montrent
un pullback d'exhaustion majoritaire après ce trigger (56 % de TP atteint sous
6h, 76 % sous 24h). Le modèle iid actuel (`P(liq | μ, σ, L, s)`) ne capture
pas cette structure conditionnelle, ce qui est la lecture la plus probable du
FAIL du bucket médian. »* En chiffres (réel vs pont brownien) : `P(min low 6h
≤ −2 %) = 56 %`, `P(min low 24h ≤ −2 %) = 76 %` (modèle 65 %), low moyen de la
barre suivante `−1.15 % à −1.55 %` (60–77 % de la distance TP) vs `~−0.7 %`
(modèle), `P(liq)` à vie sur les mêmes entrées `0.0875` vs `0.2250` (modèle).

**Statut : PRÉ-ENREGISTRÉE (REV03 §3).** Aucun calcul H6 avant ce commit —
règle producteur : jamais de sélection de variable après avoir vu le résultat.
Le pré-enregistrement est le contrat de l'hypothèse ; l'implémentation se fera
sur `feature/h6-conditional-liq`, H4/H2 restant la baseline publiée telle
quelle.

**Pré-enregistrement (fixé à l'avance, non modifiable sans nouvelle REV) :**
- *Variables candidates autorisées* (limitées à cette liste) : taille du spike
  déclencheur (excès du high au-dessus de l'ancre), position du close dans la
  chandelle, taille des mèches, momentum des heures précédentes, distance à
  l'ancre, `μ`/`σ` locaux, fréquence récente des triggers, comportement de la
  barre suivant le trigger.
- *Découpage temporel* : identique en esprit à H4 — fenêtres non chevauchantes,
  paramètres estimés sur train uniquement, prédiction sur test hors-échantillon.
- *Métrique de comparaison* : amélioration de la calibration du Wald
  cluster-robuste sur le **même bucket vol 1** qui a échoué en H4 (global inchangé).
- *Nombre maximal de variantes* : **3** ; au-delà, correction de Bonferroni
  (α/k) sur la métrique. Toute variante testée doit être listée ici avant son
  calcul.

**Test.** `tests/test_conditional.py` (écrit depuis ce pré-enregistrement, pas
depuis l'implémentation) + `src/risk/conditional.py` (extension, ne modifie ni
`two_barriers.py` ni le pipeline H4).

**Critère d'échec.** la prédiction conditionnelle ne réduit pas l'écart du
bucket vol 1 hors-échantillon par rapport à H4, ou la réduction n'est pas
significative au seuil fixé (avec correction pour comparaisons multiples) → H6
réfutée. **H4 reste réfutée et publiée telle quelle, H6 ne la remplace pas.**

---

## 4. Ce qui n'est PAS une hypothèse (et ne sera jamais présenté comme tel)

- "Ce bot est rentable" — la rentabilité est un **constat mesuré** sur une
  fenêtre donnée, jamais une promesse.
- "Le levier 8x est sûr quand σ < 3.5%" — remplacé par H3/H4 qui le sont
  paramétrées par `α` et testées hors-échantillon.
- Toute assertion sur des données **synthétiques** non marquées comme telles.

---

## 5. Reproductibilité

> **TD-002** (dette de traçabilité, REV02 #6 ; replanifiée REV03 §1) :
> `run_reproducible.sh`, `MANIFEST` et `flake.nix` sont déclarés ici mais
> **absents du repo** — la reproductibilité réelle passe aujourd'hui par
> `activate.sh` (venv) + `python -m pytest tests/ -q` + `scripts/03/04_validate_thesis.py`.
> **TODO explicite, cible 2026-09-30** : aligner les artefacts avant toute
> publication externe (voir `docs/LIMITATIONS.md` §5).

- Toute donnée (réelle ou synthétique) a une provenance : `metadata.json`
  (source, intervalle, plage, horodatage, sha256 du fichier).
- Toute sortie est régénérable par `scripts/run_reproducible.sh --verify`, qui
  doit produire un diff vide sur les artefacts commités (voir `MANIFEST`).
- Les versions Python/dépendances sont épinglées (pyproject + flake.nix).

---

## 6. Lecture de ce document

Si vous voulez **réfuter** ce projet : exécutez `scripts/04_validate_thesis.py`.
S'il passe, la thèse survit sur les fenêtres testées — avec les limites
déclarées dans `docs/LIMITATIONS.md`. S'il échoue, le projet vous dira
précisément quel énoncé (H1…H5) est en défaut, avec quel écart et quelle
significativité.
