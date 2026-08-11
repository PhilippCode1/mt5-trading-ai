"""Die juengsten Samples duerfen nicht aus dem Test fallen.

``fold_size = n // k`` schneidet ab. Bei ``n % k != 0`` endete der letzte Fold
vor dem Datenende, und die **juengsten** Samples wurden nie getestet -- bei
n=100/k=7 die Indizes 98-99, bei n=97/k=5 die Indizes 95-96.

Das ist kein Randfall: in einer Zeitreihe sind die juengsten Beobachtungen die
entscheidungsrelevantesten. Ein Walk-Forward, der sie auslaesst, misst die
Vergangenheit und schweigt ueber die Gegenwart. Ohne den Fix schlagen die ersten
drei Testgruppen fehl (15 von 20); die Leckage-Gegenprobe bleibt gruen.

Hinweis zur Umzugskorrektur: ``purge_ms``/``embargo_ms`` sind jetzt pflichtig.
Die Abdeckungstests waehlen bewusst und sichtbar ``0``; nur so misst der Test die
reine Abdeckung, nicht das Sperrband.
"""

from __future__ import annotations

import pytest
from mastertrade.backtest.splits import (
    Range,
    purged_kfold_embargo_indices,
    purged_walk_forward_indices,
    walk_forward_indices,
)

# (n, k) -- jeweils mit n % k != 0, also genau die Faelle, die abschnitten.
UNEVEN = [(100, 7), (97, 5), (50, 3), (10, 3), (101, 4)]


def _ranges(n: int) -> list[Range]:
    return [Range(i * 10, i * 10 + 9) for i in range(n)]


def _tested(splits: list[tuple[list[int], list[int]]]) -> set[int]:
    return {j for _, test in splits for j in test}


@pytest.mark.parametrize("n,k", UNEVEN)
def test_purged_walk_forward_reaches_the_last_sample(n: int, k: int) -> None:
    tested = _tested(
        purged_walk_forward_indices(_ranges(n), k, purge_ms=0, embargo_ms=0)
    )
    assert max(tested) == n - 1, f"juengste {n - 1 - max(tested)} Samples nie getestet"


@pytest.mark.parametrize("n,k", UNEVEN)
def test_purged_kfold_reaches_the_last_sample(n: int, k: int) -> None:
    tested = _tested(purged_kfold_embargo_indices(_ranges(n), k, 0.0, purge_ms=0))
    assert max(tested) == n - 1


@pytest.mark.parametrize("n,k", UNEVEN)
def test_walk_forward_reaches_the_last_sample(n: int, k: int) -> None:
    tested = _tested(walk_forward_indices(_ranges(n), k, 0.0))
    assert max(tested) == n - 1


@pytest.mark.parametrize("n,k", UNEVEN)
def test_no_leakage_after_the_fix(n: int, k: int) -> None:
    """Der Fix darf keine Ueberschneidung einschleppen -- sonst waere er teurer als der Fehler."""
    for train, test in purged_walk_forward_indices(
        _ranges(n), k, purge_ms=5, embargo_ms=5
    ):
        assert not (set(train) & set(test)), "Train und Test ueberschneiden sich"
        if train:
            assert max(train) < min(test), "Training liegt nicht vollstaendig vor dem Test"
