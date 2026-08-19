# Stufe 3 — Simulator und Ergebnistor

*Erhoben 2026-08-19. Rohausgaben in `belege/`. Alle Mutationen wirklich gefahren.*

**Auftrag (§7, Stufe 3):** Ein ereignisgetriebener Simulator, der die Entscheidungskette
gegen die Historie fährt und je hypothetischem Trade Einstieg, Ausstieg, Gebühren, Spread,
Slippage, Finanzierungskosten, Teilausführungen und Entscheidungslatenz ausweist.
Rechenfehler in geldnahen Größen — Maximalverlust, Stückzahlberechnung, Kennzahleinheiten
— **vorher** korrigieren, mit rotem Eichfall je Korrektur. Vor dem ersten Lauf die
Vorregistrierung schreiben. Das Ergebnistor ist ein Haltepunkt.

> **Diese Stufe ist NICHT abgenommen.** Der Vorlauf ist erledigt und belegt; der Lauf
> selbst steht aus. Warum, steht in Abschnitt 4.

---

## 1. Die drei geldnahen Größen — einzeln nachgerechnet

Alle drei waren im verworfenen Stand `bitget-btc-ai` defekt. Das ist **kein** Grund,
sie hier als defekt anzunehmen. Jede wurde gemessen (Beleg:
`belege/01-geldnahe-groessen.txt`).

### 1.1 Maximalverlust — richtig

| Reihe | `_drawdown` |
|---|---:|
| reine Verluststrecke (Basis 1000, 5 × −100) | **0,500000** |
| kleiner Gewinn, dann Absturz | 0,999001 |
| Gewinn, dann halbe Rücknahme | 0,045455 |

Der Grund für den Unterschied zum verworfenen Stand steht im Code: `equity` beginnt bei
`equity_base = contract_size × volume × preis / hebel`, und die Funktion setzt
`peak = equity[0]`. Ein `equity_base <= 0` wirft. Dort startete der Peak bei 0, weshalb
eine reine Verluststrecke **0,0** meldete.

### 1.2 Stückzahlberechnung — richtig

`raw_volume = Risikobetrag / (Preisabstand × Kontraktgröße)` ergibt **Lots** und wird
gegen `volume_min`/`volume_step` geprüft — ebenfalls Lots. Handrechnung gegen die
Funktion: 50 / (1,10 × 50/10000 × 100000) = 0,090909 → abgerundet **0,09 Lots**, Notional
9.900, Marge 1.980. Der Defekt des verworfenen Standes — ein Währungsbetrag im Feld `qty`,
gegen Basiseinheiten geprüft — existiert hier nicht.

*Nebenbefund beim Nachrechnen:* `normalise_risk_fraction` klammert hart auf
**[0,25 %; 0,5 %]**. Mein Prüfwert von 1 % wurde auf 0,5 % heruntergeklemmt — meine erste
Handrechnung war deshalb falsch, nicht der Code.

### 1.3 Kennzahleinheiten — kein aktiver Fehler, aber eine scharfe Kante

Gemessen (N = 500, T = 1000):

| `observed_sharpe` | DSR |
|---|---:|
| 0,067 — richtig, je Beobachtung | 0,039193 |
| 1,0636 — **dieselbe Zahl, annualisiert** | **1,000000** |

Die vorregistrierte Schwelle ist 0,95. Eine Einheitenverwechslung dreht ein klares Nein
in ein perfektes Ja, lautlos und in die schmeichelnde Richtung.

**Aber: in diesem Stand ist das kein aktiver Fehler.** Der einzige Aufrufer im
Berichtspfad liest `report.trade_sharpe_per_obs` — ein Feld, das seine Einheit im Namen
trägt. Die Ereignisstudie rechnet ihren Wert zwei Zeilen vorher selbst als
Mittel/Streuung; eine falsche Einheit ist dort per Konstruktion unmöglich.

**Was ich daraufhin falsch gemacht habe,** steht in `fehler.md` F-007: ich habe eine
Laufzeitsperre gebaut, die **18 Fälle** brach — weil die betroffenen Reihen synthetische
Prüfdaten mit fast verschwindender Streuung sind und Sharpes von 23,98 bis 3,06 × 10¹³
erzeugen. Ein Streuungsartefakt, kein Einheitenfehler. Die Sperre ist zurückgenommen und
gelöscht (V1: kein Code ohne Aufrufer im Ausführungspfad).

**Geblieben ist, was ohne Preis wirkt:** die Feldwahl an der einen gefährlichen Zeile ist
über den Syntaxbaum festgenagelt. Eichfälle wirklich gefahren
(Beleg: `belege/02-eichfaelle-feldwahl.txt`):

| Mutation | Ergebnis |
|---|---|
| unverändert | `5 passed` |
| Feld auf `annualised_sharpe` umgeschrieben | **`2 failed, 3 passed`** |
| Feld auf `trade_sharpe` umgeschrieben | **`2 failed, 3 passed`** |
| zurückgenommen | `5 passed` |

