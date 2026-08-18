"""Roter Eichfall des 180-Tage-Demo-Tors (E7) -- gemessen, nicht behauptet.

Der Befund: ``evaluate_demo_progress`` nahm einen freien ``elapsed_days: int`` und
glaubte ihn, waehrend die uebergebene ``DemoRegistration`` im ganzen Funktionskoerper
kein einziges Mal gelesen wurde. Die Laufzeit, die als Beleg gelten sollte, war die
einzige Groesse, die niemand belegen musste.

WARUM DIESE DATEI ANDERS GESCHRIEBEN IST ALS DER REST
-----------------------------------------------------
Sie soll gegen die **alte** Fassung laufen (``git archive`` in einen Temp-Ordner,
Testdatei hineinkopieren) und dort ehrlich mit einer *Assertion* fehlschlagen -- nicht
schon beim Import zerbrechen. Ein Sammelfehler ("ImportError: DemoAccount") waere kein
Nachweis, dass die alte Fassung das Loch HAT, sondern nur, dass sie die neue API nicht
kennt. Darum importiert diese Datei ausschliesslich Namen, die es in beiden Fassungen
gibt, baut die Datentypen ueber ``dataclasses.fields`` und reicht dem Tor per
``inspect.signature`` nur die Argumente, die es annimmt. Beide Fassungen laufen also
durch denselben Aufruf -- und geben verschiedene Antworten. Genau das ist die Messung.

Erwartung: alle vier Faelle hier sind gegen die alte Fassung ROT und gegen die neue
GRUEN.
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import UTC, datetime, timedelta
from typing import Any

from mt5_trading_ai.backtest.edge import EdgeVerdict
from mt5_trading_ai.venue import demo_run

#: Feste Gegenwart. Der Eichfall darf an keiner Rechneruhr haengen.
JETZT = datetime(2026, 1, 1, 12, tzinfo=UTC)


def _uhr() -> datetime:
    return JETZT


def _bestanden() -> EdgeVerdict:
    """Ein bestandener Edge -- damit NUR die Laufzeit/Kontobindung entscheidet."""
    return EdgeVerdict(passed=True, checks=(), unmet=())


def _konto(nummer: str = "4711") -> Any:
    """Kontoidentitaet, sofern die Fassung eine kennt. Die alte kennt keine."""
    typ = getattr(demo_run, "DemoAccount", None)
    return None if typ is None else typ(nummer, "Demo-Broker", True)


def _registrierung(*, tage_alt: int, konto: str = "4711") -> Any:
    """Eine Registrierung, die vor ``tage_alt`` Tagen erfolgt ist -- in beiden
    Fassungen baubar, weil die Felder aus dem Datentyp selbst gelesen werden."""
    felder = {f.name for f in dataclasses.fields(demo_run.DemoRegistration)}
    args: dict[str, Any] = {
        "strategy_id": "x",
        "version": "v1",
        "registered_on": (JETZT - timedelta(days=tage_alt)).date(),
    }
    if "account" in felder:
        args["account"] = _konto(konto)
    return demo_run.DemoRegistration(**args)


def _tor(**angebot: Any) -> Any:
    """Rufe das Tor und reiche ihm NUR die Argumente, die seine Fassung annimmt.

    So sieht die alte Fassung ihr ``elapsed_days`` und die neue ihre ``clock``; der
    Testkoerper bleibt fuer beide derselbe.
    """
    erlaubt = inspect.signature(demo_run.evaluate_demo_progress).parameters
    return demo_run.evaluate_demo_progress(
        **{name: wert for name, wert in angebot.items() if name in erlaubt}
    )


def test_behauptete_laufzeit_reift_kein_konto() -> None:
    """DER Eichfall: die Registrierung ist von heute -- null Tage Demo. Der Aufrufer
    behauptet 400. Die alte Fassung glaubte die Behauptung und meldete reif."""
    ergebnis = _tor(
        registration=_registrierung(tage_alt=0),
        observed_account=_konto(),
        elapsed_days=400,
        live_verdict=_bestanden(),
        clock=_uhr,
    )
    assert not ergebnis.ready_for_live_question, (
        "eine frei behauptete Laufzeit hat das Demo-Tor passiert"
    )


def test_die_registrierung_wird_ueberhaupt_gelesen() -> None:
    """Zwei Registrierungen, die sich NUR im Datum unterscheiden, muessen zu zwei
    verschiedenen Antworten fuehren.

    Fuehren sie zur selben, wird das Objekt nicht gelesen -- unabhaengig davon, wie
    die Funktion sonst aussieht. Das ist der Befund in seiner knappsten Form.
    """
    lange = _tor(
        registration=_registrierung(tage_alt=400),
        observed_account=_konto(),
        elapsed_days=400,
        live_verdict=_bestanden(),
        clock=_uhr,
    )
    frisch = _tor(
        registration=_registrierung(tage_alt=0),
        observed_account=_konto(),
        elapsed_days=400,
        live_verdict=_bestanden(),
        clock=_uhr,
    )
    assert lange.ready_for_live_question is True
    assert frisch.ready_for_live_question is False


def test_fremdes_konto_reift_nicht() -> None:
    """Ein Reifezeugnis eines ANDEREN Kontos darf nicht zaehlen: 400 Tage auf Konto
    4711 machen Konto 9999 nicht reif."""
    ergebnis = _tor(
        registration=_registrierung(tage_alt=400, konto="4711"),
        observed_account=_konto("9999"),
        elapsed_days=400,
        live_verdict=_bestanden(),
        clock=_uhr,
    )
    assert not ergebnis.ready_for_live_question, (
        "die Reife eines fremden Kontos hat das Demo-Tor passiert"
    )


def test_das_tor_nimmt_keine_laufzeit_mehr_entgegen() -> None:
    """Die strukturelle Seite: solange ``elapsed_days`` ein Parameter ist, gibt es
    einen Weg, dem Tor die Antwort vorzusagen."""
    params = inspect.signature(demo_run.evaluate_demo_progress).parameters
    assert "elapsed_days" not in params
    assert "clock" in params
    assert "observed_account" in params
