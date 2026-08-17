"""Gemessene Volatilitaet je Instrument — ATR(14) und die Ablage dafuer.

WARUM DIESES MODUL
------------------
Das Kostentor (``tools/kostentor.py``) rechnet die erforderliche Trefferquote aus
Round-Turn-Kosten und **Stopabstand**. Der Stopabstand ist ein Vielfaches der
Volatilitaet. Eine geratene Volatilitaet macht das ganze Tor wertlos — es saehe aus
wie ein Beleg und waere keiner. Darum trennt dieses Paket sauber:

* Die **Rechnung** steht hier, in der Standardbibliothek, ohne Terminal, und ist
  getestet (``tests/test_volatility.py``).
* Die **Messung** steht in ``tools/atr_messung.py`` und liest ueber den bestehenden
  lesenden MT5-Pfad (``RealMt5Terminal``, ``allow_write=False``, Demokonto).
* Das **Ergebnis** liegt in ``config/atr_measurements.json`` — versioniert und
  fail-closed nach dem Muster von ``config/instrument_catalog.json``.

Damit steht jede Zahl an genau einer Stelle (Kernregel 9) und traegt ihren Status:
``gemessen`` oder ``nicht_gemessen``. Ein ``nicht_gemessen`` wird **nie** still durch
eine Schaetzung ersetzt; der Aufrufer muss den Fall behandeln.

DIE RECHNUNG
------------
True Range je Kerze::

    TR_i = max(H_i - L_i, |H_i - C_(i-1)|, |L_i - C_(i-1)|)

ATR(14) nach Wilder (gleitender Durchschnitt mit Glaettungsfaktor 1/14)::

    ATR_14 = Mittel(TR_1..TR_14)                 (Startwert)
    ATR_i  = (ATR_(i-1) * 13 + TR_i) / 14        (danach)

**Luecken-Bereinigung.** Zwischen zwei H1-Kerzen liegt nicht immer eine Stunde:
Wochenenden, Feiertage und Boersenpausen erzeugen Spruenge. Der Kurssprung ueber eine
solche Pause geht in ``|H_i - C_(i-1)|`` ein und blaeht die True Range auf. Ein zu
grosser ATR laesst das Kostentor **besser** aussehen, als es ist (grosser Stopabstand
``S`` -> kleinere erforderliche Trefferquote ``p*``). Deshalb wird die Verkettung zum
Vorgaenger geloest, wenn der Abstand ``max_gap`` ueberschreitet: dann gilt
``TR_i = H_i - L_i``. Die unbereinigte Reihe wird zusaetzlich berechnet, damit die
Bereinigung sichtbar bleibt und nichts still verschwindet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ATR_MEASUREMENT_VERSION = "atr-measurement-v1"
ATR_MEASUREMENTS_FILENAME = "atr_measurements.json"

#: Standard-Periode. Vom Auftrag vorgegeben (M1: „ATR(14) auf H1").
ATR_PERIOD = 14

#: Standard-Luecke, ab der die Verkettung zum Vorgaenger geloest wird. Bei H1-Kerzen
#: ist alles ueber zwei Stunden eine Pause und kein Handelsfluss.
DEFAULT_MAX_GAP = timedelta(hours=2)

#: Status-Werte je Instrument. ``nicht_gemessen`` ist ein Ergebnis, kein Fehlen.
STATUS_MEASURED = "gemessen"
STATUS_NOT_MEASURED = "nicht_gemessen"
_STATUS_VALUES = (STATUS_MEASURED, STATUS_NOT_MEASURED)


class AtrMeasurementError(ValueError):
    """Die Messdatei ist unbrauchbar. Fail-closed: keine Kostenrechnung."""


@dataclass(frozen=True)
class Candle:
    """Eine Kerze, so viel wie die Rechnung braucht."""

    ts: datetime
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class AtrMeasurement:
    """Das Messergebnis eines Instruments.

    ``status`` ist ``gemessen`` oder ``nicht_gemessen``. Bei ``nicht_gemessen`` sind
    alle Zahlenfelder ``None`` und ``reason`` traegt den Grund — der Aufrufer darf
    daraus keine Schaetzung machen.

    Alle ``*_price``-Felder stehen in Preiseinheiten des Instruments, alle ``*_bps``
    in Basispunkten des gleichzeitigen Schlusskurses.
    """

    symbol: str
    status: str
    reason: str | None
    bars: int
    window_start: str | None
    window_end: str | None
    atr_median_price: float | None
    atr_p25_price: float | None
    atr_median_bps: float | None
    atr_p25_bps: float | None
    atr_median_price_roh: float | None
    price_median: float | None
    spread_median_points: float | None
    spread_p75_points: float | None
    point: float | None
    digits: int | None
    contract_size: float | None
    gap_bars: int | None

    @property
    def measured(self) -> bool:
        return self.status == STATUS_MEASURED


def percentile(values: list[float], q: float) -> float:
    """Perzentil mit linearer Interpolation. ``q`` in [0, 1].

    Bewusst hier statt aus ``statistics``: ``statistics.quantiles`` schneidet die
    Reihe in feste Abschnitte und trifft ein einzelnes Perzentil nur ueber Umwege.
    """
    if not values:
        raise ValueError("percentile auf leerer Reihe")
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"q ausserhalb [0, 1]: {q}")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def true_ranges(
    candles: list[Candle], *, max_gap: timedelta | None = DEFAULT_MAX_GAP
) -> list[float]:
    """True Range je Kerze ab der zweiten.

    Ist ``max_gap`` gesetzt und der Abstand zum Vorgaenger groesser, faellt die
    Verkettung weg: ``TR = H - L``. Mit ``max_gap=None`` entsteht die unbereinigte
    Reihe.
    """
    out: list[float] = []
    for index in range(1, len(candles)):
        current = candles[index]
        previous = candles[index - 1]
        spanne = current.high - current.low
        if max_gap is not None and (current.ts - previous.ts) > max_gap:
            out.append(spanne)
            continue
        out.append(
            max(
                spanne,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return out


def gap_count(candles: list[Candle], *, max_gap: timedelta = DEFAULT_MAX_GAP) -> int:
    """Wie viele Kerzen folgen auf eine Pause laenger als ``max_gap``?"""
    return sum(
        1
        for index in range(1, len(candles))
        if (candles[index].ts - candles[index - 1].ts) > max_gap
    )


def wilder_atr(ranges: list[float], *, period: int = ATR_PERIOD) -> list[float]:
    """ATR-Reihe nach Wilder. Gibt eine Reihe der Laenge ``len(ranges) - period + 1``.

    Der erste Wert ist das einfache Mittel der ersten ``period`` True Ranges, danach
    glaettet Wilder mit ``1/period``. Ist die Reihe kuerzer als ``period``, ist das
    Ergebnis leer — kein Ersatzwert.
    """
    if period <= 0:
        raise ValueError("period muss positiv sein")
    if len(ranges) < period:
        return []
    current = sum(ranges[:period]) / period
    out = [current]
    for value in ranges[period:]:
        current = (current * (period - 1) + value) / period
        out.append(current)
    return out


def atr_series_bps(atr: list[float], closes: list[float]) -> list[float]:
    """ATR in Basispunkten des jeweils gleichzeitigen Schlusskurses.

    ``closes`` muss dieselbe Laenge haben wie ``atr`` und die Schlusskurse **zu den
    ATR-Zeitpunkten** tragen. Ein Schlusskurs <= 0 ist ein Fehler, kein Ueberspringen.
    """
    if len(atr) != len(closes):
        raise ValueError(
            f"ATR-Reihe ({len(atr)}) und Schlusskurse ({len(closes)}) "
            "haben verschiedene Laenge"
        )
    out: list[float] = []
    for value, close in zip(atr, closes, strict=True):
        if close <= 0:
            raise ValueError(f"Schlusskurs <= 0 in der Reihe: {close}")
        out.append(value / close * 10_000.0)
    return out


def not_measured(symbol: str, reason: str) -> AtrMeasurement:
    """Ein sauberes „nicht gemessen" — laut, mit Grund, ohne Ersatzzahl."""
    return AtrMeasurement(
        symbol=symbol,
        status=STATUS_NOT_MEASURED,
        reason=reason,
        bars=0,
        window_start=None,
        window_end=None,
        atr_median_price=None,
        atr_p25_price=None,
        atr_median_bps=None,
        atr_p25_bps=None,
        atr_median_price_roh=None,
        price_median=None,
        spread_median_points=None,
        spread_p75_points=None,
        point=None,
        digits=None,
        contract_size=None,
        gap_bars=None,
    )


