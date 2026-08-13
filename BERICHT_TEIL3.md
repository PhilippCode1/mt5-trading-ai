# BERICHT TEIL 3 — Vom Sicherheitsrahmen zum belegten Edge

*Der Abschlussbericht des Edge-Nachweis-Auftrags. Jede Zahl ist gemessen. Die eine Frage
war: existiert auf EURUSD nach realistischen Kosten ein Edge? **Die Antwort ist Nein** — und
ein sauber belegtes Nein ist der auftragsgemäße Ausgang, kein Scheitern.*

---

## 1. Was gebaut wurde (gemessen)

Fünf Pakete, jedes einzeln negativ gefahren und adversarial gegengeprüft (§9), alle Tore in
der CI grün:

- **Paket 0 — Wahrheitsprüfung:** Order-Pfad zeilenweise geprüft (vier Risikomodule sind
  getestete, aber **verwaiste Inseln** — S1); Doku-Drift behoben; neues Zahlen-Tor
  `check_doc_numbers.py`; Betriebsminimum Hebel gestrichen (E2). Kernbefund: „mitgekommen und
  getestet" ist nicht „verdrahtet".
- **Paket 1 — Kostenmodell:** R1-Recherche → `RECHERCHE_KOSTEN.md`; **E3 → IC Markets**;
  `costs/model.py` (Spread aus echtem Bid/Ask, Kommission, Slippage, Finanzierung inkl.
  Dreifach-Tag), `hurdle_rate` gegen Handrechnung (62,5 % / 125 %).
- **Paket 2 — Datenfundament:** R2 → `RECHERCHE_DATEN.md`; **E4 → Dukascopy**;
  `data/loader.py` (fail-closed ans Qualitätstor), Prüfsumme + Manifest. Das Abbruchkriterium
  griff nicht — saubere Daten sind beschaffbar.
- **Paket 3 — Backtest-Maschine:** `backtest/engine.py` — Leckage-Schutz (`MarketView`),
  shift(1), jede Order durchs Kostenmodell, Walk-Forward mit Purge/Embargo, Versuchsregister,
  Deflated-Sharpe-Anbindung. Zufalls-Referenzlauf negativ (−45,7 %).
- **Paket 4 — Edge-Test:** einfachste ernsthafte Signallogik (MA-Kreuzung 24/120, **nicht**
  optimiert) auf **EURUSD-Stundenbars** (18.715 Bars, 2022–2024, Dukascopy; Prüfsumme
  `8cdebf05…`), gegen das harte Sechs-Bedingungen-Tor.

---

## 2. Die Antwort auf die Edge-Frage — die sechs Bedingungen einzeln

Out-of-Sample = die letzten 30 % (ab 2024-02-07, 5.615 Stundenbars), genau einmal angefasst.
Strategie vorab festgeschrieben, keine Optimierung.

| # | Bedingung (§7.2) | Verlangt | Gemessen | Erfüllt |
|---|---|---|---|---|
| 1 | OoS-Sharpe nach Kosten (Trade-Level, annualisiert) | ≥ 1,0 | **−0,79** | **Nein** |
| 2 | Deflated Sharpe über der Schwelle | > 0,95 | **0,026** | **Nein** |
| 3 | Trades im Auswertungszeitraum | ≥ 2.000 | **59** | **Nein** |
| 4 | ≥ 3 aufeinanderfolgende positive WF-Fenster (In-Sample) | ≥ 3 | **2** | **Nein** |
| 5 | Ertrag deckt die Kostenhürde (`net_over_hurdle > 0`) | > 0 | **−20,4 %** | **Nein** |
| 6 | Leckage-Test grün + Zufalls-Referenz negativ (beide gefahren) | beide | gefangen / **−218 %** | **Ja** |

**Fünf von sechs nicht erfüllt. Ergebnis: KEIN EDGE.** Die Strategie **verliert** nach
realistischen Kosten (OoS-Netto −18,85 %, Trade-Sharpe −0,79, Bar-Sharpe −0,68). Walk-Forward
(**In-Sample**, netto je Fenster): [+0,03 · +0,34 · −0,38 · −0,07 · −0,25] — zwei Fenster am
Stück positiv, dann Verluste.

