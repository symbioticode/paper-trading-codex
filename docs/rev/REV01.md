Rien sur le disque du container — ces documents sont dans le project knowledge (uploadés dans le projet Claude.ai), pas sur le filesystem. Laisse-moi les chercher directement.## Préalable — socle de connaissance produit

`β=N` sur : mécanisme ADL Binance et son effet sur PnL simulé — non vérifié dans le livrable, non mentionné dans `exchange_spec.py` ni `LIMITATIONS.md` (à confirmer). Je juge donc H1/H5 sans référence à l'ADL ; toute liquidation partielle en cascade réelle reste hors du modèle testé ici, pas seulement hors de ma vérification.

## Checklist (bloquants et non-bloquants)

**État/Logique (signature)**
PASS — `ShortGridStrategy.on_bar` est pure/déterministe, ne lit aucun état externe caché ; `Position`/`cash_usd` vivent dans `SimulationEngine`, séparés proprement de la stratégie.

**Liquidation = arrêt**
PASS — `_liquidate` retire la position (`self.positions.remove(pos)`) et `on_bar` traite liq (high) avant TP (low) dans la même barre, cohérent avec E6 documenté. Aucune ligne de trading ne suit sans retrait immédiat.

**Frais doubles**
PASS — commentaire explicite "AXIOME H5" + `net = delta_cash − pos.entry_fee` où `entry_fee` n'est débité qu'une fois du cash à l'ouverture et soustrait une fois du net à la clôture. Vérifié sur `test_funding_credite_le_short_dans_le_runner` : `1000·5·5% − 1000·0.0002 − 1000·0.0004 + 1.0` correspond à frais entrée+sortie comptés une fois chacun.

**FAIL — Slippage sur sortie TP (contradiction convention vs code)**
Point : E8 documente *"sortie = prix cible·(1 + slip)"*, s'appliquant a priori à toute sortie hors liquidation.
Évidence : `on_bar` appelle `self._close(pos, exit_price=pos.tp_price, ...)` sans aucun ajustement de `slip_bps` sur le TP. Seuls `test_slippage_entree_short` et `test_liq_prix_reflete_slippage` existent — aucun test ne couvre le slippage à la sortie TP, ce qui aurait dû être détecté par la règle producteur §6 (test écrit depuis la spec).
Cas précis qui casse la proposition : avec `slip_bps=50`, une position TP à `entry·(1−s)` se ferme actuellement exactement à ce prix, alors que la doc promet un TP moins favorable (`tp_price·(1+slip)`), ce qui **surestime le PnL net réalisé de chaque TP** de manière systématique. Reproductible en instrumentant `eng.trades[0].exit` après un cycle TP avec `slip_bps>0`.
→ Soit c'est un choix voulu (TP = ordre limite, pas de slippage) et alors E8 est mal rédigé et doit être corrigé pour dire "slippage seulement à l'entrée" ; soit c'est un oubli d'implémentation. Dans les deux cas c'est une approximation non déclarée au sens producteur §8 : à trancher explicitement avant la prochaine mesure H4/H5, car ça biaise le PnL constaté (mesure hors-thèse mais publiée dans les rapports).

**Benchmark Buy&Hold / plafond**
β=N — non vu dans les fichiers consultés ; je n'ai pas la preuve que ces benchmarks existent dans cette version. À transmettre si le livrable en contient.

**Contrainte d'exchange (MMR)**
PASS avec réserve déclarée — `TIER_1_MMR = 0.005` est marqué `ASSUME` avec cible de vérification (`leverageBracket`, 401 sans clé au 2026-08-04) au lieu d'être présenté comme `OBSERVE`. C'est exactement la discipline attendue par producteur §3. Point d'attention : cet ASSUME conditionne H1 → H4 entièrement ; si la vraie MMR SOLUSDT diffère, toute la chaîne de calibration change. Ce n'est pas un défaut du livrable, mais un risque de propagation à surveiller — vaudrait la peine d'un test de sensibilité (±X% sur MMR tier1 → impact sur `p̂/P̂`).

**Résultat "trop propre"**
PASS — PASS-rate théorique ≈0.95⁴≈0.81 documenté et mesuré, pas de score suspect (>95% ou <1% d'erreur) relevé dans les chiffres cités (GBM p̂=0.1245 vs P̂=0.1206 ±0.014 ; réel p̂=0.110 vs P̂=0.124 ±0.023). Pas d'alerte fuite de données ici.

**β=N — Indépendance des clusters (fenêtres) au sens du test de Wald**
Point : W3 permet à une position ouverte en fenêtre `i` d'être suivie jusqu'à résolution même après `test_end`, potentiellement dans le chemin de prix de la fenêtre `i+1`.
Évidence : `tag_opening_indices` assigne la position à sa fenêtre d'ouverture (correct pour l'indépendance *entre* fenêtres au sens strict), mais je n'ai pas vu de test vérifiant que le clustering Wald (`validate_thesis`/V5) traite bien ces positions "à cheval" sans double influence sur deux buckets adjacents (ex. via la vol_train du bucket voisin si elle est calculée sur une fenêtre qui inclut la queue de résolution).
Ce qu'il faudrait vérifier et qui : le Producteur, en montrant explicitement qu'aucune statistique de la fenêtre `i+1` (bucket, μ̂/σ̂) n'utilise des barres postérieures à `test_start` de `i+1` qui contiennent la résolution d'une position ouverte en `i`. Si déjà garanti par construction (barres de test non réutilisées pour l'estimation), le dire et citer où.

## Synthèse

Un FAIL bloquant sur l'axe "Frais/PnL net" (slippage TP non appliqué malgré la doc E8) — ceci invalide la mesure de PnL net telle quelle jusqu'à clarification/correction, même si la mécanique de liquidation et le non-double-comptage des frais sont solides par ailleurs. Le reste de la structure (H1 dérivation, calibration Wald sur contrôle GBM, discipline ASSUME/OBSERVE) est du travail sérieux et bien tracé — la contradiction trouvée est ponctuelle, pas structurelle.