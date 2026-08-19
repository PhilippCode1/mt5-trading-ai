"""Der Modellpfad, schliessbar gemacht: ein Herausforderer wartet, er regiert nicht.

WORUM ES GEHT
-------------
Stufe 6 des Auftrags::

    Befoerderung standardmaessig aus. Artefakt erreicht den auswertenden Dienst und
    ueberlebt Neustarts. Freigabeteilung auf den gesaeuberten Vorwaertstest.
    Trainingsmindestmenge in ein Verhaeltnis zur Merkmalszahl setzen.
    Trainingsendpunkte authentifizieren. Ueberlappende Zielwerte gewichten.

    Abnahme: ein Trainingslauf erzeugt einen Herausforderer im Wartezustand, nicht
    einen Champion; ein falscher Schemahash fuehrt zum Verwerfen; das Artefakt ist
    nach Neustart noch da.

DER MODELLPFAD DIESES STANDES
-----------------------------
Hier trainiert nichts ein neuronales Netz. Der Modellpfad ist
``gates/learning_phase.py``: aus beobachteten Trades entstehen **Parametersaetze**
(``Proposal``). Das ist ein Modell im Sinne dieser Stufe -- eine aus Daten
abgeleitete Groesse, die spaeter Entscheidungen faerben soll --, und alle sechs
Forderungen greifen daran.

Gemessen wurde vor dieser Stufe (``AUFTRAG/stufen/06-modellpfad/belege/``):

* **Befoerderung** war bereits aus: ``Proposal.state`` ist ``"candidate"``, und
  ``validate_proposal`` weist alles andere ab. Diese Forderung war erfuellt.
* **Ein Artefakt gab es nicht.** Der Vorschlag landete als Versuchszeile im Ledger --
  ohne Zustand, ohne Lesefunktion, ohne Schemahash. Nach einem Neustart war er als
  Vorschlag nicht wiederauffindbar, nur als Zeile in einer Versuchsliste.
* **Mindestmenge zur Merkmalszahl:** keine. Eine Rangliste entstand aus **einem**
  einzigen Trade; acht Parameter liessen sich ohne jeden Bezug zur Beobachtungszahl
  vorschlagen.
* **Ueberlappende Zielwerte:** ungewichtet. Fuenf vollstaendig ueberlappende Trades --
  dieselbe Marktbewegung fuenfmal -- zaehlten als fuenf unabhaengige Beobachtungen.
* **Schemahash:** existierte nicht.

WARUM DER SCHEMAHASH KEIN FORMALISMUS IST
-----------------------------------------
Ein Artefakt ueberdauert den Code, der es geschrieben hat. Wird ein Feld umbenannt,
umgedeutet oder entfernt, liest der neue Code die alte Datei weiter -- und zwar
klaglos, weil JSON keine Typen kennt. Der gefaehrliche Fall ist nicht der Absturz,
sondern die stille Fehldeutung: ``beobachtungen`` hiess frueher „Trades", heisst jetzt
„effektive Beobachtungen", und dieselbe Zahl bedeutet plotzlich etwas anderes.

Der Hash geht ueber **Feldnamen und Feldtypen** des Artefakts. Er aendert sich, sobald
sich die Bedeutung aendern *koennte*, und ein Artefakt mit fremdem Hash wird verworfen,
nicht zurechtgebogen.

DIE ZWEI RECHENREGELN
---------------------
**Mindestmenge je Merkmal.** Ein Parametersatz mit ``p`` Parametern braucht mindestens
``MINDESTBEOBACHTUNGEN_JE_MERKMAL * p`` Beobachtungen, und nie weniger als
``MINDESTBEOBACHTUNGEN_ABSOLUT``. Die Zahl ist keine Wissenschaft und wird auch nicht
als solche verkauft: sie ist eine vorab gesetzte Schranke gegen den Fall, den die
Messung gefunden hat -- acht Parameter aus drei Trades.

**Ueberlappung.** Zwei Trades, die dasselbe Instrument zur selben Zeit halten, sehen
dieselbe Marktbewegung. Sie sind nicht zwei Beobachtungen. Gezaehlt wird deshalb die
**belegte Zeit**: die Vereinigung aller Haltespannen, geteilt durch die mittlere
Haltedauer. Fuenf vollstaendig deckungsgleiche Trades ergeben so eine Beobachtung, fuenf
disjunkte ergeben fuenf.

Das ist bewusst dieselbe Ueberlegung wie Purge/Embargo in ``backtest/splits.py``: dort
wird verhindert, dass Trainings- und Testfenster dieselbe Bewegung sehen, hier, dass
eine Bewegung mehrfach als Beleg zaehlt.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Der einzige Zustand, in dem ein Herausforderer entsteht. Es gibt in diesem Modul
#: **keine** Funktion, die ihn aendert -- die Befoerderung ist kein Programmschritt.
WARTEND = "wartend"

#: Beobachtungen je Parameter, vorab gesetzt. Verschaerfen ist erlaubt, senken nicht
#: (V6): eine Schranke, die man senkt, wenn sie stoert, ist keine.
MINDESTBEOBACHTUNGEN_JE_MERKMAL = 30

#: Untergrenze unabhaengig von der Parameterzahl. Auch ein einziger Parameter wird
#: nicht aus einer Handvoll Trades geschaetzt.
MINDESTBEOBACHTUNGEN_ABSOLUT = 50

#: Laenge einer Pruefsumme aus ``data/loader.py`` (SHA-256, hexadezimal).
PRUEFSUMMENLAENGE = 64


class HerausfordererFehler(ValueError):
    """Eine der Schranken dieser Stufe wurde verletzt. Kein Artefakt entsteht."""


@dataclass(frozen=True)
class Herkunft:
    """Woher die Zahlen stammen, auf denen der Herausforderer steht.

    „Trainingsendpunkte authentifizieren" heisst in einem Stand ohne Netzdienste genau
    das: die Quelle jeder Eingangsgroesse ist benannt und formal geprueft. Eine
    Pruefsumme, die ``"egal"`` lauten darf, authentifiziert nichts -- gemessen war das
    vor dieser Stufe der Fall.
    """

    data_checksum: str
    code_commit: str

    def pruefe(self) -> None:
        if len(self.data_checksum) != PRUEFSUMMENLAENGE or not all(
            c in "0123456789abcdef" for c in self.data_checksum
        ):
            raise HerausfordererFehler(
                f"data_checksum ist keine SHA-256-Hexpruefsumme "
                f"({len(self.data_checksum)} Zeichen). Eine Herkunft, die jeder Text "
                "sein darf, authentifiziert nichts."
            )
        if not self.code_commit.strip():
            raise HerausfordererFehler("code_commit fehlt.")


@dataclass(frozen=True)
class Herausforderer:
    """Das Artefakt. Es wartet -- und sagt selbst, worauf.

    Die Feldnamen und -typen dieser Klasse sind der Gegenstand des Schemahashes. Wer
    hier ein Feld aendert, aendert den Hash, und alte Artefakte werden ab dann
    verworfen statt fehlgedeutet.
    """

    strategy_id: str
    base_version: str
    parameters: dict[str, Any]
    rationale: str
    herkunft: Herkunft
    #: Rohe Zahl der Trades, aus denen der Vorschlag stammt.
    beobachtungen: int
    #: Dieselbe Menge nach Abzug der Ueberlappung. Diese Zahl traegt die Schranke.
    effektive_beobachtungen: float
    erstellt_am: datetime
    #: Der noch ausstehende Nachweis. Ein Herausforderer wird NICHT dadurch Champion,
    #: dass jemand ihn befoerdert, sondern indem er den gesaeuberten Vorwaertstest
    #: besteht -- und dieses Feld sagt, welchen.
    freigabeteilung: str
    zustand: str = WARTEND

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_hash": schema_hash(),
            "strategy_id": self.strategy_id,
            "base_version": self.base_version,
            "parameters": dict(self.parameters),
            "rationale": self.rationale,
            "herkunft": {
                "data_checksum": self.herkunft.data_checksum,
                "code_commit": self.herkunft.code_commit,
            },
            "beobachtungen": self.beobachtungen,
            "effektive_beobachtungen": self.effektive_beobachtungen,
            "erstellt_am": self.erstellt_am.isoformat(timespec="seconds"),
            "freigabeteilung": self.freigabeteilung,
            "zustand": self.zustand,
        }


def schema_hash() -> str:
    """Hash ueber Feldnamen **und** Feldtypen von :class:`Herausforderer`.

    Ueber die Typen, nicht nur die Namen: eine Umdeutung von ``int`` nach ``float``
    aendert die Bedeutung einer Zahl, ohne ihren Namen anzufassen. Genau diese
    Aenderung hat diese Stufe selbst vorgenommen (``effektive_beobachtungen``), und sie
    soll sichtbar sein.
    """
    beschreibung = ";".join(f"{f.name}:{f.type}" for f in fields(Herausforderer))
    return hashlib.sha256(beschreibung.encode("utf-8")).hexdigest()[:16]


def mindestbeobachtungen(parameterzahl: int) -> int:
    """Wie viele (effektive) Beobachtungen ein Satz aus ``parameterzahl`` braucht."""
    if parameterzahl < 1:
        raise HerausfordererFehler("Ein Parametersatz ohne Parameter ist keiner.")
    return max(
        MINDESTBEOBACHTUNGEN_ABSOLUT,
        MINDESTBEOBACHTUNGEN_JE_MERKMAL * parameterzahl,
    )


def effektive_beobachtungen(
    spannen: Sequence[tuple[str, datetime, datetime]],
) -> float:
    """Beobachtungszahl nach Abzug der Ueberlappung -- je Instrument.

    ``spannen`` sind ``(Instrument, von, bis)``. Gerechnet wird je Instrument::

        belegte Zeit (Vereinigung der Spannen) / mittlere Spannenlaenge

    Fuenf deckungsgleiche Spannen ergeben 1,0; fuenf disjunkte ergeben 5,0. Zwei
    Instrumente laufen getrennt und werden addiert -- sie sehen verschiedene Maerkte.

    **Was das nicht ist:** eine Korrelationsrechnung. Zwei Instrumente koennen eng
    zusammenlaufen (EURUSD und GBPUSD an einem Dollartag), und diese Funktion zaehlt
    sie trotzdem doppelt. Sie behandelt die Ueberlappung, die man ohne Marktmodell
    sehen kann -- die zeitliche. Der Rest bleibt offen und wird nicht als geloest
    ausgegeben.
    """
    if not spannen:
        return 0.0
    je_instrument: dict[str, list[tuple[datetime, datetime]]] = {}
    for instrument, von, bis in spannen:
        if bis < von:
            raise HerausfordererFehler(
                f"Spanne endet vor ihrem Beginn ({instrument}: {von} .. {bis})."
            )
        je_instrument.setdefault(instrument, []).append((von, bis))

    gesamt = 0.0
    for eintraege in je_instrument.values():
        laengen = [(bis - von).total_seconds() for von, bis in eintraege]
        mittlere = sum(laengen) / len(laengen)
        if mittlere <= 0:
            # Nur Nullspannen: keine belegte Zeit, also keine Beobachtung, die eine
            # Ueberlappung haette. Jede zaehlt einzeln.
            gesamt += float(len(eintraege))
            continue
        belegt = 0.0
        aktuell_von, aktuell_bis = None, None
        for von, bis in sorted(eintraege):
            if aktuell_bis is None or von > aktuell_bis:
                if aktuell_bis is not None and aktuell_von is not None:
                    belegt += (aktuell_bis - aktuell_von).total_seconds()
                aktuell_von, aktuell_bis = von, bis
            elif bis > aktuell_bis:
                aktuell_bis = bis
        if aktuell_bis is not None and aktuell_von is not None:
            belegt += (aktuell_bis - aktuell_von).total_seconds()
        gesamt += belegt / mittlere
    return gesamt


def baue_herausforderer(
    *,
    strategy_id: str,
    base_version: str,
    parameters: dict[str, Any],
    rationale: str,
    herkunft: Herkunft,
    spannen: Sequence[tuple[str, datetime, datetime]],
    freigabeteilung: str,
    jetzt: datetime,
) -> Herausforderer:
    """Ein Herausforderer im Wartezustand -- oder gar keiner.

    Die drei Schranken laufen **vor** der Erzeugung, damit ein Artefakt, das existiert,
    auch eines ist, das durfte: Herkunft geprueft, Ueberlappung abgezogen,
    Mindestmenge gegen die Merkmalszahl gehalten.
    """
    herkunft.pruefe()
    if not parameters:
        raise HerausfordererFehler("Ein Parametersatz ohne Parameter ist keiner.")
    if not freigabeteilung.strip():
        raise HerausfordererFehler(
            "Ohne benannte Freigabeteilung entstuende ein Herausforderer, der nicht "
            "sagt, worauf er wartet."
        )
    effektiv = effektive_beobachtungen(spannen)
    noetig = mindestbeobachtungen(len(parameters))
    if effektiv < noetig:
        raise HerausfordererFehler(
            f"{len(parameters)} Parameter verlangen {noetig} effektive Beobachtungen, "
            f"vorhanden sind {effektiv:.1f} (aus {len(spannen)} Trades, der Rest ist "
            "Ueberlappung)."
        )
    return Herausforderer(
        strategy_id=strategy_id,
        base_version=base_version,
        parameters=dict(parameters),
        rationale=rationale,
        herkunft=herkunft,
        beobachtungen=len(spannen),
        effektive_beobachtungen=effektiv,
        erstellt_am=jetzt,
        freigabeteilung=freigabeteilung,
    )


@dataclass(frozen=True)
class Ablagebefund:
    """Was die Ablage hergibt -- und was sie verworfen hat."""

    herausforderer: tuple[Herausforderer, ...] = ()
    verworfen: tuple[str, ...] = field(default_factory=tuple)


class HerausfordererAblage:
    """Die Artefakte auf der Platte. Je Herausforderer eine Datei.

    **Je Datei einer, nicht alle in einer.** Ein defektes Artefakt nimmt so nur sich
    selbst mit; eine Sammeldatei haette bei einem einzigen Formatfehler alle
    verworfen, und der Betrieb stuende ohne jeden Kandidaten da, ohne zu wissen warum.
    """

    def __init__(self, ordner: Path) -> None:
        self._ordner = ordner

    @property
    def ordner(self) -> Path:
        return self._ordner

    def schreibe(self, herausforderer: Herausforderer) -> Path:
        self._ordner.mkdir(parents=True, exist_ok=True)
        stempel = herausforderer.erstellt_am.strftime("%Y%m%dT%H%M%S")
        ziel = self._ordner / f"{herausforderer.strategy_id}-{stempel}.json"
        neben = ziel.with_suffix(".json.neu")
        neben.write_text(
            json.dumps(herausforderer.as_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        neben.replace(ziel)
        return ziel

    def lade(self) -> Ablagebefund:
        """Lies alle Artefakte. Fremder Schemahash -> verworfen, nicht gedeutet."""
        if not self._ordner.is_dir():
            return Ablagebefund()
        erwartet = schema_hash()
        gefunden: list[Herausforderer] = []
        verworfen: list[str] = []
        for pfad in sorted(self._ordner.glob("*.json")):
            try:
                daten = json.loads(pfad.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                verworfen.append(f"{pfad.name}: unlesbar ({exc})")
                continue
            if not isinstance(daten, dict):
                verworfen.append(f"{pfad.name}: kein Objekt")
                continue
            gelesen = daten.get("schema_hash")
            if gelesen != erwartet:
                verworfen.append(
                    f"{pfad.name}: Schemahash {gelesen!r} statt {erwartet!r} -- "
                    "mit einem anderen Feldsatz geschrieben, wird nicht gedeutet"
                )
                continue
            try:
                gefunden.append(_aus_dict(daten))
            except (KeyError, TypeError, ValueError) as exc:
                verworfen.append(f"{pfad.name}: Feld unbrauchbar ({exc})")
        return Ablagebefund(tuple(gefunden), tuple(verworfen))


def _aus_dict(daten: dict[str, Any]) -> Herausforderer:
    herkunft = daten["herkunft"]
    zustand = daten["zustand"]
    if zustand != WARTEND:
        # Ein Artefakt, das sich selbst zum Champion erklaert, wird nicht gelesen.
        # Die Befoerderung ist kein Feld in einer Datei.
        raise ValueError(f"Zustand {zustand!r} -- ein Artefakt wartet oder ist keines")
    return Herausforderer(
        strategy_id=str(daten["strategy_id"]),
        base_version=str(daten["base_version"]),
        parameters=dict(daten["parameters"]),
        rationale=str(daten["rationale"]),
        herkunft=Herkunft(
            data_checksum=str(herkunft["data_checksum"]),
            code_commit=str(herkunft["code_commit"]),
        ),
        beobachtungen=int(daten["beobachtungen"]),
        effektive_beobachtungen=float(daten["effektive_beobachtungen"]),
        erstellt_am=datetime.fromisoformat(str(daten["erstellt_am"])).astimezone(UTC),
        freigabeteilung=str(daten["freigabeteilung"]),
        zustand=zustand,
    )