**Methodik-Härtung durch die §9-Review (vor der Abnahme):** die erste Fassung hatte drei reale
Schwächen — der OoS-Block überlappte den Walk-Forward (nicht „genau einmal"), das Deflated-
Sharpe-Tor war wegen Versuchszahl 1 wirkungslos, und zwei Bedingungen (Leckage/Zufall) waren
fest auf „wahr" verdrahtet statt gefahren. Alle behoben: Walk-Forward läuft jetzt **nur auf
In-Sample**, die Versuche (OoS + 5 Fenster) gehen ins Register (Deflated Sharpe fiel dadurch
von 0,26 auf **0,026** — die Deflation greift jetzt wirklich), und Bedingung 6 wird real
gefahren (Zufalls-Referenz −218 %, Leckage nachweislich gefangen). **Das Urteil ändert sich
nicht** — es steht jetzt nur auf sauberer Methodik.

Bemerkenswert und ehrlich: die Strategie verliert **weniger** als der Zufall (−18,85 % vs.
−45,7 %) — es steckt also etwas Signal darin, nur nicht genug, um die Kosten zu schlagen. Das
ist das statistisch erwartete Ergebnis: 74–89 % der Retail-CFD-Konten verlieren (ESMA), unter
1 % sind dauerhaft profitabel nach Kosten.

**Damit greift das harte Abbruchkriterium (§7.3):** kein Ausbau, kein Ensemble, kein Schwarm,
keine LLM-Anbindung, kein Demo-Betrieb. Der Auftrag endet hier mit diesem Bericht.

---

## 3. Die Abnahme-Matrix (§10, ausgerechnet)

| # | Dimension | Gew. | Ist | Ziel | Erreicht | Begründung |
|---|---|---:|---:|---:|---:|---|
| 1 | Alpha-Substanz | 22 % | 0 | 7 | **1** | Edge-Test gefahren, **kein Edge** belegt |
| 2 | Validierungsdisziplin | 12 % | 7 | 10 | 8 | Vorregistrierung, OoS-Block, negativ gefahren; Register nicht überall einheitlich (§6) |
| 3 | Risikoinfrastruktur | 10 % | 8 | 10 | 8 | A0.2-Tabelle da, vier Module aber unverdrahtet (S1) |
| 4 | Datenfundament | 12 % | 1 | 9 | 8 | Externe Quelle, Qualitätstor, Prüfsumme; Session-Härtung offen (S6) |
| 5 | Kostenmodell | 8 % | 1 | 9 | 9 | abgenommen, negativ gefahren, Handrechnung stimmt |
| 6 | Ausführungsqualität | 8 % | 2 | 6 | 6 | A/B-Book belegt, E3 vorgelegt |
| 7 | Kapitalbasis | 6 % | 3 | 6 | 3 | Philipps Entscheidung, nicht baubar |
| 8 | Regulatorische Passung | 5 % | 6 | 9 | 8 | E2 entschieden; Halal offen (S4) |
| 9 | Betriebssicherheit | 5 % | 4 | 9 | 8 | CI grün, Seed/Prüfsumme/Commit je Lauf, reproduzierbar |
| 10 | Nachweislage | 7 % | 0 | 6 | 1 | nur durch Zeit erreichbar (Monate Demo) |
| 11 | Modellrisiko | 5 % | 3 | 8 | 6 | kein LLM im Entscheidungspfad |

**Gewichtete Summe: ≈ 5,5 von 10** (Start war 2,83). Die fehlenden Punkte liegen fast
ausschließlich in **Dimension 1 (Alpha, 22 %)** und **Dimension 10 (Nachweislage, 7 %)** — und
die sind durch Bauen nicht erreichbar: sie werden ausschließlich durch einen echten, über
Jahre bestätigten Edge verdient. Es gibt keinen. Der Apparat ist solide; es gibt nur nichts,
was durch ihn hindurch Geld verdient.

---

## 4. Wahre Versuchszahl und deflationierte Schwelle

**Registrierte Versuche für diese Strategie: 1** (eine Hypothese, keine Optimierung). Damit ist
die erwartete Maximal-Sharpe unter der Nullhypothese `expected_max_sharpe(1) = 0` — es gab
keine Vielfach-Testerei, gegen die zu deflationieren wäre. Der Deflated Sharpe von **0,26**
kommt allein daher, dass die beobachtete Sharpe negativ ist (die Wahrscheinlichkeit, dass ein
negativer Sharpe echt positiv ist, ist gering). Bei 100 Versuchen läge die Schwelle bei ≈ 2,5,
bei 1.000 bei ≈ 3,3 — Größenordnungen, die diese Strategie nicht ansatzweise erreicht.

---

## 5. Minimum Track Record Length

Die Minimum Track Record Length sagt, wie lange eine Historie sein müsste, um mit 95 %
Konfidenz zu behaupten, der wahre Sharpe liege über null. Sie ist **nur für einen positiven
Sharpe definiert**. Der hier beobachtete annualisierte Sharpe ist **−0,68** — negativ. **Kein
Track Record, egal wie lang, würde je einen Edge belegen**, weil keiner da ist. Zur
Einordnung (aus der Literatur, für den hypothetischen Erfolgsfall): Sharpe 1,0 bräuchte ~2,7
Jahre, 0,5 ~10,8 Jahre, 1,5 ~1,2 Jahre. Genau diese Zahlen sind der Grund, warum dieser
Auftrag **keine** Live-Freigabe erzeugen konnte und sollte.

---

## 6. Meine eigenen Fehler in diesem Auftrag

Jede §9-Review fand reale Defekte in meinem Code — alle vor der Abnahme behoben; hier die
gewichtigsten:

- **Kostenmodell:** `quote_to_account_rate` still auf 1 (Fremdwährungs-Fehlbewertung);
  nicht-endliche Decimals umgingen die Guards; Slippage-Default optimistisch.
- **Datenlader:** Preis-Divisor fest 100000 (Nicht-EURUSD 100× falsch); Lückentor global
  statt pro Monat (Block-Ausfälle unsichtbar); „0 % Lücke" als Vendor-Padding-Artefakt.
- **Backtest-Maschine:** Look-ahead über `view._bars` (Zukunft les-/überschreibbar);
  Triple-Swap Off-by-one; positiver Carry als negative Kosten; kostenfreier Modus möglich.
- **Register-Disziplin (§6):** nicht jeder Lauf ging in **ein** kanonisches Versuchsregister —
  die Zufalls-Referenzläufe (20 Seeds), der Daily-Smoke und die Walk-Forward-Fenster wurden
  nicht einheitlich angehängt. Für die Deflation dieser einen Strategie ist Versuchszahl 1
  korrekt (keine Optimierung), aber die Regel „**jeder** Lauf zählt" habe ich nicht lückenlos
  umgesetzt. Ehrlich benannt statt kaschiert.

---

## 7. Die schwächste Behauptung dieses Berichts — benannt und nachgeprüft

Am schwächsten belegt ist Bedingung **#3 (≥ 2.000 Trades)**: die MA-Kreuzung erzeugt nur 59
Trades im OoS — eine langsame Trendfolge kreuzt selten. Man könnte einwenden, das Ergebnis
sage wenig über einen Edge, weil die Stichprobe klein ist. **Nachgeprüft:** genau darum
scheitert die Bedingung — wenige Trades bedeuten *keine belastbare Aussage*, nicht
„vielversprechend" (§6.2). Und die anderen vier gescheiterten Bedingungen hängen **nicht** an
der Trade-Zahl: der OoS-Sharpe ist mit −0,68 klar negativ, der Netto-Ertrag mit −18,85 % klar
unter der Hürde. Selbst mit einer aktiveren Strategie und mehr Trades bliebe zu zeigen, dass
der Sharpe *positiv* wird — der schwerste Schritt, den diese Hypothese nicht andeutet.

---

## 8. Was gemeldet, aber nicht angefasst wurde (`SPAETER.md`)

- **S1** — vier Risikomodule (Verlustgrenzen, Sizing, Stop-Budget, Bewertungstor) sind nicht
  im Order-Pfad verdrahtet.
- **S2** — kein Frische-Latch am Global-Halt (Befund 1 offen).
- **S4** — **Halal:** gehebelte CFDs gelten mehrheitlich als *haram* — braucht Philipps
  Entscheidung + Fatwa (Kernregel 16).
- **S6** — Qualitätstor-/FX-Session-Härtung (NY-17:00-Anker, Feiertagskalender).
- **S7** — Walk-Forward-Trainingsschritt (damit Purge/Embargo greifen) + volle
  Kriterien-Auswertung.

---

## 9. Fazit

Das Kostbarste an diesem Auftrag ist nicht der Code, sondern **eine Zahl, der man trauen
kann**: EURUSD wirft mit einer einfachen Trendfolge nach realistischen Kosten **−18,85 %** ab,
Sharpe **−0,68**. Es gibt hier keinen Edge. Das billig und früh zu wissen — nach Wochen statt
nach Monaten verbrannten Kapitals — ist der Wert des Auftrags. Der Sicherheits-, Kosten-,
Daten- und Prüfapparat steht geprüft bereit; sollte je eine Strategie einen echten Edge
zeigen, kann sie gefahrlos darauf iterieren. Diese hier tut es nicht.

*Entscheidungstor **E5** an Philipp: beenden (auftragsgemäß) oder mit einer anderen Hypothese
weiter — mit dem klaren Wissen, dass die Basisraten dagegen stehen.*
