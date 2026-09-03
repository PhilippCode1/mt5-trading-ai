# Stufe 4 — Risikokern verdrahten und fail-closed stellen

*Gefahren am 2026-08-19 auf Anweisung des Auftraggebers („weiter mit schritt 4").
Belege in [`belege/`](belege/), acht Dateien. Bestätigt durch Ausführung — jede Ausgabe
liegt bei.*

---

## 0. Zur Zulässigkeit dieser Stufe — sie ist nicht meine Entscheidung

§1 des Auftrags schließt diese Stufe für den vorliegenden Ausgang **ausdrücklich aus**:

> „(B) beendet den Auftrag ebenso gültig wie (A) — und zwar, **bevor weiterer Aufwand in
> Absicherung, Ausführung, Oberfläche oder Betrieb fließt**. Ein System, dessen Vorteil
> widerlegt ist, wird nicht abgesichert."

Stufe 4 heißt wörtlich „Risikokern verdrahten und fail-closed stellen" — sie ist
Absicherung, und der Vorteil ist widerlegt (H-004, Befund (B), am 2026-08-19 zusätzlich
gegen den Erfüllbarkeits-Einwand geprüft und gehalten).

**Ich habe diesen Punkt vor der Stufe benannt und der Auftraggeber hat sie angewiesen.**
Das ist seine Entscheidung über seinen eigenen Vertrag, nicht meine Auslegung. Sie steht
als E-009 in [`../../entscheidungen.md`](../../entscheidungen.md); dieselbe Lage gab es
in diesem Vorhaben schon einmal (`BERICHT_TEIL3.md` §11, Paket 5 auf ausdrückliche
Anweisung nach dem Abschluss). Wer später prüft, findet den Sachverhalt an beiden Stellen.

**Was das ändert und was nicht:** Der Befund (B) bleibt unberührt — diese Stufe misst
keinen Vorteil und behauptet keinen. Sie macht den Risikokern dichter. Dass ein dichterer
Risikokern an einem System ohne belegten Vorteil kein Geld verdient, bleibt wahr.

---

## 1. Was der Auftrag verlangt — und wie hier dagegen gemessen wurde

Fünf Forderungen und drei Abnahmefälle, wörtlich aus dem Vertrag. Gemessen wurde jede
einzeln, **vor** jeder Änderung (Beleg `03-messung-vorher.txt`).

| # | Forderung | Befund vor der Stufe |
|---|---|---|
| A1 | Sicherheitsriegel in eine eigene Zustandstabelle statt in ein Protokoll | **erfüllt** |
| A2 | Jede fehlende Pflichtkennzahl blockiert, statt übersprungen zu werden | **Lücke** |
| A3 | Portfoliozustand serverseitig aus den eigenen Beständen, nie aus der Anfrage | **erfüllt** |
| A4 | Reduzierende Aufträge von allen Sperren ausnehmen | **Lücke** |
| A5 | Genau eine Größenberechnung und ein Stopbudget | **erfüllt** |
| B1 | Zwei aufeinanderfolgende Eröffnungsaufträge werden **beide** abgelehnt | **erfüllt** |
| B2 | Leere Kontodaten erzeugen eine Ablehnung mit Grund | **Lücke** |
| B3 | Bei erzwungenem Halt scheitert die Eröffnung, der Ausstieg läuft trotzdem | **erfüllt** |
| B4 | Je Tor ein roter und ein grüner Eichfall | **fehlte für A2/A4/B1/B2/B3** |

Zwei Lücken, beide echt, beide geschlossen. Was schon stand, steht unten mit Beleg — denn
„erfüllt" ohne Messung wäre genau die Behauptung, gegen die dieser Auftrag gebaut ist.

---

## 2. Lücke 1 (A4/V5) — eine Position ließ sich nicht schließen

**Sperre V5 des Auftrags:** *„Reduzierende Aufträge werden von keiner Sperre blockiert."*

**Gemessen** (`01-reduce-only.txt`, `03-messung-vorher.txt`): `_validate_volume` stand in
`submit_order` **vor** der Reduce-Weiche und traf damit auch den Abbau.

| Lage | vorher | nachher |
|---|---|---|
| Gegenposition 0,10 → Abbau 0,01 | durchgelassen | durchgelassen |
| dieselbe, mit gelatchtem Global-Halt | durchgelassen | durchgelassen |
| **Gegenposition 0,005 → voller Abbau 0,005** | **ABGELEHNT `volume_below_min`** | **durchgelassen** |
| Gegenposition 0,005 → Abbau 0,01 (Flip) | abgelehnt `missing_stop_loss` | abgelehnt `missing_stop_loss` |

Das Mindestvolumen des Prüfstands ist 0,01. Eine Position von 0,005 Lot **konnte nicht
geschlossen werden** — die Sperre stand auf dem Risikoabbau.

**Ist die Lage erreichbar?** Ja, auf drei Wegen: `adopt_book` übernimmt, was der Broker
meldet, nicht was unsere Schrittweite erlaubt; eine Teilschließung von außen hinterlässt
einen Rest beliebiger Größe; und eine geänderte Kontraktspezifikation hebt das
Mindestvolumen über eine bestehende Position. Keiner dieser Wege ist exotisch.

**Geändert.** `_validate_volume` läuft jetzt nur noch im Eröffnungszweig. Für den Abbau
bleibt genau eine Bedingung, und sie ist keine Sperre, sondern eine Definition: es muss
etwas abgebaut werden (`volume > 0` → sonst `volume_not_positive`). Die Obergrenze — nicht
mehr als die Gegenposition — erzwingt `_reduces_position` bereits; deshalb dort weder
Mindestvolumen noch Schrittweite noch Höchstvolumen.

**Warum nicht strenger:** Ein Broker, der einen Teilabbau ablehnt, lehnt ihn selbst ab.
Sich als zweite Instanz davorzustellen kostet nichts, wenn der Broker ohnehin ablehnt —
und kostet die Schließbarkeit einer Position, wenn er es nicht getan hätte. Die
Irrtumsrichtung ist hier eindeutig.

**Was die Ausnahme nicht ist:** ein Freifahrtschein. `reduce_only=True` ohne offene
Gegenposition ist eine Eröffnung und geht durch alle Tore; ein Abbau über die
Gegenposition hinaus dreht sie und ist ebenfalls eine Eröffnung. Beide Fälle sind rot
gefahren.

---

## 3. Lücke 2 (A2/B2) — leere Kontodaten stürzten ab, statt abzulehnen

**Abnahmekriterium:** *„leere Kontodaten erzeugen eine Ablehnung mit Grund."*

**Gemessen** (`03-messung-vorher.txt`):

| Lage | vorher | nachher |
|---|---|---|
| `account()` liefert `None` | `AttributeError: 'NoneType' object has no attribute 'is_demo'` | `account_unevaluable` |
| Kontozeitstempel `ts` fehlt | `AttributeError: 'NoneType' object has no attribute 'date'` | `account_unevaluable` |

**Warum ein `AttributeError` die Abnahme nicht erfüllt.** Er nennt den Ort, nicht die
Ursache. Er trägt keinen `reason`, an dem der Betrieb ihn zählen oder von anderen
Ablehnungen unterscheiden könnte. Und er sieht im Protokoll aus wie ein Programmfehler
statt wie eine Sperre, die getan hat, was sie soll — was bei der Auswertung eines
Zwischenfalls genau die falsche Spur legt.

**Geändert.** Eine Regel, zwei der Lage angemessene Ausgänge:

- `konto_maengel(acc)` — die Regel. Prüft vier Pflichtfelder (`account_id`, `currency`,
  `is_demo`, `ts`) und vier Pflichtzahlen (`balance`, `equity`, `margin_used`,
  `margin_free`), letztere zusätzlich auf Endlichkeit. Liefert den Mangel als Text oder
  `None`.
- `Mt5Venue._konto_pflicht()` — der Orderpfad. Wirft `OrderRejectedError` mit
  `reason="account_unevaluable"`, `retryable=True`.
- `Mt5Venue.get_account()` — die lesende Abfrage. Wirft `VenueUnavailableError`; dort gibt
  es keine Order, die abgelehnt werden könnte.

**Warum auch „nicht endlich" sperrt:** `NaN` überlebt jeden Vergleich klaglos und färbt
ihn in die milde Richtung — `NaN > limit` ist `False`. Der Kill-Switch schwiege also
gerade dann, wenn die Zahl unbrauchbar ist. „Nicht endlich" ist deshalb derselbe Befund
wie „fehlt".

**Nicht auf dem reduzierenden Pfad.** Der braucht den Kontostand nicht, und nach V5
blockiert ihn ohnehin keine Sperre. Eine Kontoprüfung dort wäre eine Sperre auf dem Abbau
— genau das, was Lücke 1 gerade beseitigt hat.

**Alle vier Lesestellen umgehängt.** Vorher las der Orderpfad `self._terminal.account()`
an vier Stellen ungeprüft. Ein Dauertor am Syntaxbaum hält jetzt fest, dass außerhalb von
`_konto_pflicht` und `get_account` keine weitere entsteht — denn genau so ist diese Lücke
entstanden.

---

## 4. Was schon stand — gemessen, nicht angenommen

### A1 — Zustandstabelle statt Protokoll

`execution/risiko_zustand.py`, 1.596 Zeilen. Der Zustand liegt **außerhalb des
Arbeitsbaums** (`%LOCALAPPDATA%` bzw. `$XDG_STATE_HOME`), mit erzwungener Ortswahl:
relative Pfade werden abgewiesen, kein Pfad darf in den Paketbaum zeigen. Fünf getrennte
Urteile für „fehlt / leer / beschädigt", je Abschnitt nach der billigeren Irrtumsrichtung.
Der Anlass steht im Modul: vor dieser Tabelle begann der Drawdown nach jedem Prozessstart
bei null — gemessen **22 Eröffnungen an einem Konto-Tag gegen eine Kappe von 10**.

### A3 — Portfoliozustand aus den eigenen Beständen

Beleg `02-a3-a5.txt`. Die Reduce-Autorisierung liest `get_positions()` — einen frischen
Broker-Query — und **ausdrücklich nicht** das lokale Netto-Buch; die Begründung steht am
Code: ein veraltet-hohes Buch ließe einen Over-Fill an den Toren vorbei.

Der `OrderRequest` trägt kein Zustandsfeld. Die einzige Zahl, die am Auftrag mitreist, ist
die Kostenmessung (`meta["measured_cost_bps"]`) — und sie wird zweifach geprüft: auf Form
(Decimal, endlich, positiv, sonst Wurf statt Rückfall auf die Tabelle) und auf Inhalt
gegen die Prämisse der Schicht. Unterbietet sie die Prämisse, wirft die Autorisierung,
statt milder zu rechnen.

### A5 — genau eine Größenberechnung, ein Stopbudget

Am Syntaxbaum gezählt, nicht am Wort (Lehre aus F-005): je **eine** Definition
(`risk/sizing.py::size_position`, `risk/stop_budget.py::stop_budget`) und je **eine**
Aufrufstelle im Paket (`execution/risk_manager.py`). Zwei Dauertore halten beides fest.

Der Margendeckel in `execution/runner.py` ist keine zweite Rechnung: er kann nur
verkleinern, nie vergrößern.

### B1 und B3

Beide bestanden schon vorher (`03-messung-vorher.txt`) und sind jetzt als Dauertor
festgehalten.

---

## 5. Ein Befund aus einer falschen Erwartung

Der grüne Gegenfall zu B1 war zuerst falsch angesetzt: ich unterstellte, ohne Halt gingen
zwei Eröffnungen hintereinander durch. **Sie gehen nicht** — die Drossel
(`gates/evaluation.py`) weist die zweite mit `throttle_cooldown_active` ab.

Das ist richtiges Verhalten, und es gehört festgehalten statt die Erwartung
stillschweigend anzupassen: **B1 hält aus zwei voneinander unabhängigen Gründen.** Am
gelatchten Halt, weil der Halt latcht. Ohne Halt, weil die Mindestpause zwischen zwei
Eröffnungen nicht eingehalten ist. Die zweite Linie fällt nicht mit dem Latch. Beide sind
jetzt eigene Fälle.

---

## 6. Der eine Fall, der ohne Angabe weiterläuft — und warum das zulässig ist

`03-messung-vorher.txt`: ein fehlender **Hebelwunsch** (`meta` leer) hält die Order nicht
an. Nach V3 („Ein fehlender Messwert sperrt. Er wird nie durch einen Standardwert
ersetzt.") sieht das zunächst nach einer dritten Lücke aus.

Es ist keine, aus zwei Gründen — und beide sind gemessen, nicht behauptet:

1. **Ein Hebelwunsch ist kein Messwert.** Er ist die Absicht des Aufrufers. V3 schützt
   Messwerte davor, durch Annahmen ersetzt zu werden; eine fehlende Absicht ist etwas
   anderes als eine fehlende Messung.
2. **Der Rückfall ist in keiner Klasse der gefährlichere.** Gemessen über **alle acht**
   Anlageklassen, nicht an einer Stichprobe (`05-hebelrueckfall-alle-klassen.txt`):

| Klasse | ohne Wunsch | höchstmöglich | milder? |
|---|---:|---:|---|
| fx_major, fx_minor, gold, index_major, index_minor, commodity_non_gold | 5 | 10 | nein |
| equity | 5 | 5 | nein |
| crypto | 2 | 2 | nein |

**0 von 8 Klassen**, in denen der Rückfall mehr Hebel gäbe als der höchstmögliche Wunsch.
Ein Dauertor fährt diese Messung bei jedem Testlauf und wird rot, sobald irgendeine Klasse
kippt — dann wäre es ein Standardwert für einen fehlenden Messwert und die Bewertung hier
falsch.

---

## 7. Abnahme

**Je Tor ein roter und ein grüner Eichfall** (B4): `tests/test_stufe4_risikokern.py`,
**27 Fälle**, Beleg `06-abnahme-eichfaelle.txt`.

**Mutationsprobe** (`08-mutationsprobe.txt`) — ein Eichfall, der eine Rückkehr des Fehlers
nicht fängt, belegt nichts. Drei Rückfälle eingebaut und gemessen:

| Mutation | rote Fälle |
|---|---:|
| M1 `_validate_volume` wieder vor die Reduce-Weiche | **2** |
| M2 Kontoprüfung wirkungslos gemacht | **9** |
| M3 eine Lesestelle wieder ungeprüft | **1** |

Nach jeder Mutation aus einer **vor** dem Eingriff angelegten Kopie zurückgestellt (Lehre
aus F-010, nicht mit `git checkout`); Prüfsumme der Datei danach identisch:
`7f68a224…6cc`.

**Torlauf** (`07-torlauf.txt`): `ruff`, `mypy --strict`, `check_docs_claims`,
`check_doc_numbers`, `gen_docs --check`, `kopien_abgleichen --pruefen` je **Exit 0**;
`pytest` **1.431 bestanden, 0 fehlgeschlagen**.

---

## 8. Was offen bleibt — benannt, nicht behoben

**Ein werfendes Terminal.** Wirft `_terminal.account()` eine Ausnahme (statt `None` zu
liefern), reicht der Orderpfad sie unverändert weiter — ohne `reason`. Das ist **keine**
verfehlte Abnahme: „leere Kontodaten" heißt fehlende Daten, nicht eine abgerissene
Sitzung, und die Order bricht laut ab statt still durchzugehen. Es bliebe trotzdem
sauberer, sie in `VenueUnavailableError` zu übersetzen. Nicht in dieser Stufe geändert,
weil jede Ausnahme jedes Terminalaufrufs zu übersetzen ein eigener Umbau ist, der eigene
Messung braucht — und der Auftrag genau eine Stufe verlangt.

**Was diese Stufe ausdrücklich nicht tut:** sie ändert nichts am Befund (B) und macht
keine Aussage über einen Vorteil. Sie schließt zwei Löcher in einer Absicherung, die es
schon gab.
