"""Zeitreihen-Splits mit Purge und Embargo — herausgeloest aus learning_engine.

Uebernommen sind nur die drei Aufteilungs-Funktionen und die Helfer, die sie
brauchen (``Range``, ``_overlaps``, ``_band_for_purge_and_embargo``). Kein
Trainingspfad, keine Registry, keine Drift-Schicht, kein ``meta_models``.

Der Fix, der den letzten Fold bis zum Datenende fuehrt, ist enthalten:
``fold_size = n // k`` schneidet bei ``n % k != 0`` sonst die juengsten -- und
damit entscheidungsrelevantesten -- Samples ab (gemessen: n=100/k=7 verlor 98-99,
n=97/k=5 verlor 95-96).

Korrektur beim Umzug (Auftrag Teil 3 VI): ``purge_ms`` und ``embargo_ms`` trugen
im Altbestand den Default ``0``. Ein stiller Null-Default sieht im Protokoll aus
wie eine gesetzte Sperre und ist offen. Deshalb sind diese Parameter jetzt
**pflichtig** (keyword-only, kein Default): ein Aufrufer muss den Wert bewusst
waehlen. Auch die bewusste Wahl ``0`` (etwa ein reiner Abdeckungstest) ist dann
sichtbar statt versteckt.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Range:
    """Zeitintervall fuer ein Label (z. B. Trade von open bis close)."""

    start: int
    end: int


def _overlaps(a: Range, b: Range) -> bool:
    return not (a.end <= b.start or a.start >= b.end)


def _band_for_purge_and_embargo(
    t0: int, t1: int, *, purge_ms: int, embargo_ms: int
) -> Range:
    """Sperr-Zeitband: Purge vor Test, Embargo nach Test."""
    return Range(
        int(t0) - int(max(0, purge_ms)),
        int(t1) + int(max(0, embargo_ms)),
    )


def purged_walk_forward_indices(
    ranges: list[Range],
    k: int,
    *,
    purge_ms: int,
    embargo_ms: int,
    min_initial_train: int = 0,
    exclude_prior_test: bool = True,
) -> list[tuple[list[int], list[int]]]:
    """
    Walk-Forward mit Purge+Embargo-Band; fruehere Test-Indizes optional
    exklusiv (Index-Menge, naehe Lopez-de-Prado).

    - Train: nur Indizes j < test_lo (chronologisch vor dem aktuellen Test-Block)
    - Pro Fold: kein range[j] ueberlappt [test_start - purge, test_end + embargo]
    - Wenn ``exclude_prior_test=True``: j aus vorherigen Test-Blocks nie im Training
    - ``min_initial_train``: erste m Zeilen ausschliesslich als Trainings-Pool vor dem
      ersten Test, damit Fold 0 nicht nur Test ist.
    """
    if not ranges or k < 1:
        return []
    n = len(ranges)
    min_initial = int(max(0, min(min_initial_train, n - 1)))
    if n - min_initial < 1:
        return []
    rem = n - min_initial
    fold_size = max(1, rem // k)
    prev_test: set[int] = set()
    splits: list[tuple[list[int], list[int]]] = []
    for i in range(k):
        lo = min_initial + i * fold_size
        # Letzter Fold laeuft bis n. Sonst schneidet `fold_size = rem // k` bei
        # `n % k != 0` ab, und die **juengsten** Samples werden nie getestet --
        # gemessen: n=100/k=7 verlor die Indizes 98-99, n=97/k=5 die Indizes 95-96.
        # Genau die sind die entscheidungsrelevantesten.
        hi = n if i == k - 1 else min(min_initial + (i + 1) * fold_size, n)
        if lo >= n or lo >= hi:
            break
        test_idx = list(range(lo, hi))
        t0 = min(ranges[j].start for j in test_idx)
        t1 = max(ranges[j].end for j in test_idx)
        band = _band_for_purge_and_embargo(
            t0, t1, purge_ms=purge_ms, embargo_ms=embargo_ms
        )
        train_idx: list[int] = []
        for j in range(n):
            if j >= lo:
                break
            if exclude_prior_test and j in prev_test:
                continue
            if _overlaps(ranges[j], band):
                continue
            train_idx.append(j)
        prev_test.update(test_idx)
        splits.append((train_idx, test_idx))
    return splits
