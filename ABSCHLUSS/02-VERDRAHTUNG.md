# Verdrahtung (A3) — die Risikoschicht am echten Orderpfad

*In sich geschlossen. Rohausgabe der Eichfälle und des Dauertors:
[`07-AUSGABEN/eichfaelle.txt`](07-AUSGABEN/eichfaelle.txt).*

---

## Das Ergebnis in drei Sätzen

1. **Die Verdrahtungsquote beträgt 5 von 5**, gemessen vom Dauertor an einer echten Order,
   an **3 von 3** eröffnenden Eintrittspunkten. *Bestätigt durch Ausführung.*
2. **Vorher waren es 0 von 5 auf jedem erreichbaren Konto.** Die Risikoschicht war formal
   verdrahtet und praktisch tot: sie stieg bei einem Demokonto sofort wieder aus, und ein
   Live-Konto gab es nicht.
3. **Der Frische-Latch (S2) hat vorher an keinem Eintrittspunkt existiert** — 0 von 5.

---

## Der Befund, wie er wirklich war

Der Auftrag beschreibt den Ausgangszustand als „nur `leverage_preflight` bindet ein
`risk/`-Modul, Verdrahtungsquote 1 von 5". **Gemessen war er anders**, und die Abweichung
gehört hierher, weil ein Befund, den man nicht nachmisst, kein Befund ist:

