# BERICHT TEIL 3 — Vom Sicherheitsrahmen zum belegten Edge

*Der Abschlussbericht des Edge-Nachweis-Auftrags. Jede Zahl ist gemessen. Die eine Frage
war: existiert auf EURUSD nach realistischen Kosten ein Edge? Getestet wurden nacheinander
**drei** vorab festgeschriebene Hypothesen (Trendfolge, Mittelwertrückkehr, Volatilitäts-
Ausbruch — jeweils nach E5 = weiterbauen). **Die Antwort ist Nein** — und ein sauber belegtes
Nein ist der auftragsgemäße Ausgang, kein Scheitern. §11 dokumentiert das spätere Paket 5 auf
ausdrückliche Anweisung.*

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
  Dreifach-Tag). (Die separate `hurdle_rate`-Funktion wurde in **Abnahme-Paket 3** als toter
  Code entfernt — die einzige, genutzte Hürdenformel steht im Backtest-Bericht selbst.)
- **Paket 2 — Datenfundament:** R2 → `RECHERCHE_DATEN.md`; **E4 → Dukascopy**;
  `data/loader.py` (fail-closed ans Qualitätstor), Prüfsumme + Manifest. Das Abbruchkriterium
  griff nicht — saubere Daten sind beschaffbar.
- **Paket 3 — Backtest-Maschine:** `backtest/engine.py` — Leckage-Schutz (`MarketView`),
  shift(1), jede Order durchs Kostenmodell, Walk-Forward mit Purge/Embargo, Versuchsregister,
  Deflated-Sharpe-Anbindung. Zufalls-Referenzlauf negativ (−45,7 %).
- **Paket 4 — Edge-Test:** drei einfachste ernsthafte Signallogiken (**nicht** optimiert) auf
  **EURUSD-Stundenbars** gegen das harte Sechs-Bedingungen-Tor: Trendfolge (MA-Kreuzung 24/120),
  Mittelwertrückkehr (z-Score 48) und Volatilitäts-Ausbruch (Donchian 48) — jeweils nach
  Philipps E5-Entscheid „weiterbauen". In-Sample 2022–2024 (18.715 Bars, Prüfsumme `8cdebf05…`);
  Versuch 3 auf frischem OoS 2025–26 (9.850 Bars, `08a6e4c9…`).

---

## 2. Die Antwort auf die Edge-Frage — zwei Hypothesen durch dasselbe Tor

Getestet wurden **drei** vorab festgeschriebene, nicht optimierte Hypothesen auf demselben
Instrument (EURUSD H1). Nach jedem Nein legte ich E5 vor; Philipps Entscheidung war jeweils
**weiterbauen mit einer anderen Hypothese**. Alle Läufe zählen ins selbe Register (18 Versuche,
je Strategie 6). Versuch 1 und 2 teilten sich einen Out-of-Sample-Block (letzte 30 % von
2022–2024, ab 2024-02-07) — je Strategie einmal angefasst, insgesamt zweimal (Selektionsbias,
§7). **Versuch 3 bekam einen frisch geladenen, unberührten OoS-Block: EURUSD H1 2025-01 bis
2026-07 (9.850 Stundenbars, Prüfsumme `08a6e4c9…`)** — Daten, die keine der ersten zwei
Strategien je gesehen hat.

### 2.1 Erster Versuch — Trendfolge (MA-Kreuzung 24/120)

| # | Bedingung (§7.2) | Verlangt | Gemessen | Erfüllt |
|---|---|---|---|---|
| 1 | OoS-Sharpe nach Kosten (Trade-Level, annualisiert) | ≥ 1,0 | **−0,79** | **Nein** |
| 2 | Deflated Sharpe über der Schwelle | > 0,95 | **0,026** | **Nein** |
| 3 | Trades im Auswertungszeitraum | ≥ 2.000 | **59** | **Nein** |
| 4 | ≥ 3 aufeinanderfolgende positive WF-Fenster (In-Sample) | ≥ 3 | **2** | **Nein** |
| 5 | Ertrag deckt die Kostenhürde (`net_over_hurdle > 0`) | > 0 | **−20,4 %** | **Nein** |
| 6 | Leckage-Test grün + Zufalls-Referenz negativ (beide gefahren) | beide | gefangen / **−218 %** | **Ja** |

