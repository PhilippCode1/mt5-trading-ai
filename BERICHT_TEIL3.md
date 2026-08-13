# BERICHT TEIL 3 — Vom Sicherheitsrahmen zum belegten Edge

*Der Abschlussbericht des Edge-Nachweis-Auftrags. Jede Zahl ist gemessen. Die eine Frage
war: existiert auf EURUSD nach realistischen Kosten ein Edge? Getestet wurden nacheinander
**zwei** vorab festgeschriebene Hypothesen (Trendfolge, dann — nach E5 = weiterbauen —
Mittelwertrückkehr). **Die Antwort ist Nein** — und ein sauber belegtes Nein ist der
auftragsgemäße Ausgang, kein Scheitern.*

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
- **Paket 4 — Edge-Test:** zwei einfachste ernsthafte Signallogiken (**nicht** optimiert) auf
  **EURUSD-Stundenbars** (18.715 Bars, 2022–2024, Dukascopy; Prüfsumme `8cdebf05…`) gegen das
  harte Sechs-Bedingungen-Tor: Trendfolge (MA-Kreuzung 24/120) und, nach Philipps E5-Entscheid
  „weiterbauen", Mittelwertrückkehr (z-Score 48, ein 2,0 / aus 0,5).

---

## 2. Die Antwort auf die Edge-Frage — zwei Hypothesen durch dasselbe Tor

Getestet wurden **zwei** vorab festgeschriebene, nicht optimierte Hypothesen auf demselben
Instrument (EURUSD H1). Nach dem ersten Nein legte ich E5 vor; Philipps Entscheidung war
**weiterbauen mit einer anderen Hypothese**. Beide Läufe zählen ins selbe Register (12
Versuche). Der Out-of-Sample-Block (letzte 30 %, ab 2024-02-07, 5.615 Stundenbars) wurde **je
Strategie einmal** angefasst — insgesamt also zweimal; das ist ein Selektionsbias (§7).

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
- **0,74 der 3,22 Prozentpunkte sind riba-Carry, kein Alpha.** Die 2024 short-lastige Strategie
  kassiert positiven Short-EUR-Overnight-Swap (+1,51/Lot/Nacht laut Katalog, am optimistischen
  Rand). Auf einem swapfreien Halal-Konto (S4) entfiele er. Der carry-freie Handelsertrag ist
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

**Fazit beider Versuche:** Trendfolge verliert deutlich; Mittelwertrückkehr liegt knapp über
Kosten, ist aber statistisch nicht von null unterscheidbar und teils Zins statt Alpha. Die
**Richtung** (Rückkehr schlägt Trend) passt zur Literatur über Intraday-FX — der Effekt ist
aber zu klein und zu unsicher, um ausbeutbar zu sein. **Auf EURUSD existiert nach realistischen
Kosten kein belegbarer Edge.**

**Damit greift das harte Abbruchkriterium (§7.3):** kein weiterer Ausbau, kein Ensemble, kein
Schwarm, keine LLM-Anbindung, kein Demo-Betrieb ohne bestandenen Test. Der Auftrag endet mit
diesem Bericht (Tor E5, §10).

---

## 3. Die Abnahme-Matrix (§10, ausgerechnet)

| # | Dimension | Gew. | Ist | Ziel | Erreicht | Begründung |
|---|---|---:|---:|---:|---:|---|
| 1 | Alpha-Substanz | 22 % | 0 | 7 | **1** | **zwei** Edge-Tests gefahren, **kein Edge** belegt |
| 2 | Validierungsdisziplin | 12 % | 7 | 10 | 8 | Vorregistrierung, OoS-Block, negativ gefahren, kampagnenweite Deflation (N = 12); Selektionsbias offengelegt (§7) |
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

**Registrierte Versuche der Kampagne: 12** — je Strategie 5 Walk-Forward-Fenster + 1
OoS-Abschlusslauf, für beide Hypothesen (6 + 6). Jeder Lauf zählt (§6), auch die verlierende
Trendfolge. Die Deflation des positiven Mittelwertrückkehr-Ergebnisses läuft gegen diese
**kampagnenweite** Zahl (`count_scope="total"`), nicht gegen die 6 der einen Strategie — das ist
die ehrliche Multiple-Testing-Zahl, wenn zwei Hypothesen gegen denselben OoS-Block selektiert
werden. Wirkung, gemessen: der Deflated Sharpe der Mittelwertrückkehr fällt von **0,127** (bei
N = 6) auf **0,066** (bei N = 12) — die kampagnenweite Zählung halbiert ihn nahezu. Beide Werte
liegen weit unter der Schwelle 0,95. Zur Einordnung: bei 100 Versuchen läge die allein durch
Zufall erwartete Maximal-Sharpe grob bei 2,5 Standardeinheiten, bei 1.000 bei ≈ 3,3.

