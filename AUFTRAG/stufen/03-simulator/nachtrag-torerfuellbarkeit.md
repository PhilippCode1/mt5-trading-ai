# Nachtrag zu Stufe 3 — ist das vorregistrierte Tor überhaupt erfüllbar?

*Geschrieben am 2026-08-19, **nach** dem Ergebnistor, auf Anweisung des Auftraggebers
(„weiter mit Stufe 3"). Beleg: [`belege/07-torerfuellbarkeit.txt`](belege/07-torerfuellbarkeit.txt).
Bestätigt durch Ausführung — die Ausgabe liegt vollständig bei.*

---

## 0. Warum dieser Nachtrag und kein vierter Lauf

Das Ergebnistor ist erreicht, und der Vertrag ist an dieser Stelle eng. §6, Stufe 3:

> „Fällt das Ergebnis unter die vorregistrierte Schwelle, ist das der Befund (B) … Du
> justierst dann nicht nach, du suchst keine bessere Parametrierung, du erweiterst nicht
> den Suchraum."

Ein vierter Hypothesenlauf wäre genau das. **Es gibt aber eine Frage, die kein
Strategielauf beantwortet und die vor jedem weiteren Versuch steht:** Die drei
gefahrenen Hypothesen erreichten 59, 123 und 58 Trades gegen eine vorregistrierte
Mindestzahl von 2.000 — sie verfehlten Bedingung 3 um den Faktor **16 bis 34**. Wenn das
Tor bei der von ihm selbst verlangten Handelsfrequenz nach Kosten nicht mehr erreichbar
ist, dann belegen die drei Fehlschläge nicht das Fehlen eines Vorteils, sondern die
Unerfüllbarkeit des Maßstabs. Das wäre ein anderer Befund als (B).

Diese Frage ist **eine Eigenschaft des Tors**, keine des Marktes und keine der
Hypothesen. Sie lässt sich ohne Backtest beantworten. Der Nachtrag tut genau das:

- **kein Backtest**, keine Hypothese, kein Edge-Urteil,
- **kein verbrauchter Versuch** — der Registerstand bleibt bei 31 von 60 (Begründung:
  [`../../entscheidungen.md`](../../entscheidungen.md), E-008),
- **keine geänderte Schwelle** — jede wird gelesen, keine gesetzt,
- gemessen wird auf dem **In-Sample-Block**; der OoS-Block steht nur als Gegenprobe auf
  Stationarität daneben und geht in keine Zahl ein, die etwas entscheidet.

Werkzeug: [`tools/torerfuellbarkeit.py`](../../../tools/torerfuellbarkeit.py), Eichfälle in
`tests/test_torerfuellbarkeit.py` (12 Fälle, fünf davon rot fahrend).

---

## 1. Was gemessen wurde

Alle Eingangsgrößen werden **gelesen**, keine wiederholt: `min_trades`,
`min_oos_sharpe` und `min_deflated_sharpe` aus `backtest/edge.py::EdgeThresholds`,
`OOS_FRACTION` aus `tools/edge_test.py`, die Bars über `load_verified_csv` mit
Prüfsummenabgleich, die Kosten über `costs/model.py::order_roundturn_cost` — dieselbe
Funktion, die der Backtest je Trade aufruft.

| Größe | Wert | Herkunft |
|---|---:|---|
| Reihe | EURUSD H1, 18.715 Bars, 2022-01-02 … 2024-12-31 | Stufe 1, unabhängig beschafft |
| Prüfsumme | `8cdebf05…4daa` | stimmt mit der Vorregistrierung überein |
| In-Sample / OoS | 13.100 / 5.615 Bars (30 %) | `OOS_FRACTION` |

### 1.1 Was Bedingung 3 an Frequenz verlangt

| | |
|---|---:|
| Mindest-Trades im OoS-Block | **2.000** |
| OoS-Bars | 5.615 |
| **→ mittlere Haltedauer** | **2,81 Bars = 2,81 Handelsstunden** |
| OoS-Kalenderspanne | 0,899 Jahre |
| **→ Trades je Jahr** | **2.224** |

### 1.2 Was ein Trade kostet

| Posten | bp des Nominals | Anteil an K |
|---|---:|---:|
| Spread | 0,0931 | 5,6 % |
| Kommission | 0,6516 | 38,9 % |
| **Slippage** | **0,9309** | **55,6 %** |
| Finanzierung (0 Nächte) | 0,0000 | 0 % |
| **K gesamt** | **1,6756** | 100 % |

### 1.3 Was der Markt über diesen Horizont hergibt

Gemessen über 13.098 überlappende 2-Bar-Fenster im In-Sample-Block:

| Größe | Wert |
|---|---:|
| Mittel \|Bewegung\| **m** | **10,7446 bp** |
| Streuung der vorzeichenbehafteten Bewegung **s** | **16,2836 bp** |
| Verhältnis s/m | 1,516 |

Zum Verhältnis: bei einer Normalverteilung wäre s/m = 1,253. Der gemessene Wert liegt
darüber — die Ränder sind schwerer als normal. Das macht die Sharpe-Bedingungen härter,
nicht weicher: mehr Streuung je Einheit mittlerer Bewegung heißt mehr nötiger
Erwartungswert für dieselbe Sharpe.

---

## 2. Befund I — welche Bedingung eigentlich bindet

Bedingung 1 (Sharpe ≥ 1,0) und Bedingung 2 (Deflated Sharpe > 0,95) stehen auf
**derselben Größe**: der Sharpe je Trade. Welche von beiden bindet, sagt keine der
Schwellen von sich aus, und **kein früherer Bericht dieses Vorhabens hat es
ausgerechnet.** Gerechnet wird es hier, indem `deflated_sharpe_ratio` — dieselbe
Funktion, die das Tor benutzt — per Intervallhalbierung umgekehrt wird:

| | Sharpe je Trade | dasselbe annualisiert |
|---|---:|---:|
| Bedingung 1 verlangt | 0,02121 | **1,000** (die dokumentierte Zahl) |
| Bedingung 2 verlangt | **0,08942** | **4,217** |

> **Bedingung 2 ist um den Faktor 4,22 strenger als Bedingung 1.** Die überall genannte
> Schwelle „Trade-Sharpe ≥ 1,0" ist **nicht** der wirksame Anspruch des Tors. Wirksam
> sind 4,22.

Das ist keine Schwellenänderung — beide Zahlen stehen unverändert seit Paket 4 im Code.
Es ist die erste Messung dessen, was sie **zusammen** bedeuten.

**Hängt der Faktor an der gewählten Versuchszahl?** Nein, nur schwach:

| Versuche der Kampagne | nötige Sharpe je Trade | annualisiert |
|---:|---:|---:|
| 7 (Stand vor Stufe 3) | 0,06788 | 3,201 |
| 31 (Stand nach Stufe 3) | 0,08361 | 3,943 |
| 60 (vorregistriert) | 0,08942 | 4,217 |
| 120 (hypothetisch) | 0,09502 | 4,481 |

Selbst bei nur sieben Versuchen verlangt Bedingung 2 eine annualisierte Sharpe von 3,20.
Der Befund ist damit nicht davon abhängig, wie viele Versuche gezählt werden.

---

## 3. Befund II — das Tor ist erfüllbar, aber die Zahl dazu ist unbequem

Gegen die **bindende** Bedingung gerechnet (nicht gegen die schwächere — das wäre die
schmeichelnde Richtung):

| Größe | In-Sample | OoS (Gegenprobe) |
|---|---:|---:|
| nötiger Netto-Ertrag je Trade **E = S_t · s** | 1,4561 bp | 0,9763 bp |
| Kosten je Trade **K** | 1,6756 bp | 1,6756 bp |
| brutto nötig **E + K** | 3,1317 bp | 2,6519 bp |
| mittlere Bewegung **m** | 10,7446 bp | 6,9919 bp |
| **einzufangender Anteil f = (E+K)/m** | **29,1 %** | **37,9 %** |
| dasselbe als Trefferquote (1:1 auf ±m) | **64,57 %** | **68,96 %** |
| nur die Kosten decken | 57,80 % | — |

**f < 1. Das Tor ist rechnerisch erfüllbar.** Es verlangt keine Unmöglichkeit — es
verlangt, dass eine Strategie im Mittel **29 % jeder Zwei-Stunden-Bewegung netto
einfängt**, über 2.000 aufeinanderfolgende Trades. Als Trefferquote gelesen: **64,6 %**,
gegen 57,8 %, die schon der Nulldurchgang kostet.

**Damit steht Befund (B).** Er ist nicht das Artefakt eines unmöglichen Maßstabs. Das war
die Frage, und sie ist beantwortet.

---

## 4. Befund III — der größte Kostenposten ist nicht gemessen

**0,9309 von 1,6756 bp = 55,6 % der Round-Turn-Kosten sind Slippage.** Sie ist größer als
Kommission (38,9 %) und zehnmal so groß wie der Spread (5,6 %).

`config/broker_costs.json` führt sie wörtlich als **„ANNAHME, keine Messung"** und
vermerkt selbst, die Annahme sei „bewusst am unteren Rand gewählt". Der Posten, der die
Kostenrechnung dominiert, ist damit der einzige, der nicht erhoben wurde — und er ist zu
Gunsten des Systems angesetzt.

Das ist keine neue Erkenntnis über die Datei, aber es ist die erste Messung ihres
**Gewichts**. Es verbindet sich unmittelbar mit Abbruchbedingung 3 („Realisierte Kosten
weichen ab — ausgelöst mangels Messung"): die Bedingung ist nicht nur formal offen,
sondern sie betrifft die Mehrheit der Kostenzahl.

---

## 5. Befund IV — der Block, an dem geurteilt wird, ist der schwerere

| | In-Sample | OoS | Differenz |
|---|---:|---:|---:|
| Mittel \|Bewegung\| | 10,7446 bp | 6,9919 bp | **−34,9 %** |
| Streuung | 16,2836 bp | 10,9178 bp | −33,0 % |

Der Out-of-Sample-Block bewegt sich rund ein Drittel weniger als der In-Sample-Block —
2022 war ein außergewöhnlich bewegtes Jahr, 2024 nicht. Die Kosten bleiben dabei
unverändert. Der Anspruch steigt entsprechend von 29,1 % auf **37,9 %** der Bewegung
(Trefferquote 64,57 % → **68,96 %**).

Das ist keine Kritik am Aufbau — ein OoS-Block soll nicht ausgesucht werden. Es ist eine
Größe, die bei jeder Auslegung eines künftigen Versuchs auf dem Tisch liegen muss.

---

## 5b. Befund V — wo der Anspruch im überhaupt Möglichen liegt

`f = 29,1 %` sagt, welchen Anteil der Bewegung das Tor verlangt. Es sagt **nicht**, wie
weit dieser Anspruch vom überhaupt Erreichbaren entfernt liegt — und ein Tor bei 90 % der
Obergrenze und eines bei 10 % sind beide „erfüllbar" und bedeuten völlig Verschiedenes.

Die Obergrenze ist berechenbar: ein Hellseher, der das Vorzeichen jeder Zwei-Stunden-
Bewegung kennt, sie ganz mitnimmt und dabei jedes Mal die vollen Kosten zahlt. Gerechnet
auf **nicht überlappenden** Fenstern — es geht um eine Folge tatsächlich nacheinander
gehaltener Positionen, nicht um dieselbe Bewegung mehrfach kassiert.

| | |
|---|---:|
| nicht überlappende Trades | 6.549 |
| Netto je Trade (\|Bewegung\| − K) | 8,9741 bp |
| Streuung | 12,2494 bp |
| **Sharpe je Trade** | **0,7326** |
| dasselbe annualisiert | 34,55 |
| das Tor verlangt je Trade | 0,08942 |
| **→ das Tor liegt bei** | **12,2 % der Obergrenze** |

Die annualisierte 34,55 ist die Plausibilitätsprobe: perfekte Voraussicht *muss* eine
absurde Zahl ergeben. Täte sie es nicht, wäre etwas an Kosten oder Horizont falsch.

**Was die 12,2 % sagen — und was nicht.** Sie sagen, dass der Anspruch des Tors weit
unterhalb dessen liegt, was diese Reihe bei dieser Frequenz und diesen Kosten hergibt. Er
ist also nicht durch die Daten selbst ausgeschlossen. Sie sagen **nicht**, dass „12 %
Können genügen": die Sharpe wächst nicht linear mit der Trefferquote, der Prozentsatz ist
eine Ortsangabe im Möglichen, keine Anforderung an das Können. Die Anforderung an das
Können steht in §3 und lautet 64,6 % Trefferquote.

Der Eichfall dazu prüft die Eigenschaft, wegen der die Zahl überhaupt taugt: der
Hellseher muss auf denselben Fenstern sowohl eine Immer-Long- als auch eine
Immer-Short-Strategie im Netto-Ertrag schlagen. Eine Obergrenze, die unterboten werden
kann, ist keine.

---

## 6. Was daraus für die drei gefahrenen Läufe folgt

Die drei Hypothesen erreichten 59, 123 und 58 Trades. Das Tor verlangt 2.000. Sie waren
damit **nie in dem Frequenzbereich, für den das Tor geschrieben wurde** — es ist auf eine
Strategie mit Haltedauer unter drei Stunden ausgelegt, gefahren wurden Strategien mit
Haltedauern von Tagen.

Das ist eine **Auslegungslücke der Kampagne**, keine Tatsache über den Markt. Sie ändert
Befund (B) nicht, und zwar aus einem Grund, der ausdrücklich hingehört: die drei Läufe
sind nicht nur an Bedingung 3 gescheitert, sondern auch an 1, 2 und 4. Die beste
OoS-Sharpe war 0,185 gegen 1,0 — sie verfehlt selbst die **schwächere** der beiden
Sharpe-Bedingungen um den Faktor 5,4 und die bindende um den Faktor 22,8.

Was der Trade-Zahl-Fehlschlag allein **nicht** trägt: eine Aussage über den Vorteil.
Wer künftig „drei Hypothesen sind am Sechs-Bedingungen-Tor gescheitert" liest, sollte
mitlesen, dass eine der sechs Bedingungen von diesen Hypothesen konstruktionsbedingt
nicht erreichbar war.

---

## 7. Was schiefging

**Die verwechselte Streuung — in diesem Lauf gefunden und vor jedem Ergebnis behoben.**
Die erste Fassung der Rechnung hat die Streuung der **Beträge** `|Bewegung|` in die
Sharpe-Rechnung gegeben. Richtig ist die Streuung der **vorzeichenbehafteten** Bewegung:
die Auszahlung eines Trades ist `Richtung × Bewegung − K` und streut mit der
vorzeichenbehafteten Größe. Beide Zahlen sind plausibel (12,24 gegen 16,28 bp), liegen in
derselben Größenordnung, und die falsche macht das Tor **leichter** aussehen (f wäre
18,0 % statt 18,8 % gewesen — gerechnet damals noch gegen die unbindende Bedingung 1).

Gefunden habe ich es durch Nachrechnen der Größenordnung, nicht durch einen Test. Der
Fall, der es künftig fängt, steht jetzt in
`tests/test_torerfuellbarkeit.py::test_streuung_ist_die_der_vorzeichenbehafteten_bewegung_nicht_der_betraege`
und ist gegen eine Reihe gebaut, bei der die beiden Zahlen um Faktor 10 auseinanderfallen.
Vollständig in [`../../fehler.md`](../../fehler.md), F-009.

---

## 8. Was unterstellt ist — ausdrücklich, damit es nachprüfbar bleibt

Diese Rechnung ist eine Größenordnungs-Rechnung, keine Simulation. Drei Annahmen tragen
sie, und alle drei sind angreifbar:

1. **Symmetrische 1:1-Auszahlung ±m** für die Übersetzung in eine Trefferquote. Reale
   Strategien haben asymmetrische Auszahlungen (Stop und Ziel verschieden weit); die
   Trefferquote ist dann eine andere Zahl. Der **Anteil f** ist von dieser Annahme
   unabhängig — nur seine Übersetzung in Prozent Trefferquote nicht.
2. **Die Streuung der Trade-Auszahlung wird durch die Streuung der unbedingten Bewegung
   angenähert.** Eine Strategie, die nur in bestimmten Lagen handelt, hat eine andere
   Streuung. Die Richtung des Fehlers ist offen.
3. **Überlappende Fenster.** Für die Frage „wie weit bewegt sich der Kurs in dieser
   Zeitspanne" ist jede Startposition ein gültiger Beobachtungspunkt. Für einen
   Signifikanztest wären sie falsch — hier wird keiner gerechnet.

Was **nicht** unterstellt ist: die Kosten (aus der Funktion des Backtests), die Schwellen
(aus dem Code), die Bars (prüfsummengesichert), die Deflation (aus der Funktion des
Tors).

---

## 9. Gegenprobe: rechnet diese Kette dasselbe wie die gefahrenen Läufe?

Ein Apparat, der sich selbst bestätigt, belegt nichts. Die Kette wurde deshalb gegen eine
**unabhängig bekannte** Zahl geprüft: `BERICHT_TEIL3.md` weist für die Mittelwertrückkehr
eine per-Trade-Sharpe von ≈ 0,016 bei 123 Trades und einen **Deflated Sharpe von 0,0150**
aus.

Dieselbe Funktion, mit denselben Eingaben aufgerufen, ergibt **0,0151**.

Die Abweichung liegt in der Rundung der zitierten Sharpe (0,016 ist selbst gerundet). Die
Kette reproduziert damit eine Zahl, die vor diesem Nachtrag und unabhängig von ihm
entstanden ist.

---

## 10. Zusammengefasst

| Frage | Antwort | Bezugsgröße |
|---|---|---|
| Ist das Tor auf dieser Reihe erfüllbar? | **Ja** | f = 29,1 % < 100 % |
| Steht Befund (B)? | **Ja, unverändert** | er ist kein Artefakt des Maßstabs |
| Was verlangt das Tor wirklich? | **annualisierte Sharpe 4,22**, nicht 1,0 | Bedingung 2 bindet, Faktor 4,22 |
| Was heißt das praktisch? | **64,6 % Trefferquote** über 2.000 Trades à 2 Stunden | 57,8 % kostet allein der Nulldurchgang |
| Auf dem OoS-Block? | **69,0 %** | der Block bewegt sich 34,9 % weniger |
| Wie belastbar ist die Kostenzahl? | **55,6 % davon ist eine Annahme** | Slippage, nie gemessen |
| Wo liegt der Anspruch im Möglichen? | bei **12,2 % der Obergrenze** | Hellseher: Sharpe je Trade 0,7326 |

**Für den Auftraggeber heißt das:** Option 3 aus [`../../rueckbau-bestandsaufnahme.md`](../../rueckbau-bestandsaufnahme.md)
— eine neu begründete Hypothese — hat jetzt eine Zahl. Wer sie zieht, muss eine Strategie
begründen können, die über 2.000 Trades hinweg annähernd **zwei von drei** Zwei-Stunden-
Bewegungen richtig trifft, auf einem der liquidesten Märkte der Welt, gegen Kosten, deren
größter Posten noch nie gemessen wurde. Das ist keine Empfehlung gegen den Versuch — es
ist die Zahl, die vorher auf dem Tisch liegen sollte.
