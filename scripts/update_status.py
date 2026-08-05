#!/usr/bin/env python3
"""
update_status.py — Régénère la section Tests de docs/STATUS.md depuis la
sortie RÉELLE de pytest (REV03-1 §1).
================================================================================
Motif : STATUS.md était « régénéré manuellement » avec une sortie attendue,
recopiée — rien n'empêchait qu'il diverge silencieusement du HEAD au prochain
commit. Ce script exécute pytest et reconstruit la section Tests uniquement à
partir de la sortie capturée (comptage par `--collect-only -q`, résultat par
l'exit code de `python -m pytest tests/ -q`).

  Usage :
    python scripts/update_status.py           # régénère docs/STATUS.md
    python scripts/update_status.py --check   # exit 1 si le fichier commité
                                              # diffère d'une régénération fraîche

  Le reste de STATUS.md (résultats audités figés) est préservé tel quel : seuls
  les compteurs de tests sont régénérés.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "docs" / "STATUS.md"
TESTS = ROOT / "tests"
HEADING = "## Tests unitaires"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def collect_counts() -> tuple[list[str], dict[str, int], int]:
    """Comptage réel par fichier via `pytest --collect-only -q`.

    Sortie attendue : lignes `tests/test_<mod>.py: N` (format réel de pytest).
    """
    r = run([sys.executable, "-m", "pytest", str(TESTS), "--collect-only", "-q"])
    if r.returncode != 0:
        raise SystemExit(
            f"pytest --collect-only a échoué (exit {r.returncode}) — "
            f"ne pas régénérer sur une collection invalide.\n{r.stdout[-2000:]}"
        )
    counts: dict[str, int] = {}
    order: list[str] = []
    for line in r.stdout.splitlines():
        m = re.match(r"tests/test_([a-z0-9_]+)\.py:\s*(\d+)", line.strip())
        if m:
            mod = m.group(1)
            if mod not in counts:
                counts[mod] = 0
                order.append(mod)
            counts[mod] += int(m.group(2))
    if not order:
        raise SystemExit("Aucun test collecté — refuser de régénérer un compteur nul.")
    return order, counts, sum(counts.values())


def gate_pytest() -> None:
    """Le vrai test : `python -m pytest tests/ -q` doit passer (exit 0)."""
    r = run([sys.executable, "-m", "pytest", str(TESTS), "-q"])
    if r.returncode != 0:
        raise SystemExit(
            f"pytest FAIL (exit {r.returncode}) — STATUS.md ne doit pas "
            f"prétendre « passed » alors que les tests sont rouges.\n"
            f"{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
        )


def has_ci() -> bool:
    return any(ROOT.joinpath(".github", "workflows").glob("*.yml")) or any(
        ROOT.joinpath(".github", "workflows").glob("*.yaml")
    )


def render_section(order: list[str], counts: dict[str, int], total: int) -> str:
    files = ", ".join(f"`test_{m}` ({counts[m]})" for m in order)
    n = len(order)
    ci_note = (
        "garde-fou branché sur la CI."
        if has_ci()
        else "garde-fou MANUEL pour l'instant (pas de CI) — TD-005, "
        "cible de vérification datée dans docs/LIMITATIONS.md §5."
    )
    return (
        f"{HEADING}\n"
        "\n"
        f"- **Nombre de tests : {total}** ({n} fichiers `tests/test_*.py`), "
        "compté par `pytest --collect-only -q` (sortie réelle, pas recopiée).\n"
        f"- **Résultat réel capturé** (`python -m pytest tests/ -q`) : "
        "**exit 0** — tous les tests passent.\n"
        f"- Les {n} fichiers : {files}.\n"
        f"- **Régénération automatique** : `python scripts/update_status.py` ; "
        f"`python scripts/update_status.py --check` échoue si ce fichier n'est "
        f"pas à jour. {ci_note}\n"
        "\n"
    )


def replace_section(text: str, section: str) -> str:
    start = text.index(HEADING)
    nxt = text.index("\n## ", start + 1)
    return text[:start] + section + text[nxt + 1:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="ne pas écrire ; exit non-nul si STATUS.md commité "
                         "diffère d'une régénération fraîche")
    args = ap.parse_args()

    gate_pytest()
    order, counts, total = collect_counts()
    section = render_section(order, counts, total)

    current = STATUS.read_text()
    regenerated = replace_section(current, section)

    if args.check:
        if regenerated == current:
            print(f"OK — docs/STATUS.md à jour ({total} tests, exit 0).")
            return 0
        print(f"docs/STATUS.md OBSOLÈTE ({total} tests collectés) — "
              f"régénérez puis committez : python scripts/update_status.py")
        return 1

    STATUS.write_text(regenerated)
    print(f"docs/STATUS.md régénéré : {total} tests / {len(order)} fichiers "
          f"(pytest exit 0).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