---

## 5. Minimum Track Record Length

Die Minimum Track Record Length sagt, wie lange eine Historie sein müsste, um mit 95 %
Konfidenz zu behaupten, der wahre Sharpe liege über null.

- **Trendfolge:** Sharpe negativ (−0,68) — die MinTRL ist nicht definiert; kein Track Record,
  egal wie lang, belegt einen Edge, weil keiner da ist.
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
- **Latente Inkonsistenz (niedrig, hier folgenlos):** `deflated_sharpe_for_report`
  deflationiert die **Bar**-Sharpe (Beobachtungen = Bars), während Bedingung 1 bewusst die
  **Trade**-Sharpe prüft. Hier unschädlich (beide ergeben 0,066), bei größerem Signal aber eine
  Überzeichnung — als Grenze in `SPAETER.md` (S8) notiert, nicht stillschweigend gelassen.

---

## 7. Die schwächste Behauptung dieses Berichts — benannt und nachgeprüft

Am schwächsten belegt ist die Aussage des zweiten Versuchs: **„der Handelsertrag deckt die
Kostenhürde (+2,48 %) / das Signal ist positiv (+3,22 %)."** Nachgeprüft und auf drei Wegen
entkräftet: (a) **Selektionsbias** — +3,22 % ist das Maximum aus zwei Hypothesen auf demselben
OoS-Block; (b) **Zins statt Alpha** — 0,74 der 3,22 Prozentpunkte sind Overnight-Carry, auf
einem Halal-Konto nicht vorhanden; (c) **statistisch null** — Deflated Sharpe 0,066, MinTRL
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
- **S4** — **Halal:** gehebelte CFDs gelten mehrheitlich als *haram* — braucht Philipps
  Entscheidung + Fatwa (Kernregel 16).
- **S6** — Qualitätstor-/FX-Session-Härtung (NY-17:00-Anker, Feiertagskalender).
- **S7** — Walk-Forward-Trainingsschritt (damit Purge/Embargo greifen) + volle
  Kriterien-Auswertung.
- **S8** — Deflation konsistent auf die Trade-Level-Sharpe (Beobachtungen = Trades) statt auf
  die Bar-Sharpe umstellen; hier folgenlos (beide 0,066), bei größerem Signal relevant.

---

## 9. Fazit

Das Kostbarste an diesem Auftrag ist nicht der Code, sondern **eine Zahl, der man trauen kann.**
Zwei ernsthafte, vorab festgeschriebene Hypothesen liefen durch dasselbe harte Tor: Trendfolge
**verliert** (−18,85 %, Trade-Sharpe −0,79); Mittelwertrückkehr liegt **knapp über Kosten**
(+2,48 % carry-frei), ist aber statistisch nicht von null zu unterscheiden (MinTRL ≈ 79–97
Jahre) und teils Zins statt Alpha. Die Richtung — Rückkehr schlägt Trend — passt zur Literatur
über Intraday-FX, der Effekt ist aber zu klein und zu unsicher, um ausbeutbar zu sein. **Auf
EURUSD existiert nach realistischen Kosten kein belegbarer Edge.**

Das billig und früh zu wissen — nach Tagen statt nach Monaten verbrannten Kapitals — ist der
Wert des Auftrags. Der Sicherheits-, Kosten-, Daten- und Prüfapparat steht geprüft bereit;
sollte je eine Strategie einen echten Edge zeigen, kann sie gefahrlos darauf iterieren. Diese
beiden tun es nicht.

---

## 10. Entscheidungstor E5 — an Philipp

Der Masterprompt verlangt E5 in **jedem** Fall nach dem Edge-Test. Nach dem ersten Nein
(Trendfolge) lautete Philipps E5-Entscheid „weiterbauen" — daraus wurde der zweite Versuch
(Mittelwertrückkehr), ebenfalls ohne Edge. E5 liegt damit erneut vor: eine **dritte**,
vorab festzuschreibende Hypothese testen (dann mit **frisch abzutrennendem** OoS-Block, weil der
bisherige durch zwei Strategien belastet ist) — oder den Auftrag **beenden**, weil die eine
Frage sauber beantwortet ist. Paket 5 (Ausbau, LLM, Demo-Betrieb) bleibt gesperrt, solange kein
Test alle sechs Bedingungen besteht (§7.3, §8).