**Fünf von sechs nicht erfüllt.** Die Strategie **verliert** nach realistischen Kosten (Netto
−18,85 %, Trade-Sharpe −0,79, Bar-Sharpe −0,68). Walk-Forward (In-Sample, netto je Fenster):
[+0,03 · +0,34 · −0,38 · −0,07 · −0,25] — zwei Fenster am Stück positiv, dann Verluste.

**Methodik-Härtung durch die §9-Review (vor der Abnahme):** die erste Fassung hatte drei reale
Schwächen — der OoS-Block überlappte den Walk-Forward (nicht „genau einmal"), das Deflated-
Sharpe-Tor war wegen Versuchszahl 1 wirkungslos, und zwei Bedingungen (Leckage/Zufall) waren
fest auf „wahr" verdrahtet statt gefahren. Alle behoben: Walk-Forward läuft **nur auf
In-Sample**, die Versuche gehen ins Register (Deflated Sharpe fiel von 0,26 auf **0,026**), und
Bedingung 6 wird real gefahren. Das Urteil ändert sich nicht.

### 2.2 Zweiter Versuch — Mittelwertrückkehr (z-Score 48, ein 2,0 / aus 0,5)

Eine von der Trendfolge **verschiedene** Hypothese: EURUSD kehrt intraday zum gleitenden Mittel
zurück; ein Kurs ≥ 2 Standardabweichungen daneben wird gegengehandelt, gehalten bis der z-Wert
wieder innerhalb 0,5 liegt.

| # | Bedingung (§7.2) | Verlangt | Gemessen | Erfüllt |
|---|---|---|---|---|
| 1 | OoS-Sharpe nach Kosten (Trade-Level, annualisiert) | ≥ 1,0 | **+0,185** | **Nein** |
| 2 | Deflated Sharpe über der Schwelle (12 Versuche) | > 0,95 | **0,066** | **Nein** |
| 3 | Trades im Auswertungszeitraum | ≥ 2.000 | **123** | **Nein** |
| 4 | ≥ 3 aufeinanderfolgende positive WF-Fenster (In-Sample) | ≥ 3 | **3** | **Ja¹** |
| 5 | Ertrag deckt die Kostenhürde (`net_over_hurdle > 0`) | > 0 | **+2,48 %** | **Ja** |
| 6 | Leckage-Test grün + Zufalls-Referenz negativ (beide gefahren) | beide | gefangen / **−218 %** | **Ja** |

**Drei von sechs erfüllt — mehr als die Trendfolge, aber die drei, die zählen (Sharpe,
Deflation, Trade-Zahl), scheitern mit großem Abstand. Ergebnis: KEIN EDGE.** Das Netto ist
diesmal **positiv** (+3,22 %) — und genau deshalb (§1.13: unerwartet gut = zuerst Bug-Verdacht)
habe ich es mit vier §9-Blickwinkeln und eigenen Gegenproben zerlegt:

- **Positiv, aber winzig und rausch-nah.** Trade-Sharpe +0,185, per-Trade-Sharpe ≈ 0,016,
  Deflated Sharpe **0,066** (6,6 % Wahrscheinlichkeit, echt zu sein, gegen 12 Versuche). Die
  **Minimum Track Record Length ist ≈ 79–97 Jahre** (§5) — mit 0,9 Jahren OoS ist das Ergebnis
  statistisch **nicht von null zu unterscheiden**.
- **0,74 der 3,22 Prozentpunkte sind Overnight-Swap-Carry, kein Alpha.** Die 2024 short-lastige
  Strategie kassiert positiven Short-EUR-Overnight-Swap (+1,51/Lot/Nacht laut Katalog, am
  optimistischen Rand). Auf einem swapfreien Konto entfiele er. Der carry-freie Handelsertrag ist
  **+2,48 %** — das ist genau `net_over_hurdle` = gross − Hürde, der den Carry bereits ausschließt
  (nicht zu verwechseln mit dem Netto +3,22 %, das den Carry enthält).
- **+3,22 % ist der selektierte Bessere aus zwei Hypothesen** auf demselben OoS-Block. Die
  kampagnenweite Deflation (N = 12) trägt diesen Selektionsbias statistisch; narrativ ist es
  **kein** eigenständiger Fund.
- **Bedingung 4 liegt im Zufallsbereich:** drei positive Fenster am Stück unter fünf haben unter
  einer fairen Münze **P ≈ 25 %** — kein ermutigendes Zeichen, sondern erwartbares Rauschen.
- **Füllzeitpunkt gegengeprüft, Einwand widerlegt.** Die §9-Review vermutete, die Zahl hänge an
  der optimistischen Füllung zur Signal-Kerze (wovon Mittelwertrückkehr am stärksten profitiert).
  Auf den **echten** OoS-Daten ändert eine Füllung eine Kerze später das Brutto **nicht**
  (+17,31 % → +17,94 %); die erste Kerze nach Einstieg trägt −4 % des Bruttos. Grund: die
  Hysterese hält die Rückkehr über viele Bars, sie hängt nicht am sofortigen Snap-back. Der
  Einwand gilt hier nicht (an einer synthetischen Reihe des Prüf-Agenten galt er, an unseren
  Daten nicht — deshalb wurde er gegengeprüft, nicht übernommen).

*¹ Erfüllt, aber im Zufallsbereich (P ≈ 25 %) — trägt keine Aussage.*

### 2.3 Dritter Versuch — Volatilitäts-Ausbruch (Donchian 48), **frisches** OoS 2025–26

Um den Selektionsbias zu heilen, bekam der dritte Versuch einen **neu geladenen, nie berührten**
OoS-Block (2025-01 bis 2026-07, 9.850 Stundenbars). Walk-Forward lief auf ganz 2022–2024,
der Abschlusstest genau einmal auf 2025–26.

| # | Bedingung (§7.2) | Verlangt | Gemessen | Erfüllt |
|---|---|---|---|---|
| 1 | OoS-Sharpe nach Kosten (Trade-Level, annualisiert) | ≥ 1,0 | **−1,005** | **Nein** |
| 2 | Deflated Sharpe über der Schwelle (18 Versuche) | > 0,95 | **0,0015** | **Nein** |
| 3 | Trades im Auswertungszeitraum | ≥ 2.000 | **101** | **Nein** |
| 4 | ≥ 3 aufeinanderfolgende positive WF-Fenster (In-Sample) | ≥ 3 | **0** | **Nein** |
| 5 | Ertrag deckt die Kostenhürde (`net_over_hurdle > 0`) | > 0 | **−59,1 %** | **Nein** |
| 6 | Leckage-Test grün + Zufalls-Referenz negativ (beide gefahren) | beide | gefangen / **−400 %** | **Ja** |

**Fünf von sechs nicht erfüllt — der klarste Verlust der drei.** Netto **−56,4 %**, Trade-Sharpe
−1,005; die fünf In-Sample-Fenster sind **allesamt negativ**. Der Verlust steckt schon im Brutto
(−35,9 % vor Kosten), ist also kein Kostenartefakt. Proportionale Gegenprobe (ein Verlust kann
keinen Edge vortäuschen, der Motor wurde in Versuch 2 von 22 Agenten geprüft): reproduzierbar
bitgleich, Kosten korrekt (Trade von Hand: net −1.064,48 = gross −1.030,00 − Kosten 34,48), und
die frischen Daten sind strukturell sauber (0 Duplikate, 0 nicht-monotone, 0 ungültige OHLC).
Das Qualitätstor meldet formal `passed=False`, aber nur wegen `expected_bar_count_unknown`
(fehlender Session-/Feiertagskalender, **S6**) — kein Integritätsdefekt.

**Wichtiger Quer-Check:** Breakout (Trendfortsetzung) verliert hart, während Mittelwertrückkehr
(Fade) knapp positiv war. Beide zeigen **dieselbe Richtung** — EURUSD H1 kehrt eher zum Mittel
zurück, als dass es ausbricht. Die drei Versuche widersprechen sich nicht, sie ergeben ein
kohärentes Bild.

**Fazit aller drei Versuche:** Trendfolge verliert (−18,85 %), Ausbruch verliert deutlich
(−56,4 %), Mittelwertrückkehr liegt knapp über Kosten (+2,48 % carry-frei), ist aber statistisch
nicht von null unterscheidbar und teils Zins statt Alpha. Die **Richtung** (Rückkehr schlägt
Trend) passt zur Literatur über Intraday-FX — der Effekt ist zu klein und zu unsicher, um
ausbeutbar zu sein. **Auf EURUSD existiert nach realistischen Kosten kein belegbarer Edge.**

**Damit greift das harte Abbruchkriterium (§7.3):** kein weiterer Ausbau, kein Ensemble, kein
Schwarm, keine LLM-Anbindung, kein Demo-Betrieb ohne bestandenen Test. Der Auftrag endet mit
diesem Bericht (Tor E5, §10).

---

## 3. Die Abnahme-Matrix (§10, ausgerechnet)

| # | Dimension | Gew. | Ist | Ziel | Erreicht | Begründung |
|---|---|---:|---:|---:|---:|---|
| 1 | Alpha-Substanz | 22 % | 0 | 7 | **1** | **drei** Edge-Tests gefahren (inkl. frischem OoS), **kein Edge** belegt |
| 2 | Validierungsdisziplin | 12 % | 7 | 10 | 8 | Vorregistrierung, OoS-Block, negativ gefahren, kampagnenweite Deflation (N = 12); Selektionsbias offengelegt (§7) |
| 3 | Risikoinfrastruktur | 10 % | 8 | 10 | 8 | A0.2-Tabelle da, vier Module aber unverdrahtet (S1) |
| 4 | Datenfundament | 12 % | 1 | 9 | 8 | Externe Quelle, Qualitätstor, Prüfsumme; Session-Härtung offen (S6) |
| 5 | Kostenmodell | 8 % | 1 | 9 | 9 | abgenommen, negativ gefahren, Handrechnung stimmt |
| 6 | Ausführungsqualität | 8 % | 2 | 6 | 6 | A/B-Book belegt, E3 vorgelegt |
| 7 | Kapitalbasis | 6 % | 3 | 6 | 3 | Philipps Entscheidung, nicht baubar |
| 8 | Regulatorische Passung | 5 % | 6 | 9 | 8 | E2 entschieden |
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

**Registrierte Versuche der Kampagne: 18** — je Strategie 5 Walk-Forward-Fenster + 1
OoS-Abschlusslauf, für drei Hypothesen (6 + 6 + 6). Jeder Lauf zählt (§6), auch die beiden
verlierenden. Die Deflation läuft gegen diese **kampagnenweite** Zahl (`count_scope="total"`),
nicht gegen die 6 der einzelnen Strategie — das ist die ehrliche Multiple-Testing-Zahl, wenn
mehrere Hypothesen selektiert werden. Wirkung, gemessen: der Deflated Sharpe der
Mittelwertrückkehr fällt mit wachsender Versuchszahl **0,127 (N = 6) → 0,066 (N = 12) → 0,045
(N = 18)** — jede weitere getestete Hypothese verschärft die Schwelle rückwirkend auch für die
positive. Der Breakout liegt bei **0,0015 (N = 18)**. Alle Werte weit unter 0,95. Zur
Einordnung: bei 100 Versuchen läge die allein durch Zufall erwartete Maximal-Sharpe grob bei 2,5
Standardeinheiten, bei 1.000 bei ≈ 3,3.

---

## 5. Minimum Track Record Length

Die Minimum Track Record Length sagt, wie lange eine Historie sein müsste, um mit 95 %
Konfidenz zu behaupten, der wahre Sharpe liege über null.

- **Trendfolge und Ausbruch:** Sharpe negativ (−0,68 bzw. −0,88) — die MinTRL ist nicht
  definiert; kein Track Record, egal wie lang, belegt einen Edge, weil keiner da ist.
- **Mittelwertrückkehr:** Sharpe positiv, aber winzig. Die Formel (Bailey/López de Prado) ist
  gegen die Referenzwerte des Auftrags kalibriert und reproduziert sie exakt (Sharpe 1,0 → 2,7
  Jahre, 0,5 → 10,8 Jahre). Für den Bar-Sharpe 0,167 ergibt sie eine **MinTRL von ≈ 97 Jahren**,
  für den Trade-Sharpe 0,185 ≈ **79 Jahre**. Wir haben **0,9 Jahre** Out-of-Sample — es fehlen
  rund zwei Größenordnungen an Historie, um dieses Ergebnis von null zu trennen.

Genau diese Zahlen sind der Grund, warum dieser Auftrag **keine** Live-Freigabe erzeugen konnte
und sollte.

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
- **Register-Disziplin (§6):** die Edge-Test-Läufe (Walk-Forward-Fenster + OoS beider
  Strategien) gehen sauber ins geteilte Kampagnen-Register (12 Versuche). Nicht lückenlos
  angehängt sind dagegen die Zufalls-Referenz- und Leckage-Kontrollläufe je Aufruf — sie sind
  Kontrollen, keine Hypothesen, aber die Regel „**jeder** Lauf zählt" habe ich damit nicht
  lückenlos umgesetzt. Ehrlich benannt statt kaschiert.
- **Zweiter Versuch, §9-Review-Funde (alle vor der Abnahme eingearbeitet oder benannt):**
  Der OoS-Block wurde **zweimal** angefasst (je Strategie einmal) — das positive +3,22 % ist der
  selektierte Bessere aus zwei Hypothesen (Selektionsbias); offengelegt in §2.2, statistisch
  durch die kampagnenweite Deflation (N = 12) getragen. Ein Review-Einwand (die Zahl hänge an
  der Füllung zur Signal-Kerze) war an einer synthetischen Reihe real, an den echten Daten
  jedoch nicht — **gegengeprüft und begründet verworfen**, nicht blind übernommen.
- **Latente Inkonsistenz (niedrig, hier folgenlos — inzwischen behoben):**
  `deflated_sharpe_for_report` deflationierte im Teil-3-Lauf die **Bar**-Sharpe (Beobachtungen =
  Bars), während Bedingung 1 bewusst die **Trade**-Sharpe prüft. Hier unschädlich (beide ~0,066),
  aber eine Inkonsistenz zwischen gemessener und deflationierter Kennzahl (Richtung der Verzerrung
  datenabhängig, nicht generell eine Überzeichnung); als S8 notiert und in **Abnahme-Paket 2**
  behoben (die Deflation nutzt jetzt die Trade-Sharpe je Trade, konsistent zum Tor). Die oben
  genannten DSR-Werte stammen aus dem Teil-3-Lauf mit der alten Methode; das Urteil (≪ 0,95) ist
  unberührt.
- **Dritter Versuch, Datenqualität ehrlich benannt:** der frische OoS-Block 2025–26 ist
  strukturell sauber (0 Duplikate/nicht-monotone/ungültige OHLC), das Qualitätstor meldet aber
  formal `passed=False`, weil es ohne Session-/Feiertagskalender die erwartete Barzahl nicht
  kennt (**S6**). Da Versuch 3 ein klarer Verlust ist, erzeugt diese Grenze kein Fehlurteil —
  aber sie ist benannt, nicht übergangen. Die §9-Review war hier proportional (Vier-Lens-
  Gegenprobe statt voller Agentenschwarm): ein Verlust kann keinen Edge vortäuschen, und der
  Motor war in Versuch 2 bereits von 22 Agenten geprüft.

---

## 7. Die schwächste Behauptung dieses Berichts — benannt und nachgeprüft

Am schwächsten belegt ist die Aussage des zweiten Versuchs: **„der Handelsertrag deckt die
Kostenhürde (+2,48 %) / das Signal ist positiv (+3,22 %)."** Nachgeprüft und auf drei Wegen
entkräftet: (a) **Selektionsbias** — +3,22 % ist das Maximum aus zwei Hypothesen auf demselben
OoS-Block; (b) **Zins statt Alpha** — 0,74 der 3,22 Prozentpunkte sind Overnight-Carry, auf
einem swapfreien Konto nicht vorhanden; (c) **statistisch null** — Deflated Sharpe 0,066, MinTRL
≈ 79–97 Jahre, per-Trade-Sharpe ≈ 0,016. Ein vierter Einwand der Review (die Zahl hänge an der
optimistischen Füllung zur Signal-Kerze) wurde an den echten Daten geprüft und **verworfen** —
das Brutto bleibt bei Füllung eine Kerze später praktisch gleich (+17,31 % → +17,94 %). Das
Gesamturteil KEIN EDGE hängt an keiner dieser Feinheiten: die Bedingungen 1–3 (Sharpe ≥ 1,0,
Deflation > 0,95, ≥ 2.000 Trades) scheitern mit großem Abstand und sind durch keine der obigen
Korrekturen erreichbar.

---

## 8. Was gemeldet, aber nicht angefasst wurde (`SPAETER.md`)

- **S1** — vier Risikomodule (Verlustgrenzen, Sizing, Stop-Budget, Bewertungstor) sind nicht
  im Order-Pfad verdrahtet.
- **S2** — kein Frische-Latch am Global-Halt (Befund 1 offen).
- **S4** — entfallen (am 2026-08-19 ersatzlos aus dem Stand entfernt).
- **S6** — Qualitätstor-/FX-Session-Härtung (NY-17:00-Anker, Feiertagskalender).
- **S7** — Walk-Forward-Trainingsschritt (damit Purge/Embargo greifen) + volle
  Kriterien-Auswertung.
- **S8** — Deflation konsistent auf die Trade-Level-Sharpe (Beobachtungen = Trades) statt auf
  die Bar-Sharpe umstellen; hier folgenlos (beide 0,066), bei größerem Signal relevant.

---

## 9. Fazit

Das Kostbarste an diesem Auftrag ist nicht der Code, sondern **eine Zahl, der man trauen kann.**
Drei ernsthafte, vorab festgeschriebene Hypothesen liefen durch dasselbe harte Tor: Trendfolge
**verliert** (−18,85 %), Volatilitäts-Ausbruch **verliert deutlich** (−56,4 % auf frischem OoS),
Mittelwertrückkehr liegt **knapp über Kosten** (+2,48 % carry-frei), ist aber statistisch nicht
von null zu unterscheiden (MinTRL ≈ 79–97 Jahre) und teils Zins statt Alpha. Alle drei zeigen
dieselbe Richtung — **Rückkehr schlägt Trend**, passend zur Literatur über Intraday-FX —, doch
der Effekt ist zu klein und zu unsicher, um ausbeutbar zu sein. **Auf EURUSD existiert nach
realistischen Kosten kein belegbarer Edge.**

Das billig und früh zu wissen — nach Tagen statt nach Monaten verbrannten Kapitals — ist der
Wert des Auftrags. Der Sicherheits-, Kosten-, Daten- und Prüfapparat steht geprüft bereit;
sollte je eine Strategie einen echten Edge zeigen, kann sie gefahrlos darauf iterieren. Diese
drei tun es nicht.

---

## 10. Entscheidungstor E5 — an Philipp

Der Masterprompt verlangt E5 in **jedem** Fall nach dem Edge-Test. Dreimal lautete Philipps
E5-Entscheid „weiterbauen": aus dem ersten Nein (Trendfolge) wurde Versuch 2 (Mittelwertrückkehr,
auf demselben OoS), aus dessen Nein Versuch 3 (Volatilitäts-Ausbruch, auf **frischem** OoS
2025–26) — alle drei ohne Edge, mit wachsender Multiple-Testing-Last (N = 18).

