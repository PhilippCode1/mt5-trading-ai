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
from mt5_trading_ai.backtest.splits import (
    Range,
    _band_for_purge_and_embargo,
    purged_walk_forward_indices,
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
def test_no_leakage_after_the_fix(n: int, k: int) -> None:
    """Der Fix darf keine Ueberschneidung einschleppen -- sonst waere er teurer als der Fehler."""
    for train, test in purged_walk_forward_indices(
        _ranges(n), k, purge_ms=5, embargo_ms=5
    ):
        assert not (set(train) & set(test)), "Train und Test ueberschneiden sich"
        if train:
            assert max(train) < min(test), "Training liegt nicht vollstaendig vor dem Test"


def test_purge_excludes_train_range_in_the_pre_test_band() -> None:
    """Die Purge muss eine Train-Range im Sperrband VOR dem Test ausschliessen.

    Ohne die Purge (``int(t0)`` statt ``int(t0) - purge_ms``) rutscht Index 2 ins
    Training -- genau die Leckage, die die Purge verhindern soll (Audit-Fund g7).
    """
    ranges = [
        Range(0, 10),
        Range(10, 20),
        Range(20, 30),  # endet bei 30 -> im Purge-Band [25, 50)
        Range(50, 60),  # Testblock
        Range(60, 70),  # Testblock
    ]
    splits = purged_walk_forward_indices(
        ranges, k=1, purge_ms=25, embargo_ms=0, min_initial_train=3
    )
    assert len(splits) == 1
    train, test = splits[0]
    assert test == [3, 4]
    assert 2 not in train, "Purge schliesst die Range im Sperrband nicht aus"
    assert train == [0, 1]


def test_band_covers_purge_before_and_embargo_after() -> None:
    """Das Sperrband reicht ``purge_ms`` vor und ``embargo_ms`` hinter [t0, t1].

    Faengt das Entfernen von Purge ODER Embargo direkt an der Bandmathematik.
    """
    band = _band_for_purge_and_embargo(1000, 2000, purge_ms=30, embargo_ms=50)
    assert band.start == 970  # 1000 - 30 (Purge)
    assert band.end == 2050  # 2000 + 50 (Embargo)


# --- Embargo ist WIRKSAM: ein Post-Test-Bar faellt aus dem Training ----------
# purged_kfold_embargo_indices testet einen Block in der MITTE der Reihe; die Bars
# DAHINTER waeren sonst im Training. Diese Tests belegen negativ gefahren, dass das
# Embargo genau diese Nachbar-Bars aus dem Training entfernt (keine Fassade). (Im
# produktiv genutzten purged_walk_forward_indices ist Embargo dagegen ein bewusster
# No-op -- die Leckfreiheit dort traegt die Vergangenheits-Konstruktion + Purge; siehe
# test_embargo_alone_does_not_change_the_training_window.)
