"""Risikoschicht am Order-Pfad: die vier Grenzen als letzte Verteidigungslinie.

Vier bisher **verwaiste** Module (getestet, am Live-Pfad nie aufgerufen) werden hier zu
**einem** Aufrufer im Order-Pfad zusammengefuehrt und in der vorgeschriebenen, nicht
verhandelbaren Reihenfolge gefahren:

1. ``risk/limits.py`` (``evaluate_limits``) -- Kill-Switch: Tagesverlust, Drawdown-Halt,
   Positionsdeckel, Gap-Sperre. Der Drawdown-Halt latcht am Venue (``_halted``) und
   loest sich nicht von selbst.
2. ``gates/evaluation.py`` (``select_one``) -- Drossel: Cooldown je Instrument,
   Mindesthaltedauer, Trades je Instrument/Konto und Tag, gleichzeitige Positionen.
   „Bewerten ist nicht Handeln": eine zu schnelle Wiederholung wird abgewiesen.
3. ``risk/stop_budget.py`` (``stop_budget``) + ``risk/sizing.py``
   (``executable_stop_floor``) -- Stop-Floor gegen Budget je Anlageklasse/Hebel. Floor
   ueber Budget -> ``no_trade`` (kein weiter gesetzter Stop -- das waere ein anderer
   Trade).
4. ``risk/sizing.py`` (``size_position``) -- Positionsgroesse aus Risikoanteil und
   Stopabstand. Das **angeforderte** Volumen darf das Budget-Volumen nicht reissen.

Der ``RiskManager`` haelt den dafuer noetigen Zustand, den die Venue nicht traegt:
Equity-Verlauf (Tagesstart, rollierender Fenster-Hoechststand fuer den Drawdown),
Handelsfrequenz (letzter Trade je Instrument, Trades je Tag) und die offenen Positionen
mit Eroeffnungszeit. Die Venue meldet akzeptierte Eroeffnungen (``record_open_fill``)
und Schliessungen (``record_close``) zurueck; der Betreiber beobachtet Equity
(``observe_equity``, von der Venue je Order automatisch aufgerufen).

**Kostenbasis der dritten Grenze.** Die Budget-Untergrenze ist eine Kostenrechnung; sie
taugt nur so viel wie die Kostenzahl, die hineingeht. Diese Schicht sucht sie in dieser
Reihenfolge: das Argument ``measured_cost_bps`` (die Messung DIESER Order, die der
Runner im selben Lauf am Live-Bid/Ask genommen hat) ->
``request.meta[MEASURED_COST_BPS_META_KEY]`` (dieselbe Messung, mitgereist am Auftrag,
damit die zweite Pruefung im Venue dieselbe Zahl sieht und nicht eine mildere) ->
``RiskPolicy.measured_cost_bps`` je Klasse (eine Messkampagne) -> Annahmetabelle. Der
letzte Schritt ist der einzige ungedeckte; die Herkunft steht deshalb als erstes Wort
in ``detail["cost_basis"]`` jeder Autorisierung (``gemessen``/``auftrag``/``kampagne``/
``annahme``), und ``require_measured_cost`` macht den Rueckfall auf Wunsch zur Sperre
(Begruendung: ``risk/stop_budget.py``).

**Die mitgereiste Zahl darf nur anheben.** Der ``meta``-Kanal ueberquert eine Grenze:
er kommt als *Auftragsdatum* herein, nicht als Messung dieser Schicht. Naehme sie ihn
ungeprueft, koennte ein Aufrufer die Kostenpraemisse des Systems von aussen setzen --
und ausgerechnet ``venue/mt5.py::_enforce_risk``, die zweite Pruefung, die einen Fehler
der ersten abfangen soll, rechnete dann mit einer Zahl aus der Schicht, die sie
absichert. Sie waere nie strenger als diese. Gemessen an der neuen Fassung reichte
``meta={"measured_cost_bps": Decimal("0.001")}``, um die Untergrenze trotz einer
Politik mit 5,0 bp auf 0,01 bp zu druecken -- mit dem Etikett "gemessen".

Darum wird die mitgereiste Zahl gegen die **Praemisse** dieser Schicht gehalten
(Messkampagne der Politik, sonst die Annahmetabelle der Klasse) und kann die Rechnung
nur in **eine** Richtung bewegen: darueber zaehlt sie und verschaerft die Untergrenze
-- genau der Zweck des Kanals --, darunter bleibt die Praemisse stehen. Nicht still:
die verworfene Zahl steht mit ihrem Grund in ``detail["cost_basis"]``.

Warum hier geklammert und nicht geworfen wird -- der Unterschied zum Typfehler in
``measured_cost_from_meta``: eine zu **niedrige** Zahl ist nicht zwingend ein Defekt.
Sie entsteht auch dann, wenn ein Markt ehrlich billiger ist als die (schmeichelnde)
Annahme -- Gold ist mit 1,5 bp angenommen, 1,0 bp sind messbar. Diese Schicht kann
"ehrlich gemessen" von "erfunden" nicht unterscheiden, weil sie nur die Zahl sieht;
sie rechnet deshalb mit ihrer eigenen Praemisse weiter und laesst die vorhandenen Tore
urteilen (zu enger Stop -> ``stop_budget_below_cost_floor``, ein typisierter,
begruendeter Abbruch). Ein Wurf machte aus einem Marktzustand einen Absturz mitten im
Live-Takt, der ``VenueError`` faengt und ``ValueError`` nicht.

Wer eine echt guenstigere Kostenlage handeln will, hinterlegt sie als Messkampagne in
``RiskPolicy.measured_cost_bps`` -- eine Entscheidung des Betreibers, nicht eines
Auftrags. Politik steht ueber Auftragsdaten, nicht darunter. Der Preis dieser
Unabhaengigkeit ist benannt und gewollt: eine in-Prozess gemessene Lage UNTER der
Praemisse traegt die erste Pruefung (Argument), nicht aber die zweite im Venue, die nur
das Auftragsdatum sieht -- die Order faellt dort fail-closed durch, statt auf einer
Zahl zu eroeffnen, die niemand nachpruefen kann.

**Eine Budgetrechnung, nicht zwei.** ``stop_budget_for`` ist die einzige Stelle, an der
diese Politik in ``risk/stop_budget.py`` geht; ``execution/runner.py`` ruft dieselbe
Methode, statt ``stop_budget`` mit den Vorgabewerten der Signatur zu fahren. Sonst
rechnet der Runner die Untergrenze mit ``max_cost_drag=0.05``, waehrend eine Politik mit
``0.02`` unmittelbar danach das Doppelte verlangt -- der Runner setzt den Stop auf die
eigene Zahl und diese Schicht lehnt ihn mit ``stop_budget_below_cost_floor`` ab. Zwei
Fassungen derselben Rechnung, und die strengere Politik erzeugt nicht den weiteren
Stop, sondern gar keinen Handel.

Fail-closed: jede nicht sicher zulaessige Order wird abgelehnt, ohne Default. Die
**Politik** (Grenzen, Schwellen, Risikoanteil) traegt der ``RiskPolicy``; die Venue
erzwingt sie am Order-Pfad (siehe ``venue/mt5.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from mt5_trading_ai.gates.evaluation import (
    Candidate,
    GateState,
    OpenPosition,
    ThrottlePolicy,
    select_one,
)
from mt5_trading_ai.risk.limits import (
    AccountSnapshot,
    LossLimits,
    TradingState,
    evaluate_limits,
)
from mt5_trading_ai.risk.sizing import (
    DEFAULT_RISK_FRACTION,
    SizingResult,
    StopFloorInputs,
    executable_stop_floor,
    size_position,
)
from mt5_trading_ai.risk.stop_budget import (
    StopBudget,
    assumed_cost_bps,
    stop_budget,
)
from mt5_trading_ai.venue.protocol import (
    AccountState,
    Instrument,
    OrderRequest,
)

#: Schluessel, unter dem eine eroeffnende Order ihre **gemessene** Roundturn-Kostenlage
#: (in bp) mitfuehrt. Der Runner legt sie hinein, diese Schicht liest sie -- damit die
#: zweite, unabhaengige Pruefung in ``venue/mt5.py::submit_order`` dieselbe Messung
#: sieht wie die erste. Ohne diesen Kanal rechnete die Venue-Pruefung gegen die
#: Annahmetabelle und waere milder als die Pruefung, die sie absichern soll.
MEASURED_COST_BPS_META_KEY = "measured_cost_bps"


@dataclass(frozen=True)
class RiskPolicy:
    """Politik der Risikoschicht -- die Grenzen, gegen die jede Eroeffnung prueft.

    ``loss_limits`` und ``throttle`` sind die vorregistrierten Konfigurationen der
    Einzelmodule; ``risk_fraction`` ist der Risikoanteil je Trade (geklammert in
    ``size_position``); ``max_cost_drag``/``safety`` steuern die Budgetspanne;
    ``measured_cost_bps`` erlaubt gemessene Round-Turn-Kosten je Klasse (schlagen die
    Annahmen im Stop-Budget). Der Eintrag ist zugleich die **Praemisse**, gegen die eine
    am Auftrag mitgereiste Zahl gehalten wird: darueber zaehlt sie, darunter wirft sie.

    ``require_measured_cost`` macht eine fehlende Messung zur Sperre statt zum Griff in
    die Annahmetabelle. Die Vorgabe ist ``False``, und das ist kein Versehen: es gibt
    heute noch eroeffnende Aufrufer ohne Messung (von Hand gebaute ``OrderRequest`` am
    Venue, die Schreibprobe in ``venue/smoke.py``), die eine Umstellung ersatzlos
    sperren wuerde. Bis die nachgezogen sind, gilt sichtbar statt still: die Basis
    steht als ``cost_basis`` in jeder Autorisierung. Der Schalter gehoert **hierher**
    und nicht an eine Aufrufstelle: der Pfad, der heute wirklich eroeffnet
    (``execution/runner.py``), uebergibt seine Messung unbedingt -- dort waere der
    Schalter eine Tautologie und keine Sperre.
    """

    loss_limits: LossLimits = field(default_factory=LossLimits)
    throttle: ThrottlePolicy = field(default_factory=ThrottlePolicy)
    risk_fraction: Decimal = DEFAULT_RISK_FRACTION
    max_cost_drag: Decimal = Decimal("0.05")
    safety: Decimal = Decimal("3")
    measured_cost_bps: dict[str, Decimal] = field(default_factory=dict)
    require_measured_cost: bool = False


@dataclass(frozen=True)
class RiskAuthorization:
    """Ergebnis der Risikopruefung. ``approved`` nur bei sicherer Zulaessigkeit.

    ``latch_halt`` ist wahr, wenn ein Drawdown-Halt greift -- die Venue setzt dann ihren
    ``_halted``-Latch (der sich nicht von selbst loest). ``detail`` traegt die
    Zwischenergebnisse fuer den Nachweis (Limit-Zustand, Budgetspanne, Sizing) und --
    sobald ein Budget gerechnet wurde -- unter ``cost_basis``, worauf die
    Budget-Untergrenze beruht: ``<herkunft> <bp>`` mit ``herkunft`` aus ``gemessen``
    (Live-Messung dieses Laufs), ``auftrag`` (am ``meta`` mitgereist, gegen die
    Praemisse geprueft), ``kampagne`` (``RiskPolicy.measured_cost_bps``) oder
    ``annahme`` (Tabelle). Der Eintrag ist nicht schmueckend: er ist die Stelle, an der
    ein Aufrufer sieht, worauf er gerade handelt -- und der Kanal steht dabei, weil
    "gemessen" ohne ihn nur hiesse, dass irgendjemand irgendeine Zahl uebergeben hat.
    """

    approved: bool
    reason: str | None
    latch_halt: bool = False
    sizing: SizingResult | None = None
    budget: StopBudget | None = None
    detail: dict[str, str] = field(default_factory=dict)


def measured_cost_from_meta(request: OrderRequest) -> Decimal | None:
    """Hole die mitgereiste Kostenmessung aus ``request.meta``. Fail-closed.

    Ein falscher Typ ist ein **Defekt des Aufrufers**, kein fehlender Wert: ein Float
    (oder ein String) an dieser Stelle hiesse, dass jemand die Messung ungenau oder
    ungeprueft weiterreicht. Er wirft, statt auf die Annahmetabelle zurueckzufallen --
    sonst waere ein Tippfehler im Schluessel eine stille Rueckstufung der Sperre.

    Dieselbe Strenge gilt fuer den Wert: eine nicht endliche oder nicht positive Zahl
    ist keine Kostenlage (Roundturn-Kosten sind Spread + Kommission + Slippage und damit
    echt positiv). Sie wirft **hier**, denn nachgelagert wuerde sie verschwinden: die
    Praemisse in ``RiskManager._kostenbasis`` klammert alles ab, was zu niedrig ist, und
    machte aus einer unbrauchbaren Zahl stillschweigend eine Nichtzahl -- ``NaN`` waere
    dort sogar ein ``InvalidOperation`` beim Vergleich. Ein Defekt wirft, er wird nicht
    weggeklammert.

    Geprueft wird hier nur die **Form**. Ob eine formal gueltige Zahl inhaltlich gelten
    darf, entscheidet ``RiskManager._kostenbasis``: dort steht die Praemisse, die sie
    nicht unterbieten darf. Diese Funktion kennt weder Politik noch Anlageklasse.
    """
    roh = request.meta.get(MEASURED_COST_BPS_META_KEY)
    if roh is None:
        return None
    if not isinstance(roh, Decimal):
        raise ValueError(
            f"{MEASURED_COST_BPS_META_KEY} in OrderRequest.meta muss ein Decimal sein, "
            f"ist {type(roh).__name__} ({roh!r})"
        )
    if not roh.is_finite() or roh <= 0:
        raise ValueError(
            f"{MEASURED_COST_BPS_META_KEY} in OrderRequest.meta muss endlich und "
            f"positiv sein, ist {roh}"
        )
    return roh


@dataclass(frozen=True)
class _Kostenbasis:
    """Die aufgeloeste Kostenzahl, ihre Herkunft -- und was dabei verworfen wurde.

    ``herkunft`` ist eines von ``gemessen`` (Live-Messung dieses Laufs, als Argument
    hereingereicht), ``auftrag`` (am ``meta`` mitgereist und ueber der Praemisse),
    ``kampagne`` (``RiskPolicy.measured_cost_bps``) oder ``annahme`` (Tabelle).
    ``verworfen`` ist leer oder nennt eine mitgereiste Zahl, die die Praemisse
    unterboten hat -- damit die Klammerung im Protokoll steht und nicht still bleibt.
    """

    bps: Decimal | None
    herkunft: str
    verworfen: str = ""

    def als_text(self, cost_bps: Decimal) -> str:
        """Die Zeile fuer ``RiskAuthorization.detail["cost_basis"]``."""
        return f"{self.herkunft} {cost_bps} bp{self.verworfen}"


class RiskManager:
    """Traegt den Risiko-Zustand und autorisiert eroeffnende Orders am Order-Pfad."""

    def __init__(
        self,
        policy: RiskPolicy | None = None,
        *,
        manual_release_id: str | None = None,
        gap_events: tuple[datetime, ...] = (),
    ) -> None:
        self._policy = policy if policy is not None else RiskPolicy()
        #: Manuelle Freigabe nach einem Drawdown-Halt. Ohne sie bleibt der Halt.
        #: Gilt nur fuer die AKTUELLE Episode: erholt sich der Drawdown unter die Grenze
        #: oder vertieft er sich ueber das freigegebene Niveau, wird sie verbraucht.
        self._manual_release_id = manual_release_id
        #: Drawdown-Niveau, gegen das die Freigabe erteilt wurde (lazily beim ersten
        #: Sehen gesetzt); ein tieferer Drawdown macht die Freigabe ungueltig.
        self._release_ceiling: Decimal | None = None
        #: Bekannte Gap-Ereignisse (Wochenende, Rolltermin, Earnings), UTC.
        self._gap_events = gap_events
        #: Equity-Beobachtungen (ts, equity), auf das Drawdown-Fenster beschnitten.
        self._equity_obs: list[tuple[datetime, Decimal]] = []
        self._day_start_equity: Decimal | None = None
        self._equity_day: date | None = None
        #: Handelsfrequenz-Zustand, taeglich zuruecksetzend.
        self._last_trade_at: dict[str, datetime] = {}
        self._trades_today_instrument: dict[str, int] = {}
        self._trades_today_account: int = 0
        self._trade_day: date | None = None
        #: Offene Positionen mit Eroeffnungszeit (Mindesthaltedauer, Positionsdeckel).
        self._open_positions: list[OpenPosition] = []

    # --- Zustandspflege ---------------------------------------------------
    def observe_equity(self, now: datetime, equity: Decimal) -> None:
        """Nimm eine Equity-Beobachtung auf (Tagesstart + Fenster-Hoechststand)."""
        if self._equity_day != now.date():
            # Neuer Handelstag: Tagesstart-Equity neu setzen (Tageslimit-Bezug).
            self._equity_day = now.date()
            self._day_start_equity = equity
        window = self._policy.loss_limits.drawdown_window
        self._equity_obs.append((now, equity))
        # Alte Beobachtungen ausserhalb des Drawdown-Fensters verwerfen.
        cutoff = now - window
        self._equity_obs = [(ts, eq) for ts, eq in self._equity_obs if ts >= cutoff]

    def _window_peak(self, current_equity: Decimal) -> Decimal:
        peak = current_equity
        for _ts, eq in self._equity_obs:
            if eq > peak:
                peak = eq
        return peak

    def _roll_trade_day(self, day: date) -> None:
        """Setzt die Frequenz-Tageszaehler bei Tageswechsel zurueck. Wird auf BEIDEN
        Pfaden gerufen (Lesen in ``authorize_opening``, Schreiben in
        ``record_open_fill``), sonst blockt eine an Tag N ausgeschoepfte Kappe an
        Tag N+1 stale weiter."""
        if self._trade_day != day:
            self._trade_day = day
            self._trades_today_instrument = {}
            self._trades_today_account = 0

    def record_open_fill(self, instrument: str, now: datetime) -> None:
        """Akzeptierte Eroeffnung: Frequenz-Zaehler + offene Position fortschreiben."""
        self._roll_trade_day(now.date())
        self._last_trade_at[instrument] = now
        self._trades_today_instrument[instrument] = (
            self._trades_today_instrument.get(instrument, 0) + 1
        )
        self._trades_today_account += 1
        # Netto je Symbol: ein bereits offenes Symbol wird nicht doppelt gezaehlt
        # (spiegelt ``record_close``, das alle Eintraege eines Symbols entfernt).
        if all(pos.instrument != instrument for pos in self._open_positions):
            self._open_positions.append(
                OpenPosition(instrument=instrument, opened_at=now)
            )

    def record_close(self, instrument: str) -> None:
        """Eine Schliessung: offene Positionen dieses Instruments entfernen."""
        self._open_positions = [
            pos for pos in self._open_positions if pos.instrument != instrument
        ]

    @property
    def open_position_count(self) -> int:
        """Offene (netto je Symbol gefuehrte) Positionen -- fuer den Deckel."""
        return len(self._open_positions)

    def release_drawdown(self, release_id: str) -> None:
        """Manuelle Freigabe nach einem Drawdown-Halt (menschliche Entscheidung).

        Gilt nur fuer die aktuelle Halt-Episode -- der Kill-Switch stellt sich nach
        Erholung oder bei einem tieferen Drawdown von selbst wieder scharf.
        """
        self._manual_release_id = release_id
        self._release_ceiling = None

    # --- Kostenbasis ------------------------------------------------------
    def stop_budget_for(
        self,
        *,
        asset_class: str,
        leverage: int,
        measured_cost_bps: Decimal | None = None,
    ) -> StopBudget:
        """Die Budgetspanne nach DIESER Politik -- die eine Stelle, die sie rechnet.

        Oeffentlich, weil ``execution/runner.py`` dieselbe Spanne braucht, bevor er
        den Stop-Preis setzt. Riefe er ``stop_budget`` selbst, uebernaehme er die
        Vorgabewerte der Signatur (``max_cost_drag=0.05``, ``safety=3``) statt der
        konfigurierten Politik -- und rechnete damit an einer Politik mit
        ``max_cost_drag=0.02`` vorbei, deren Untergrenze doppelt so hoch liegt. Der
        Runner setzte den Stop auf seine Zahl, diese Schicht lehnte ihn Zeilen
        spaeter mit ``stop_budget_below_cost_floor`` ab: die strengere Politik
        erzeugte keinen weiteren Stop, sondern gar keinen Handel.

        ``measured_cost_bps`` ist die bereits aufgeloeste Kostenzahl (siehe
        ``_kostenbasis``); ``None`` bedeutet "keine Messung" -- dann entscheidet
        ``require_measured_cost`` zwischen Annahmetabelle und Sperre.
        """
        return stop_budget(
            asset_class=asset_class,
            leverage=leverage,
            measured_cost_bps=measured_cost_bps,
            max_cost_drag=self._policy.max_cost_drag,
            safety=self._policy.safety,
            require_measured_cost=self._policy.require_measured_cost,
        )

    def _kostenbasis(
        self,
        *,
        instrument: Instrument,
        request: OrderRequest,
        measured_cost_bps: Decimal | None,
    ) -> _Kostenbasis:
        """Welche Kostenzahl fuer diese Order gilt -- und **woher** sie stammt.

        Rangfolge, Praemisse und Begruendung stehen im Modul-Docstring unter
        "Kostenbasis". ``bps is None`` heisst: keine gemessene Zahl -- ``stop_budget``
        entscheidet dann zwischen Annahmetabelle und Sperre.

        Die mitgereiste Zahl gilt nur, soweit sie die Praemisse nicht unterbietet. Sie
        wird auch dann gegen die Praemisse gehalten, wenn das Argument sie schlaegt:
        sie faehrt am Auftrag weiter zur zweiten Pruefung im Venue, und was dort
        gelten wird, gehoert schon hier in die Akte.
        """
        klasse = instrument.asset_class.value
        kampagne = self._policy.measured_cost_bps.get(klasse)
        praemisse = kampagne if kampagne is not None else assumed_cost_bps(klasse)
        mitgereist = measured_cost_from_meta(request)
        verworfen = ""
        if mitgereist is not None and praemisse is not None and mitgereist < praemisse:
            verworfen = (
                f" (Auftrag {mitgereist} bp verworfen: unter Praemisse {praemisse} bp)"
            )
            mitgereist = None

        if measured_cost_bps is not None:
            return _Kostenbasis(measured_cost_bps, "gemessen", verworfen)
        if mitgereist is not None:
            return _Kostenbasis(mitgereist, "auftrag", verworfen)
        if kampagne is not None:
            return _Kostenbasis(kampagne, "kampagne", verworfen)
        return _Kostenbasis(None, "annahme", verworfen)

    # --- Autorisierung ----------------------------------------------------
    def authorize_opening(
        self,
        *,
        instrument: Instrument,
        request: OrderRequest,
        account: AccountState,
        price: Decimal,
        spread_bps: Decimal,
        leverage: int,
        now: datetime,
        measured_cost_bps: Decimal | None = None,
    ) -> RiskAuthorization:
        """Fahre die vier Grenzen in vorgeschriebener Reihenfolge fuer eine Eroeffnung.

        Reihenfolge: Kill-Switch (Limits) -> Drossel -> Stop-Floor/Budget -> Groesse.
        Der erste Verstoss lehnt fail-closed ab. ``latch_halt=True`` bei einem
        Drawdown-Halt (die Venue setzt dann ihren ``_halted``-Latch).

        ``measured_cost_bps`` sind die am Live-Bid/Ask gemessenen Roundturn-Kosten
        DIESER Order in bp. Wer sie hat, gibt sie her: sie bestimmt die
        Budget-Untergrenze und schlaegt jede Tabelle (Rangfolge im Modul-Docstring).
        Sie steht oben in der Rangfolge, weil sie **in diesem Prozess** entstanden ist
        -- der Aufrufer hat gerade gemessen. Die am Auftrag mitgereiste Zahl ist etwas
        anderes: sie hat eine Grenze ueberquert und wird gegen die Praemisse dieser
        Schicht geprueft (``_kostenbasis``); unterbietet sie sie, wirft die
        Autorisierung, statt milder zu rechnen.
        """
        self.observe_equity(now, account.equity)
        # Frequenz-Tageszaehler auch auf dem LESEpfad rollen (nicht nur beim Fill),
        # sonst blockt eine an Tag N ausgeschoepfte Kappe an Tag N+1 stale weiter.
        self._roll_trade_day(now.date())

        # Freigabe-Gueltigkeit VOR der Limit-Auswertung bestimmen, damit die AKTUELLE
        # Order korrekt entscheidet: die Freigabe deckt nur die aktuelle Halt-Episode.
        peak = self._window_peak(account.equity)
        drawdown = (
            Decimal("1")
            if peak <= 0
            else max(Decimal("0"), peak - account.equity) / peak
        )
        max_dd = self._policy.loss_limits.max_drawdown_fraction
        if self._manual_release_id is not None:
            if drawdown < max_dd:
                # Erholt -> Episode vorbei, Kill-Switch wieder scharf.
                self._manual_release_id = None
                self._release_ceiling = None
            elif self._release_ceiling is None:
                # Erstes Sehen in der Episode -> freigegebenes Niveau festhalten.
                self._release_ceiling = drawdown
            elif drawdown > self._release_ceiling:
                # Drawdown vertieft sich ueber das freigegebene Niveau -> neuer Halt.
                self._manual_release_id = None
                self._release_ceiling = None

        # 1) Kill-Switch (evaluate_limits): Tagesverlust, Drawdown, Deckel, Gap.
        snapshot = AccountSnapshot(
            now=now,
            equity=account.equity,
            day_start_equity=self._day_start_equity
            if self._day_start_equity is not None
            else account.equity,
            window_peak_equity=peak,
            open_positions=len(self._open_positions),
            trading_day=now.date(),
            manual_release_id=self._manual_release_id,
            upcoming_gap_events=self._gap_events,
        )
        limit = evaluate_limits(snapshot, self._policy.loss_limits)
        if not limit.may_open:
            halt = limit.state is TradingState.HALTED
            reason = f"risk_{limit.reasons[0]}" if limit.reasons else "risk_blocked"
            return RiskAuthorization(
                approved=False,
                reason=reason,
                latch_halt=halt,
                detail={"limit_state": limit.state.value},
            )

        # 2) Drossel (select_one): Cooldown, Mindesthaltedauer, Tageskappen, Deckel.
        # Der Score liegt per Konstruktion auf der Schwelle: der Auftrag existiert, die
        # Bewertung ist also bereits getroffen -- die Drossel prueft nur die Frequenz.
        candidate = Candidate(
            instrument=request.symbol,
            asset_class=instrument.asset_class.value,
            score=self._policy.throttle.score_threshold,
        )
        gate_state = GateState(
            now=now,
            open_positions=tuple(self._open_positions),
            last_trade_at=dict(self._last_trade_at),
            trades_today_per_instrument=dict(self._trades_today_instrument),
            trades_today_account=self._trades_today_account,
        )
        gate = select_one([candidate], gate_state, self._policy.throttle)
        if gate.selected is None:
            reasons = gate.suppressed[0].reasons if gate.suppressed else ()
            reason = f"throttle_{reasons[0]}" if reasons else "throttle_blocked"
            return RiskAuthorization(approved=False, reason=reason)

        # 3) Stop-Floor gegen Stop-Budget je Klasse/Hebel.
        if price <= 0:
            return RiskAuthorization(approved=False, reason="risk_price_missing")
        requested_stop_bps = (
            abs(price - request.stop_loss) / price * Decimal("10000")
        )
        floor = executable_stop_floor(
            StopFloorInputs(
                spread_bps=spread_bps,
                tick_size_bps=instrument.tick_size / price * Decimal("10000"),
                # Volatilitaet steht am Order-Pfad nicht je Bar bereit -> 0; der Floor
                # nimmt das Maximum, die uebrigen Komponenten (Broker-Abstand, Tiefe,
                # Spread) binden weiter. Nachruesten: siehe SPAETER.
                volatility_bps=Decimal("0"),
                broker_stop_level_bps=Decimal(instrument.stop_level_points)
                * instrument.tick_size
                / price
                * Decimal("10000"),
                depth_ratio=None,
            )
        )
        # Kostenbasis samt Herkunft (Rangfolge und Pruefung: ``_kostenbasis``). Das
        # erste Wort im ``detail`` benennt den Kanal, nicht nur "jemand hat eine Zahl
        # uebergeben" -- eine mitgereiste Zahl ist etwas anderes als eine Messung
        # dieses Laufs, auch wenn beide gepruefte Zahlen sind.
        basis = self._kostenbasis(
            instrument=instrument, request=request, measured_cost_bps=measured_cost_bps
        )
        budget = self.stop_budget_for(
            asset_class=instrument.asset_class.value,
            leverage=leverage,
            measured_cost_bps=basis.bps,
        )
        kostenbasis = basis.als_text(budget.cost_bps)
        if not budget.tradeable:
            return RiskAuthorization(
                approved=False,
                reason=f"stop_budget_{budget.reason or 'untradeable'}",
                budget=budget,
                detail={"cost_basis": kostenbasis},
            )
        # Der effektive Stopabstand muss die Budget-UNTERgrenze (Kostenfloor) einhalten.
        # Ein zu enger Stop ist rechnerisch unhandelbar -- die Kosten heben den
        # Nulldurchgang zu weit (``breakeven_hit_rate``). Die Obergrenze prueft
        # ``size_position`` bereits praezise (stop_floor/requested vs. budget.upper).
        effective_stop_bps = max(floor.executable_floor_bps, requested_stop_bps)
        if effective_stop_bps < budget.lower_bps:
            return RiskAuthorization(
                approved=False,
                reason="stop_budget_below_cost_floor",
                budget=budget,
                detail={
                    "cost_basis": kostenbasis,
                    "effective_stop_bps": str(effective_stop_bps),
                    "cost_floor_bps": str(budget.lower_bps),
                },
            )

        # 4) Positionsgroesse: angefordertes Volumen darf das Budget nicht reissen.
        sizing = size_position(
            account_equity=account.equity,
            risk_fraction=self._policy.risk_fraction,
            stop_floor_bps=floor.executable_floor_bps,
            stop_budget_bps=budget.upper_bps,
            requested_stop_bps=requested_stop_bps,
            price=price,
            contract_size=instrument.contract_size,
            volume_min=instrument.volume_min,
            volume_step=instrument.volume_step,
            volume_max=instrument.volume_max,
            leverage=leverage,
        )
        if sizing.no_trade:
            first = sizing.reasons[0] if sizing.reasons else "no_trade"
            return RiskAuthorization(
                approved=False,
                reason=f"risk_sizing_{first}",
                sizing=sizing,
                budget=budget,
                detail={"cost_basis": kostenbasis},
            )
        if sizing.volume is not None and request.volume > sizing.volume:
            # Das angeforderte Volumen liegt ueber dem risikobudgetierten Maximum.
            return RiskAuthorization(
                approved=False,
                reason="volume_exceeds_risk_budget",
                sizing=sizing,
                budget=budget,
                detail={
                    "requested_volume": str(request.volume),
                    "budget_volume": str(sizing.volume),
                    "cost_basis": kostenbasis,
                },
            )

        return RiskAuthorization(
            approved=True,
            reason=None,
            sizing=sizing,
            budget=budget,
            detail={"budget_volume": str(sizing.volume), "cost_basis": kostenbasis},
        )