**Ausgang: Philipp hat entschieden — beenden.** Nach drei distinkten, kohärenten No-Edge-
Ergebnissen ist die eine Frage so belastbar beantwortet, wie dieser Datensatz es zulässt.
Weitere Hypothesen auf demselben Instrument zu testen wäre Data-Mining, das die Deflation
bereits sichtbar bestraft (der Mittelwertrückkehr-DSR fiel allein durch die dritte Hypothese
von 0,066 auf 0,045). **TEIL 3 ist damit abgeschlossen.** Paket 5 (Ausbau, LLM, Demo-Betrieb)
bleibt gesperrt — es gibt keinen bestandenen Test, auf dem es aufsetzen könnte (§7.3, §8). Der
geprüfte Sicherheits-, Kosten-, Daten- und Backtest-Apparat bleibt bestehen und ist für einen
künftigen, ehrlich registrierten Versuch bereit. Der Overnight-Swap-Carry im zweiten Versuch
bleibt als Sachbefund stehen: 0,74 der 3,22 Prozentpunkte kamen aus der Finanzierung, nicht aus
dem Signal.

---

## 11. Paket 5 — auf ausdrückliche Anweisung, unter Vorbehalt (Nachtrag)

**Vorab und ehrlich:** Nach dem Abschluss unter §10 („beenden") hat Philipp sich **ausdrücklich
umentschieden** und angewiesen, **Paket 5 dennoch zu bauen**. Das ist ein bewusstes
**Übersteuern** des harten Tors §7.3/§8 („Paket 5 nur bei bestandenem Edge-Test") — auf seine
ausdrückliche Anweisung, hier klar als solche gekennzeichnet (Kernregel 6: eigene bzw. fremde
Entscheidungen benennen). Die harten Sicherheitsregeln bleiben **unberührt**: kein Echtgeld,
`allow_write` auf dem Live-Pfad geschlossen, ESMA-Hebel (konservativ 5:1), kein LLM im
Entscheidungspfad ohne Beleg.

Gebaut wurde die **Infrastruktur**, die §8 beschreibt — und ihre eigenen Tore bestätigen die
Integrität, indem sie (korrekt) **nichts** durchlassen, solange kein Edge existiert:

- **§8.1 Multi-Instrument** (`tools/multi_instrument_edge.py`): prüft die beste Strategie
  (Mittelwertrückkehr) einzeln je Instrument gegen dasselbe Sechs-Bedingungen-Tor, Hebel
  konservativ 5:1. Ergebnis auf EURUSD + GBPUSD: **0 von 2 Instrumenten mit Edge** (EURUSD
  +3,22 %, GBPUSD +7,18 % — beide wieder knapp positiv, dieselbe Mittelwertrückkehr-Tendenz,
  aber beide verfehlen dieselben drei Bedingungen: Sharpe, Deflation, Trade-Zahl; GBPUSD-Daten
  mit einer Vendor-Lücke im Dez 2022, im In-Sample) → kein Ausbau (§8.1: „ein Instrument, das
  durchfällt, kommt nicht mit").
- **§8.2–8.4 LLM-Tor** (`backtest/llm_compare.py`): fail-closed. Ein LLM kommt nur in den
  Entscheidungspfad, wenn die LLM-Variante die Nicht-LLM-Variante gegen dieselben sechs
  Bedingungen **schlägt**, nur auf Daten **nach** dem Trainingsstichtag (Leckage), mit
  protokollierter Modellversion (Drift). Das Modul ruft **kein** LLM und trifft keine
  Entscheidung — es ist nur das Tor davor (Kernregel 17). Ohne bestandene Baseline bleibt es zu.
- **§8.5 Demo-Betrieb** (`venue/demo_run.py`): fail-closed. Eine Strategie kommt nur in den
  ≥ 6-monatigen Demo-Betrieb, wenn sie den Edge-Test **bestanden** hat. Gegen das echte
  Mittelwertrückkehr-Urteil (bester der drei, `passed=False`) verweigert das Tor die
  Registrierung — nachgewiesen. Echtgeld bleibt hinter der unberührten vierteiligen
  Live-Freigabe.

**Eigener Fehler, von der §9-Gegenprobe gefunden und behoben:** im ersten Wurf des
Multi-Instrument-Harness war Bedingung 6 (Leckage/Zufall) fest auf „wahr" verdrahtet — **exakt
die Schwäche, die ich in Paket 4b kritisiert und dort behoben hatte**, hier wiederholt. Jetzt
wird sie je Instrument wirklich gefahren (Zufalls-Referenz < 0, Leckage-Schutz fängt eine
Zukunfts-Strategie). Das Ergebnis (0 von 2) ändert sich dadurch nicht — beide Instrumente
scheitern ohnehin an den Bedingungen 1–3 —, aber die Zahl steht jetzt auf ehrlicher Messung.

**Fazit Paket 5:** Die Infrastruktur steht, geprüft und negativ gefahren (jedes Tor absichtlich
gebrochen → rot → zurückgenommen). Aber sie lässt — ihrer eigenen Integrität folgend — **kein
aktuelles Vorhaben durch**, weil kein Edge existiert. Paket 5 ist damit gebaut, aber **leer**:
es wartet auf eine Strategie, die das Tor aus §2 zuerst besteht. Das ist die ehrlichste Form, in
der dieses Paket unter der gegebenen Faktenlage existieren kann — es widerspricht dem Urteil
„kein Edge" nicht, es macht es baubar sichtbar.

---

## 12. Entfallen

Dieser Abschnitt beschrieb einen Finanzierungs- und Screening-Pfad, den es seit dem
2026-08-19 nicht mehr gibt: er wurde auf Anweisung des Auftraggebers ersatzlos aus dem
Stand entfernt (`costs/halal.py`, `venue/halal.py`, das Live-Tor `_enforce_halal`, der
Runner-Schritt und die zugehörigen Tests). Die Nummer bleibt besetzt, damit die Verweise
in §1 und §10 nicht verrutschen.

Der eine Messwert daraus, der zur Sache gehört und darum in §4 stehen bleibt: von den
+3,22 % Netto des zweiten Versuchs waren **160,06 USD** empfangener Overnight-Carry und
damit 0,74 Prozentpunkte Finanzierung statt Signal. Am Sechs-Bedingungen-Tor änderte das
nichts — mit wie ohne Carry lautete das Urteil **KEIN EDGE**.

Was entfernt wurde und was der Wegfall am Orderpfad ändert: `AUFTRAG/geloescht.md`.