def default_measurements_path() -> Path:
    """Suche aufwaerts nach ``config/atr_measurements.json``.

    Bewusst kein ENV-Override — die Messung ist Teil der gepruften Datenlage, kein
    Laufzeitschalter (wie beim Instrumentenkatalog).
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / ATR_MEASUREMENTS_FILENAME
        if candidate.is_file():
            return candidate
    return here.parent / "data" / ATR_MEASUREMENTS_FILENAME


_REQUIRED_TOP = ("schema_version", "measurement_id", "measured_on", "timeframe",
                 "atr_period", "method", "terminal", "instruments")

_NUMERIC_FIELDS = (
    "atr_median_price",
    "atr_p25_price",
    "atr_median_bps",
    "atr_p25_bps",
    "atr_median_price_roh",
    "price_median",
    "spread_median_points",
    "spread_p75_points",
    "point",
    "contract_size",
)


def load_atr_measurements(
    path: Path | str | None = None,
) -> dict[str, AtrMeasurement]:
    """Lade und validiere die Messdatei. Jeder Defekt ist ein Fehler, kein Default."""
    file_path = Path(path) if path is not None else default_measurements_path()
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AtrMeasurementError(f"Messdatei fehlt: {file_path}") from exc
    except json.JSONDecodeError as exc:
        raise AtrMeasurementError(
            f"Messdatei ist kein gueltiges JSON: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise AtrMeasurementError("Messdatei ist kein Objekt")
    for field in _REQUIRED_TOP:
        if field not in raw:
            raise AtrMeasurementError(f"Messdatei ohne Pflichtfeld {field!r}")
    if int(raw["atr_period"]) != ATR_PERIOD:
        raise AtrMeasurementError(
            f"Messdatei mit fremder ATR-Periode {raw['atr_period']!r}, "
            f"erwartet {ATR_PERIOD}"
        )

    instruments = raw["instruments"]
    if not isinstance(instruments, dict) or not instruments:
        raise AtrMeasurementError("Messdatei ohne Instrumente")

    return {
        str(symbol): _parse_measurement(str(symbol), entry)
        for symbol, entry in instruments.items()
    }


def load_fx_rates(path: Path | str | None = None) -> dict[str, float]:
    """Die gemessenen Umrechnungskurse aus derselben Messdatei.

    Warum sie hier liegen und nicht in der Kostendatei: sie sind **gemessen** (letzter
    H1-Schlusskurs desselben Laufs), nicht recherchiert. Eine Kommission in USD auf ein
    in JPY notiertes Instrument laesst sich ohne sie nicht in Basispunkte umrechnen --
    und ein geratener Kurs waere genau die Sorte stiller Annahme, die dieses Paket
    ausschliesst. Fehlen sie, ist das ein Fehler, kein leeres Woerterbuch.
    """
    file_path = Path(path) if path is not None else default_measurements_path()
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AtrMeasurementError(f"Messdatei fehlt: {file_path}") from exc
    except json.JSONDecodeError as exc:
        raise AtrMeasurementError(f"Messdatei ist kein gueltiges JSON: {exc}") from exc
    rates = raw.get("fx_rates") if isinstance(raw, dict) else None
    if not isinstance(rates, dict) or not rates:
        raise AtrMeasurementError(
            "Messdatei ohne 'fx_rates' — ohne gemessene Umrechnungskurse laesst sich "
            "eine Kommission in fremder Waehrung nicht in Basispunkte umrechnen"
        )
    out: dict[str, float] = {}
    for paar, wert in rates.items():
        try:
            zahl = float(wert)
        except (TypeError, ValueError) as exc:
            raise AtrMeasurementError(
                f"fx_rates[{paar!r}] ist keine Zahl: {wert!r}"
            ) from exc
        if zahl <= 0:
            raise AtrMeasurementError(f"fx_rates[{paar!r}] ist nicht positiv: {zahl}")
        out[str(paar)] = zahl
    return out


def _number(symbol: str, field: str, value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise AtrMeasurementError(
            f"{symbol}: Feld {field!r} ist keine Zahl: {value!r}"
        ) from exc


def _parse_measurement(symbol: str, entry: Any) -> AtrMeasurement:
    if not isinstance(entry, dict):
        raise AtrMeasurementError(f"{symbol}: Eintrag ist kein Objekt")
    status = str(entry.get("status", ""))
    if status not in _STATUS_VALUES:
        raise AtrMeasurementError(
            f"{symbol}: unbekannter status {status!r}, erlaubt: {_STATUS_VALUES}"
        )
    numbers = {
        field: _number(symbol, field, entry.get(field)) for field in _NUMERIC_FIELDS
    }
    if status == STATUS_MEASURED:
        for field in ("atr_median_price", "atr_p25_price", "price_median"):
            wert = numbers[field]
            if wert is None or wert <= 0:
                raise AtrMeasurementError(
                    f"{symbol}: status={STATUS_MEASURED}, aber {field!r} fehlt "
                    f"oder ist <= 0 ({entry.get(field)!r})"
                )
    else:
        reason = entry.get("reason")
        if not (isinstance(reason, str) and reason.strip()):
            raise AtrMeasurementError(
                f"{symbol}: status={STATUS_NOT_MEASURED} ohne Begruendung "
                "('reason') — ein nicht gemessener Wert braucht einen Grund"
            )
    digits = entry.get("digits")
    gap_bars = entry.get("gap_bars")
    return AtrMeasurement(
        symbol=symbol,
        status=status,
        reason=entry.get("reason"),
        bars=int(entry.get("bars", 0)),
        window_start=entry.get("window_start"),
        window_end=entry.get("window_end"),
        digits=int(digits) if digits is not None else None,
        gap_bars=int(gap_bars) if gap_bars is not None else None,
        **numbers,
    )