**Neu aufgenommen als `SPAETER.md` S9:** bei entarteter Streuung sättigt die Deflation der
Ereignisstudie auf 1,0. Für die realen Läufe aus Paket 3a folgenlos (höchster DSR dort
0,686), aber unbemerkt in die schmeichelnde Richtung. Das ist ein Streuungs- und kein
Einheitenproblem und gehört an `backtest/resolution.py` angebunden, nicht mit einer
zweiten Plausibilitätsregel überklebt.

---

## 2. Deckt der Simulator die geforderte Aufschlüsselung?

Gemessen (Beleg: `belege/03-simulator-deckung.txt`):

| Geforderte Größe | vorhanden | wo |
|---|---|---|
| Einstieg | ja | `TradeRecord.entry_ts` |
| Ausstieg | ja | `TradeRecord.exit_ts` |
| Gebühren | ja | `BacktestReport.cost_commission` |
| Spread | ja | `cost_spread` |
| Slippage | ja | `cost_slippage` |
| Finanzierungskosten | ja | `cost_financing` **und** `carry_income`, getrennt geführt |
| Entscheidungslatenz | teilweise | shift(1): Entscheidung bei Bar *i*, gehalten über *i+1* |
| **Teilausführungen** | **nein** | 0 Treffer im gesamten Backtest-Paket |

**Sechs von acht vollständig, eine grob, eine fehlt.**

Zur Latenz: shift(1) ist eine bewusste, dokumentierte Modellierung und läuft in die
konservative Richtung (die Entscheidung wirkt erst eine Bar später). Sie ist grob — auf
H1 also eine Stunde —, aber sie ist keine Auslassung.

Zu den Teilausführungen: sie fehlen ganz. Bei fester Größe von einem Lot auf EURUSD ist
das nicht bindend — die Tiefe trägt das um Größenordnungen. Bindend wird es, sobald die
Größe steigt oder ein dünneres Instrument dazukommt. Das gehört benannt und nicht
stillschweigend übergangen; gebaut wird es hier nicht, weil es das Ergebnis des
anstehenden Laufs nicht ändern würde.

*Nicht gefordert und trotzdem vorhanden:* `MarketSpec.__post_init__` verbietet den
kostenfreien Modus — sind Spread, Slippage und Kommission alle 0, wirft es.

---

## 3. Zustand nach dem Vorlauf

`belege/04-schlusspruefung.txt`: `check_docs_claims`, `check_doc_numbers`,
`gen_docs --check`, `ruff` und `mypy` je **Exit 0**; `pytest` **1.403 bestanden,
1 fehlgeschlagen**.

Der eine rote Fall ist unverändert der seit `6cf80a6` eingecheckte `datetime`-Defekt in
`tools/live_betrieb.py:604` — Stufe 4 (V5), nicht diese Stufe.

---

## 4. Warum hier angehalten wird

Der Vorlauf ist erledigt. Der nächste Schritt wäre, die Vorregistrierung nach
`AUFTRAG/vorregistrierung/<datum>.md` zu schreiben und den ersten Lauf zu fahren. Beides
unterlasse ich, und zwar aus zwei Gründen, die zusammen zählen:

1. **H-002 ist unbeantwortet.** Der Stand trägt eine eigene, vorab bezifferte
   Abbruchregel, deren Empfehlung wörtlich „Bedingtes Halten (M5 gelb). Keine
   Strategiearbeit" lautet und deren Bedingung 6 ausgelöst ist. Ob ein Simulatorlauf auf
   der Entscheidungskette darunterfällt, ist eine Auslegung, die der Auftraggeber trifft
   — nicht ich. §6 des Auftrags ist an dieser Stelle eindeutig: eine Schwelle wird nie
   verschoben, damit etwas durchgeht.
2. **Die Vorregistrierung ist unwiderruflich, und jeder Lauf verbraucht einen Versuch.**
   „Diese Datei wird danach nicht mehr geändert." Vom Kampagnenbudget sind 53 von 60
   Versuchen offen, befristet bis 2027-08-17. Eine Vorregistrierung unter einer
   ungeklärten Abbruchregel zu schreiben, hieße, den Maßstab zu setzen, bevor feststeht,
   ob überhaupt gemessen werden darf.

**Das ist keine Verzögerung aus Vorsicht.** Alles, was ohne diese Entscheidung getan
werden kann, ist getan: die geldnahen Größen sind nachgerechnet, der eine gefährliche
Punkt ist festgenagelt, die Deckung des Simulators ist beziffert, und die Datengrundlage
aus Stufe 1 liegt geprüft bereit (EURUSD H1, 18.715 Bars, 2022-01-02 … 2024-12-31,
Prüfsumme `8cdebf05…`).

**Was der nächste Lauf braucht,** wenn die Entscheidung „zulässig" lautet:

1. Vorregistrierung schreiben — Mindestzahl Trades, Mindest-Erwartungswert nach Kosten,
   Signifikanzmaß, Kostenannahme einschließlich der 1,5-fachen, Stand des
   Versuchszählers (**7 von 60**).
2. Erst danach `run_registered_backtest` gegen die Reihe aus Stufe 1 fahren. Jeder Lauf,
   auch ein abgebrochener, schreibt vorher in `TRIALS.jsonl`.
3. Fällt das Ergebnis unter die vorregistrierte Schwelle, ist das Befund **(B)** aus §1 —
   ein gültiges Ende des Auftrags, kein Anlass nachzujustieren.