Zwischen Paket 0 und heute wurde die Risikoschicht in `Mt5Venue.submit_order` angeschlossen
(Commit `130fcde`, „Abnahme-Paket 4 — Risikoschicht real an den Order-Pfad (S1)"). Vier der
fünf Sperren waren also aufgerufen. **Aber:**

```python
def _enforce_risk(self, instrument, request, leverage) -> None:
    account = self._terminal.account()
    if account.is_demo:
        return          # <-- hier stieg sie aus
```

Es gibt in diesem Vorhaben **kein Live-Konto** und darf keines geben, bevor der
Fail-Closed-Apparat steht — das ist die eigene Reihenfolge-Regel aus `FEHLT.md`. Die
Risikoschicht lief damit an **keinem** Konto, das man erreichen kann. Dieselbe Fehlerklasse
wie die 7/75-Hebeldefaults, nur eine Ebene subtiler: nicht „nicht angeschlossen", sondern
„angeschlossen und abgeschaltet".

| | vorher | nachher |
|---|---|---|
| Sperren an einer Demo-Eröffnung | **0 von 5** | **5 von 5** |
| Sperren an einer Live-Eröffnung | 4 von 5 | **5 von 5** |
| Frische-Latch, überhaupt vorhanden | **nein** | ja |
| Eintrittspunkte mit voller Verdrahtung | **0 von 3** | **3 von 3** |
| Dauertor, das das nachzählt | **nein** | ja, 26 Fälle |

---

## A3.1 — Erst zählen: die Eintrittspunkte

Ermittelt per Quellcode-Suche über `mt5_trading_ai/` und `tools/` (nicht geschätzt):
jede Stelle, an der eine **eröffnende** Order entsteht.

| # | Datei | Funktion | eröffnend? |
|---|---|---|---|
| E1 | `mt5_trading_ai/venue/mt5.py` | `Mt5Venue.submit_order` | **ja** — der Flaschenhals |
| E2 | `mt5_trading_ai/execution/runner.py` | `run_signal` | **ja** — baut einen `OrderRequest` |
| E3 | `mt5_trading_ai/venue/smoke.py` | `_write_probe` | **ja** — baut einen `OrderRequest` |
| E4 | `mt5_trading_ai/venue/mt5.py` | `emergency_flatten` | nein (siehe unten) |
| E5 | `mt5_trading_ai/venue/mt5.py` | `RealMt5Terminal.order_send` | nein (siehe unten) |

### Eigene Entscheidung 4 — die Sollzahl ist 3, nicht 5

*(Entscheidung des ausführenden Agenten, mit Begründung und mit Beleg.)*

A3.1 fragt nach „jeder Stelle, an der eine eröffnende Order **entsteht**". Zwei Kandidaten
entstehen dort nicht, und beide sind trotzdem behandelt statt weggelassen:

- **E4 `emergency_flatten`** erzeugt ausschließlich `reduce_only`-Schließungen mit
  `stop_loss = 0` und setzt **vor** der ersten Order den Global-Halt. Selbst wenn eine
  dieser Orders in den eröffnenden Zweig fiele, ist sie dort doppelt gesperrt: am
  Halt-Latch und an der Stop-Pflicht. *Belegt von*
  `test_emergency_flatten_kann_nicht_eroeffnen`.
- **E5 `RealMt5Terminal.order_send`** ist die Übertragungsschicht **unter** dem Flaschenhals,
  Teil des `Mt5Terminal`-Protokolls und deshalb nicht privatisierbar. Sie *überträgt* eine
  Order, sie *erzeugt* keine. Sie ist trotzdem eine reale Umgehung, wenn jemand das Terminal
  direkt hält — deshalb ist ihr Schreibpfad in diesem Paket zusätzlich **an ein Demokonto
  geklammert** (`require_demo=True`). Ein Live-Schreibpfad ist damit eine bewusste, getrennte
  Konstruktionsentscheidung. *Belegt von*
  `test_realterminal_schreibpfad_ist_auf_demo_geklammert`.

**Gegen den Rückfall gesichert:** `test_kein_unbemerkter_neuer_eintrittspunkt` durchsucht das
gesamte Paket nach Stellen, die einen `OrderRequest` bauen, und wird rot, sobald eine
auftaucht, die nicht bewertet ist. Es scheitert außerdem laut, wenn es **gar keine** findet.

---

## A3.2 — Die fünf Sollsperren und ihre Reihenfolge

Jede Sperre ist eine **Modulfunktion**, damit sie zählbar ist:

| # | Sperre | Definiert in | Gefahren über |
|---|---|---|---|
| 1 | Frische-Latch | `execution/freshness.py::evaluate_account_freshness` | `venue/mt5.py` direkt |
| 2 | Verlustgrenzen | `risk/limits.py::evaluate_limits` | `execution/risk_manager.py` |
| 3 | Stop-Budget | `risk/stop_budget.py::stop_budget` | `execution/risk_manager.py` |
| 4 | Positionsgröße | `risk/sizing.py::size_position` | `execution/risk_manager.py` |
| 5 | Bewertungstor | `gates/evaluation.py::select_one` | `execution/risk_manager.py` |

### Eigene Entscheidung 5 — der Demo-Ausstieg wurde entfernt

*(Entscheidung des ausführenden Agenten. Sie ist der Kern dieses Pakets.)*

`_enforce_risk` prüft nicht mehr auf `is_demo`. Begründung:

- Kostentor und Halal-Screen schützen vor **realem Geld** und **realer Zinsbelastung**. Auf
  einem Demokonto gibt es beides nicht; dort sind sie nicht bloß unnötig, sondern
  gegenstandslos. Sie bleiben demo-frei.
- Die Risikoschicht prüft dagegen, ob der **Mechanismus** trägt. Genau das muss auf dem
  Demokonto laufen, weil das Demokonto der Beweisplatz vor jedem Live-Pfad ist — die eigene
  Reihenfolge-Regel aus `FEHLT.md`. **Eine Sperre, die nur auf dem Konto läuft, das man noch
  nicht benutzt, ist nicht verdrahtet.**

**Statisch gegen den Rückfall gesichert:**
`test_risikoschicht_hat_keinen_konto_abhaengigen_ausstieg` liest den Quelltext von
`_enforce_risk` und wird rot, sobald dort wieder `is_demo` steht.

### Eigene Entscheidung 6 — die Reihenfolge

*(Entscheidung des ausführenden Agenten, mit Begründung.)*

**Bindend eingehalten:** der Frische-Latch läuft **zuerst** — vor allem, was aus dem
Kontozustand liest, auch vor der Live-Freigabe, die `is_demo` aus genau diesem Schnappschuss
zieht. *Statisch geprüft von* `test_frische_laeuft_vor_allem_was_den_kontozustand_liest`.

**Abweichend von der Auflistung in A3.2:** die Sperren 2 bis 5 laufen in der Reihenfolge des
bestehenden `RiskManager` — Verlustgrenzen → Drossel → Stop-Budget → Positionsgröße —, nicht
in der Reihenfolge Limits → Stop-Budget → Sizing → Bewertungstor. Drei Gründe:

1. **Die Menge der angenommenen Orders ist identisch.** Alle vier sind harte Ablehnungen;
   die Reihenfolge ändert nur, welcher Grund zuerst gemeldet wird, wenn zwei zugleich
   greifen.
2. **Fail-fast ist richtig herum.** Der Kill-Switch ist kontoweit, die Drossel reine
   Frequenzarithmetik ohne Preisbezug. Ein Konto im Halt erreicht so nie die Preisrechnung.
3. **Umbauen ohne Nutzen wäre Risiko ohne Gegenwert.** Der `RiskManager` hat eine grüne
   Rot-Grün-Eichung; eine rein kosmetische Umstellung setzt sie aufs Spiel.

### Der Frische-Latch — die Frist und warum sie so kurz ist

**`MAX_SNAPSHOT_AGE = 5 Sekunden`** *(eigene Entscheidung, begründet.)*

Der Kontozustand wird unmittelbar vor der Prüfung abgefragt; die normale Latenz einer
lokalen Terminalabfrage liegt im Millisekundenbereich. Fünf Sekunden sind rund drei
Größenordnungen über dem Normalfall — die Frist kann im gesunden Betrieb nicht zufällig
reißen. Reißt sie doch, ist genau einer von zwei Fällen eingetreten, und beide sind
Ablehnungsgründe: der Aufrufer hat einen **zwischengespeicherten** Schnappschuss
weitergereicht, oder das Terminal **hängt**. Eine längere Frist ließe beides durch, ohne
etwas zu gewinnen.

Die Sperre hat **zwei** Kanten: zu alt *und* zu weit in der Zukunft (Toleranz 1 Sekunde).
Ohne die zweite ließe sich die Sperre durch einen falschen Zeitstempel vollständig
aushebeln. Dazu eine dritte Bedingung: eine getrennte Sitzung liefert nie einen gültigen
Kontozustand, egal wie frisch der Stempel aussieht.

**Was sie nicht leistet, ausdrücklich:** sie prüft das *Alter*, nicht die *Richtigkeit*. Ein
Terminal, das einen frischen Zeitstempel auf einen veralteten Kontostand setzt — genau das
tut `RealMt5Terminal.account()` mit der lokalen Uhr —, fällt hier nicht auf. Dagegen hilft
nur die Verbindungsprüfung, die mitläuft.

---

## A3.3 — Negativ gefahren: die Eichfälle

Jede Sperre wurde absichtlich beschädigt und der rote Lauf belegt. Ohne roten Eichfall gilt
ein Tor als ungeprüft.

| Sperre | roter Eichfall | erwarteter Grund | grüner Gegenfall |
|---|---|---|---|
| 1 Frische | Uhr 5 Minuten vor | `snapshot_stale` | Uhr +1 s → angenommen |
| 1 Frische | Uhr 5 Minuten zurück | `snapshot_from_future` | (derselbe) |
| 2 Verlustgrenzen | Fensterhöchststand 12k gegen Equity 10k | `risk_drawdown_limit_reached` + Latch | Standard-Manager → angenommen |
| 3 Stop-Budget | Sicherheitsfaktor 100 | `risk_sizing_stop_floor_exceeds_budget` | Standard-Politik → angenommen |
| 4 Positionsgröße | 0,10 Lot statt 0,01 | `volume_exceeds_risk_budget` | 0,01 Lot → angenommen |
| 5 Bewertungstor | zweite Order sofort danach | `throttle_*` | erste Order → angenommen |

Zusätzlich negativ gefahren:

- **Ohne Risiko-Manager wird auch auf Demo abgelehnt** (`risk_unconfigured`) — der
  fail-closed-Fall, der vorher nur live griff.
- **Reduce-Only fährt 0 von 5 Sperren** — die Ausnahme ist festgehalten, damit sie nicht
  versehentlich zugezogen wird. Eine Sperre, die das Schließen verhindert, erhöht das
  Risiko.
- **Der Not-Aus kann nicht eröffnen**, und nach ihm ist jede Eröffnung am Latch gesperrt.

`tests/test_freshness.py` fährt zusätzlich jede der vier Ablehnungskanten des Latches
einzeln (**12 Fälle**), inklusive der Politik selbst: eine Frist ≤ 0 ist ein Fehler, kein
Urteil. Die Eichfälle im Dauertor selbst: **6 rote**, **2 grüne**.

---

## A3.4 — Das Dauertor gegen den Rückfall

`tests/test_orderpfad_verdrahtung.py`, **28 Fälle**. Es zählt auf zwei Ebenen, weil jede für
sich täuschbar ist:

**Dynamisch** — eine echte Order läuft durch den echten Pfad, und jede der fünf Sollsperren
wird beim Aufruf gezählt. Der Zähler hängt an der **Benutzungsstelle**, nicht an der
Definition: so fällt auf, wenn der Aufrufer die Sperre gar nicht mehr importiert. Zwei
Läufe, Demo und Live, beide 5 von 5.

**Statisch** — der Quelltext wird gelesen und auf die Wiederkehr des alten Fehlers geprüft:
kein `is_demo` in `_enforce_risk`, kein `is_demo` im Frische-Latch, Frische vor Live-Freigabe
und vor Risikoschicht, E2 und E3 rufen `submit_order`, `_require_write` klammert auf Demo.

**Laut scheitern, nie still.** Das Tor prüft **zuerst**, dass es seinen Gegenstand findet —
die Datei, die Klasse, die Methode, die Aufrufstellen. Findet es nichts, ist das ein
Fehlschlag mit einer Meldung, die das sagt, nicht ein bestandener Test ohne Befund:

> „Dauertor findet seinen Gegenstand nicht: … Ein Tor, das nichts findet und deshalb grün
> ist, ist der Fehler selbst."

---

## A3.5 — Der Kill-Switch-Widerspruch

**Der Widerspruch:** die Kopfzeile von `risk/limits.py` sagte „Verlustgrenzen und
Kill-Switch". `FEHLT.md` §7 führte den Kill-Switch als **nicht mitgekommen**.

**Gemessen — beide waren halb richtig.** Der Kill-Switch existiert, verteilt auf drei
Module:

| Bestandteil | Wo | Beleg |
|---|---|---|
| Kriterium und Zustände (`NORMAL` / `REDUCE_ONLY` / `HALTED`) | `risk/limits.py` | `test_kill_switch_kriterium_liegt_in_limits` |
| Freigabe-Kante (`AccountSnapshot.manual_release_id`) | `risk/limits.py` | (derselbe) |
| Latch und Griff (`latch_halt`, `clear_halt`, `is_halted`, `emergency_flatten`) | `venue/mt5.py` | `test_kill_switch_griff_und_latch_liegen_am_venue` |
| Manuelle Freigabe nach Drawdown | `execution/risk_manager.py` | `test_kill_switch_freigabe_liegt_am_risikomanager` |
| Der Latch hält und löst nur von Hand | Zusammenspiel | `test_kill_switch_latch_haelt_und_loest_nur_von_hand` |

**Beide Stellen wurden korrigiert, nicht eine:**

- Die Kopfzeile von `risk/limits.py` sagt jetzt genau, welchen Teil des Kill-Switch das
  Modul trägt (Kriterium und Zustand, als reine Funktion) und wo der Rest liegt (Latch und
  Griff am Venue). Der Grund steht dabei: ein Zustand, der sich nicht von selbst löst,
  braucht einen Halter, und das Modul hält nichts.
- `FEHLT.md` §7 führt den Kill-Switch als **erledigt** mit Angabe der drei Fundstellen und
  dem Testnamen. Offen bleiben aus §7 Runtime-Safety-Oracle und Exchange-Readiness.

---

## Was dabei noch aufgefallen ist — und mitbehoben wurde

**Zwei getrennte Risiko-Zustände.** Der Paper-Runner hielt einen eigenen `RiskManager`,
das Venue einen zweiten. Zwei getrennte Manager bedeuten zwei getrennte Frequenz- und
Positionszähler, von denen keiner das Ganze sieht — und die Drossel, die „mehrere Trades je
Tag" begrenzen soll, hätte je Pfad anders gezählt. Behoben: Runner und Venue teilen einen
Manager, und gebucht wird genau einmal. Der Runner erkennt das über die neue Eigenschaft
`Mt5Venue.risk_manager` und quittiert dann nur.

**Ein Testartefakt, das eine Semantik verdeckte.** Das Fake-Terminal meldete für **jede**
Order ein festes Füllvolumen von 0,10 Lot, unabhängig vom angeforderten. Dadurch bestand ein
Test zur Reduce-Only-Buchung aus dem falschen Grund: eine Schließung über 0,01 Lot stellte
eine Position von 0,10 Lot rechnerisch glatt. Behoben: das Fake spiegelt jetzt das
angeforderte Volumen; der Test schließt die volle Position.
