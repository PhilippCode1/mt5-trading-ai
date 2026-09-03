# Kostentor (A1) — trägt die Betriebsauslegung nach echten Kosten?

*In sich geschlossen. Jede Zahl mit Bezugsgröße. Rohausgabe des Laufs:
[`07-AUSGABEN/kostentor.txt`](07-AUSGABEN/kostentor.txt), Rohausgabe der Messung:
[`07-AUSGABEN/atr_messung.txt`](07-AUSGABEN/atr_messung.txt).*

---

## Das Ergebnis in vier Sätzen

1. **M1 = GRÜN.** Die erforderliche Trefferquote p\* bei CRV 1:1 und einem Stop von
   1,0 × Median-ATR(14) auf H1 liegt bei **4 von 6** Prüfinstrumenten unter 56 %; gefordert
   sind mindestens 3. *Bestätigt durch Ausführung.*
2. **M2 = ROT.** Bei der geplanten Auslegung (4 Round-Turns je Handelstag, 250 Tage,
   Hebel 5) reißen **13 von 18** rechenbaren Kostenzeilen die 50-%-Grenze. Nach M2 ist damit
   die **Betriebsauslegung** zu ändern, nicht der Maßstab. *Bestätigt durch Ausführung.*
3. **Das grüne Urteil hat keine Reserve** und wird von Gold, dem DAX und der Einzelaktie
   getragen — nicht von den Währungspaaren, um die die Auslegung gebaut ist.
4. **BTCUSD ist nicht bewertbar.** Der erreichbare MT5-Handelsplatz führt keinen
   Krypto-CFD. Es steht „nicht gemessen" da, keine Schätzung.

---

## A1.1 — Die Kosten: was erhoben wurde

**Vier EU-regulierte Broker mit MT5-Zugang** (gefordert: mindestens drei), je Broker eine
Erhebung auf den Kontraktspezifikations-Seiten und eine **davon unabhängige Gegenprüfung**,
die dieselben URLs erneut abgerufen hat.

| Broker | Aufsicht | Kontotyp | Gegenprüfung: bestätigt / abweichend / unbelegt |
|---|---|---|---|
| IC Markets (EU) Ltd | CySEC 362/18 | Raw Spread MT5 | **47 / 0 / 1** von 48 Feldern |
| Admirals Europe Ltd | CySEC 201/13 | Trade.MT5 | **53 / 0 / 8** von 61 Feldern |
| Tickmill Europe Ltd | CySEC 278/15 | Raw/Pro MT5 | **29 / 0 / 15** von 44 Feldern |
| Pepperstone EU Limited | CySEC 388/20 | Razor MT5 | Spreads aus der veröffentlichten Durchschnittstabelle (Zeitraum 01.–30.04.2026) |

**Über alle vier Broker: 0 abweichende Werte.** Kein einziger erhobener Wert stand im
Widerspruch zu dem, was der Gegenprüfer auf der Seite selbst gesehen hat. Die unbelegten
Felder stehen je Zeile in `config/broker_costs.json` unter `verification`; sie betreffen
überwiegend Swap-Sätze, die clientseitig nachgeladen werden, und abgeleitete Tick-Größen.

Ablage: **`config/broker_costs.json`**, versioniert und fail-closed nach dem Muster von
`config/instrument_catalog.json` (Lader: `mt5_trading_ai/costs/broker_costs.py`,
33 Tests in `tests/test_broker_costs.py`). Jede Zeile trägt Quell-URL, Abrufdatum
(2026-08-17) und ein wörtliches Zitat der Fundstelle.

### Die Einheitenfalle — und warum sie hier geschlossen ist

Broker veröffentlichen Spreads in Pips, Punkten, Indexpunkten oder nackten Zahlen ohne
jede Einheit. Wer sie ungeprüft in eine Rechnung schiebt, verrechnet sich um Faktor 10, 100
oder 10 000 — und merkt es nicht, weil das Ergebnis weiter wie eine Zahl aussieht. Jede
Spreadangabe steht deshalb dreiteilig:

| Feld | Bedeutung | Beispiel IC Markets / EURUSD |
|---|---|---|
| `spread_published` | die Zahl, wie sie auf der Quelle steht | `0.06` |
| `spread_unit` | die Einheit, wie sie auf der Quelle steht | `"Pips"` |
| `unit_in_price` | wie viel **eine** solche Einheit in Preiseinheiten ist | `0.0001` |

Der wirksame Spread ist damit ein **gerechneter**, kein abgetippter Wert. Der Test
`test_spreads_der_echten_datei_liegen_in_plausibler_groessenordnung` prüft zusätzlich alle
Zeilen gegen das Band 0,01–50 Basispunkte — genau dort fällt ein Faktor-Fehler auf, nicht
erst im Ergebnis.

### Wo nur ein „ab"-Wert vorlag

Bei **keinem** der vier Broker musste auf einen reinen Werbewert zurückgegriffen werden:
alle vier veröffentlichen Durchschnitts- oder Typisch-Spreads. Der Lader würde einen
Werbewert (`spread_kind = "ab-wert"`) ohne bezifferten Aufschlag (`spread_markup_factor` > 1)
ablehnen — ein stiller Aufschlag wäre im Ergebnis nicht mehr zu erkennen.

**Eine Ausnahme, die als solche gekennzeichnet ist:** IC Markets nennt für Aktien-CFDs
allgemein „commissions start from 0.1% per share, per trade". Das ist ein „ab"-Satz; er
ist als **Untergrenze** in die Rechnung eingegangen (20 bp Round-Turn), nicht als typischer
Wert. Siehe „Eigene Entscheidung 3" unten.

### Zwei Zeilen ohne Zahlen — und warum das ein Ergebnis ist

| Zeile | Zustand | Grund |
|---|---|---|
| Tickmill EU / NVDA | `spread_nicht_veroeffentlicht` | Der Broker führt den Aktien-CFD („NVDA.NAS", „No Commissions."), veröffentlicht für Aktien-CFDs aber keine Spreadtabelle. Ohne Spread **und** ohne Kommission wäre die Kostenzeile Null — und Null wäre falsch, denn die Kosten stecken laut Broker vollständig im Spread |
| Pepperstone EU / NVDA | `spread_nicht_veroeffentlicht` | Veröffentlicht die Kommission (0,02 USD je Aktie je Seite), aber keine Spreadtabelle: „Share CFD trades are charged a commission in addition with any spread which differs by underlying exchange." Nur die Kommission ergäbe rund 2 bp und unterschätzte die realen Kosten |

Beide fallen **begründet** aus der Rechnung. Der Lader kennt dafür einen eigenen Zustand —
weder „bietet es nicht an" noch „kostet nichts", beides wäre falsch.

---

## A1.2 — Die Volatilität: was gemessen wurde

**ATR(14) auf H1 über 12 Monate**, gelesen über den bestehenden lesenden Pfad
(`RealMt5Terminal` mit `allow_write=False`) gegen ein **Demokonto**. Werkzeug:
`tools/atr_messung.py`, Ablage `config/atr_measurements.json` (fail-closed, Lader
`mt5_trading_ai/costs/volatility.py`, **39 Tests**).

| Instrument | Kerzen | ATR-Median (bp) | ATR 25. Perzentil (bp) | Median-Preis | Lücken |
|---|---:|---:|---:|---:|---:|
| EURUSD | 6.183 | 10,04 | 8,64 | 1,16393 | 54 |
| GBPJPY | 6.182 | 11,72 | 9,76 | 211,3765 | 54 |
| XAUUSD | 5.790 | 41,80 | 33,70 | 4.323,455 | 136 |
| DE40 | 5.142 | 26,81 | 21,09 | 24.370,20 | 219 |
| US500 | 5.463 | 21,24 | 16,38 | 6.891,00 | 58 |
| NVDA | 1.990 | 91,18 | 77,38 | 188,225 | 249 |
| **BTCUSD** | **0** | **nicht gemessen** | — | — | — |

Fenster: 2025-08-16 bis 2026-08-16. **Gemessen: 6 von 7 Symbolen.**

### BTCUSD — laut gescheitert, nicht still gefüllt

Der erreichbare MT5-Handelsplatz (MetaQuotes-Demo, 12.525 Symbole) führt **keinen
Krypto-CFD**. Die Symbolpfade sind: `Nasdaq` (12.363), `Forex` (126), `Indexes` (26),
`Metals` (10) — kein Kryptosegment. Symbole wie `BTC` oder `IBIT` sind
Bitcoin-**ETFs** an der Nasdaq, keine Krypto-CFDs; ihr Kursverlauf ist der eines
Fondsanteils mit Nasdaq-Handelszeiten und nicht der eines 24/7-Krypto-CFDs.

Nach der Regel aus A1.2 steht deshalb **„nicht gemessen"** in der Datei, mit Grund, und
BTCUSD fällt aus der Rechnung. Die **Kosten** für BTCUSD sind trotzdem erhoben (alle vier
Broker führen den CFD) und stehen in `config/broker_costs.json` — sie lassen sich nur ohne
gemessene Volatilität nicht in ein p\* überführen.

*Folge für die Ampel, ausdrücklich:* Solange ein Instrument nicht bewertbar ist, kann **ROT**
nach dem Wortlaut von M1 gar nicht eintreten, denn ROT verlangt „bei allen sechs
Instrumenten". Die Ampel ist in dieser Richtung fail-open, was der Kernregel „nicht
bewertbar = nicht erfüllt" widerspricht. BTCUSD zählt hier darum als **nicht grün**; ein
rotes Urteil wird mit dieser Datenlage nicht behauptet.

### Eigene Entscheidung 1 — Lücken-Bereinigung des ATR

*(Entscheidung des ausführenden Agenten, mit Begründung.)*

Zwischen zwei H1-Kerzen liegt nicht immer eine Stunde: Wochenenden, Feiertage und
Börsenpausen erzeugen Sprünge. Der Kurssprung über eine solche Pause geht in
`|H − C_vorher|` ein und bläht die True Range auf. **Ein zu großer ATR lässt das Kostentor
besser aussehen, als es ist** (großer Stopabstand → kleineres p\*). Deshalb wird die
Verkettung zum Vorgänger gelöst, wenn der Abstand zwei Stunden überschreitet; dann gilt
`TR = H − L`.

Die unbereinigte Reihe steht zum Vergleich in derselben Datei. Wirkung, gemessen:

| Instrument | ATR bereinigt | ATR unbereinigt | Differenz |
|---|---:|---:|---:|
| EURUSD | 0,00117 | 0,00118 | −0,4 % |
| XAUUSD | 18,653 | 18,741 | −0,5 % |
| DE40 | 65,711 | 66,000 | −0,4 % |
| **NVDA** | **1,7212** | **1,8442** | **−6,7 %** |

Bei NVDA folgt jede achte Kerze auf eine Übernachtpause; dort ist die Bereinigung
entscheidend. Die Richtung ist durchgehend konservativ.

**Gegengerechnet:** die Reihe wurde unabhängig mit `numpy` nachgerechnet (True Range,
Wilder-Glättung, Perzentile) und stimmt auf fünf Nachkommastellen überein.

### Was die Messung ausdrücklich nicht ist

Der ATR stammt vom **Demo-Feed des MetaQuotes-Handelsplatzes**, die Kosten von vier
**anderen** Brokern. Das ist zulässig, weil Volatilität eine Markteigenschaft ist und
zwischen Anbietern nahezu gleich — Kosten sind es nicht und stehen deshalb getrennt. Der
Vermerk steht in `config/atr_measurements.json` unter `terminal.note`.

---

## A1.3 — Die Rechnung

Kein neues Kostenmodell. `tools/kostentor.py` füttert die vorhandenen Funktionen aus
`mt5_trading_ai/risk/stop_budget.py` — `cost_floor_bps`, `margin_ceiling_bps`,
`breakeven_hit_rate` — mit den Zahlen aus A1.1 und A1.2.

```
K  = Spread + Kommission + Slippage-Annahme        (Round-Turn-Kosten)
p* = 0,5 + K / (2 x S)                             S = Stopabstand
k  = K / P                                         Kostenanteil am Nominal
L  = N x H x k                                     Jahreskostenlast
```

Gerechnet wird durchgehend in **Basispunkten des Nominals** — der einzige Weg, sechs
Instrumente in vier Notierungen (USD, JPY, EUR, USD je Aktie) zu vergleichen, ohne bei
jedem Schritt eine Währung mitzuschleppen. `p*` bleibt davon unberührt: es ist ein
Verhältnis zweier Größen derselben Einheit. Die Umrechnung von Kommissionen zwischen
Währungen benutzt **gemessene** Kurse aus demselben Messlauf (EURUSD 1,15704,
GBPUSD 1,35340, USDJPY 159,317); ein fehlender Kurs ist ein Fehler, keine Näherung.

### Die Slippage-Annahme — beziffert und begründet

| Instrumentengruppe | Annahme je Round-Turn |
|---|---|
| Haupt-Währungspaar, Gold, Hauptindex | **0,5 bp** |
| Nebenpaar, Einzelaktie | **1,0 bp** |
| Krypto | **2,0 bp** |

**Herleitung:** eine Marktorder in Mindestgröße läuft bei diesen Instrumenten typischerweise
innerhalb des ersten Buchlevels; der Ausführungsnachteil liegt damit in der Größenordnung
eines halben bis ganzen Spreads, und die erhobenen Spreads liegen bei 0,05–2 bp
(FX/Index/Gold) beziehungsweise 1–20 bp (Aktie/Krypto).

**Die Annahme ist bewusst am unteren Rand gewählt** — damit das Kostentor nicht durch eine
großzügige Annahme künstlich rot wird. Fällt das Urteil trotzdem rot aus, liegt es nicht an
dieser Zahl. Ein Aufschlag für Nachrichtenlagen ist **nicht** enthalten; Stress-Spreads
veröffentlicht kein Broker.

**Sie ist der einzige ungemessene Posten in K** und bei den günstigen Instrumenten der
größte: bei XAUUSD macht sie 59 % von K aus. Deshalb ist sie Abbruchbedingung 3 in
`ABBRUCH.md`: eine Abweichung von mehr als 50 % im Demobetrieb löst einen Halt aus.

### Eigene Entscheidung 2 — Kommission je Lot oder je Prozent

*(Entscheidung des ausführenden Agenten.)*

Bei Aktien-CFDs veröffentlichen die Broker die Kommission als **Prozentsatz** oder als
**Betrag je Aktie**. Zwischen beiden Lesarten liegt eine Größenordnung. Die Kostendatei
kennt deshalb ein optionales Feld `commission_bps_round_turn`; ist es gesetzt, schlägt es
den Betrag je Lot, weil ein Prozentsatz mit der Position skaliert und ein fester Betrag
nicht.

### Eigene Entscheidung 3 — IC Markets / NVIDIA: Regelsatz statt Mindestgebühr

*(Entscheidung des ausführenden Agenten. Sie kippt eine Zeile von grün auf rot.)*

Die erste Fassung rechnete mit der belegten **Mindestgebühr** (0,02 USD je Aktie je Seite =
2,1 bp Round-Turn) — dem günstigsten denkbaren Satz. Eine adversarische Gegenprüfung
(vier unabhängige Prüfer, Auftrag: das grüne Urteil zu widerlegen) hat das als zu
freundlich zurückgewiesen, mit drei Argumenten:

1. IC Markets nennt auf derselben Seite den Regelsatz „ab 0,1 % je Aktie je Trade" =
   10 bp je Seite = **20 bp Round-Turn**.
2. Das eigene Kostenmodell dieses Repos nimmt für Aktien genau diesen Wert an:
   `ASSUMED_ROUND_TURN_COST_BPS["equity"] = 20`.
3. Tickmill und Pepperstone wurden wegen einer vergleichbaren Lücke als **nicht rechenbar**
   verworfen; fail-closed hätte IC Markets ebenso treffen müssen.

**Übernommen: 20 bp.** Wirkung: IC Markets / NVDA fällt von p\* = 52,9 % (grün) auf
**62,7 % (rot)**. Admirals bleibt bei 52,3 % grün, weil Admirals tatsächlich 0,02 USD je
Aktie je Seite berechnet — das ist bei diesem Anbieter der Regelsatz, nicht eine
Mindestgebühr. Die Bezugsgröße dafür steht in der Datei: **100 Aktien je Position**;
darunter bindet Admirals' Mindestkommission von 1 USD je Transaktion, und die Kosten
liegen höher.

---

## A1.4 — Das Urteil

### Gegen M1

| Instrument | bestes p\* | Broker | Ampel | ESMA-Deckel |
|---|---:|---|---|---:|
| EURUSD | **55,5 %** | Tickmill EU | GRÜN | 30:1 |
| GBPJPY | 57,8 % | IC Markets EU | GELB | 20:1 |
| XAUUSD | **51,0 %** | IC Markets EU / Tickmill EU | GRÜN | 20:1 |
| DE40 | **51,6 %** | Tickmill EU | GRÜN | 20:1 |
| BTCUSD | — | — | **nicht bewertbar** | 2:1 |
| NVDA | **52,3 %** | Admirals EU | GRÜN | 5:1 |

**grün: 4 von 6 — gefordert: mindestens 3. → M1 = GRÜN.**

**Strenge Lesart geprüft.** M1 sagt „bei mindestens einem Broker". Streng gelesen muss
**ein** Broker die drei grünen Instrumente tragen, nicht drei Broker je eines — sonst baut
man ein Konto zusammen, das es nicht gibt. Gemessen: **jeder** der vier Broker trägt für
sich genommen 3 grüne Instrumente. Das Urteil hält also auch streng gelesen.

### Warum das Urteil keine Reserve hat

Dieselbe Rechnung unter fünf **gleich vertretbaren** Lesarten derselben Daten
(Tabelle 2b der Rohausgabe). Der Maßstab M1 wird dabei nicht angetastet — er stand vor der
Messung fest.

| Lesart | grüne Instrumente | M1 |
|---|---:|---|
| **A** wie gerechnet | 4 | GRÜN |
| **B** gemessener Median-Spread des Demo-Feeds statt des veröffentlichten | 4 | GRÜN |
| **C** Slippage-Annahme verdoppelt | **3** | GRÜN |
| **D** Swap eingerechnet (25 % der Trades kreuzen den Rollover bei 4 RT/Tag) | 4 | GRÜN |
| **E** 25. Perzentil der Volatilität statt des Medians (ruhige Marktphase) | **3** | GRÜN |
| **F** B, C, D und E zusammen | **3** | GRÜN |

**M1 hält unter allen sechs Lesarten** — aber unter drei davon nur noch mit genau den
geforderten drei Instrumenten. **EURUSD fällt in C, E und F heraus.** Die drei, die in
jeder Lesart grün bleiben, sind **XAUUSD, DE40 und NVDA**.

### Der Befund, der schwerer wiegt als die Ampel

`risk/stop_budget.py` setzt `max_cost_drag = 0,05`: die Kosten dürfen den Nulldurchgang um
höchstens 5 Prozentpunkte anheben, also **p ≤ 55 %**. Daraus folgt eine Kostenuntergrenze
von 10 × K. Liegt sie über dem gemessenen Median-ATR, ist ein Stop von 1,0 × ATR nach der
**eigenen Politik dieses Systems** unzulässig:

| Instrument | K (bp) | Kostenuntergrenze (10 × K) | ATR-Median (bp) | 1,0 × ATR zulässig? |
|---|---:|---:|---:|---|
| EURUSD | 1,10 | 11,01 | 10,04 | **NEIN** |
| GBPJPY | 1,84 | 18,35 | 11,72 | **NEIN** |
| XAUUSD | 0,85 | 8,47 | 41,80 | ja |
| DE40 | 0,87 | 8,73 | 26,81 | ja |
| NVDA | 4,19 | 41,88 | 91,18 | ja |

**Bei den beiden Währungspaaren ist der Stopabstand, auf dem M1 gemessen wird, nach der
hauseigenen Politik nicht handelbar.** M1 bleibt davon unberührt — der Maßstab wird nicht
nachträglich verschoben —, aber das grüne Urteil für EURUSD ist ohne eine Verlängerung des
Horizonts nicht umsetzbar. Die M1-Schwelle von 56 % ist lockerer als die hauseigene
55-%-Regel; dieser Widerspruch liegt nicht im Maßstab, sondern im Vorhaben.

### Gegen M2

M2 misst die Jahreskostenlast **bei der geplanten Auslegung**: 4 Round-Turns je Handelstag,
250 Tage, Hebel 5 (Krypto 2).

| Instrument | Spanne über die Broker | reißt 50 %? |
|---|---|---|
| EURUSD | 55,1 – 63,7 % | **ja, alle 4** |
| GBPJPY | 91,8 – 180,1 % | **ja, alle 4** |
| XAUUSD | 42,3 – 81,7 % | ja, 1 von 4 (Admirals) |
| DE40 | 43,7 – 55,8 % | ja, 2 von 4 |
| NVDA | 209,4 – 1.153,6 % | **ja, beide** |

**13 von 18 Kostenzeilen reißen die Grenze. → M2 ausgelöst.** Nach M2 wird damit die
**Betriebsauslegung** geändert, nicht der Maßstab.

### Die Gegenrechnung — welche Auslegung hält?

Je Instrument mit dem **günstigsten** Broker gerechnet (wer ein Instrument handelt, wählt
dafür nicht den teuersten Anbieter):

| Umschlag | Hebel | höchste Jahreskostenlast | Urteil |
|---|---:|---:|---|
| 8 RT/Tag | 5 | 418,8 % | reißt (alle fünf) |
| 4 RT/Tag | 5 | 209,4 % | reißt (EURUSD, GBPJPY, NVDA) |
| 4 RT/Tag | 2 | 83,8 % | reißt (NVDA) |
| **4 RT/Tag** | **1** | **41,9 %** | **hält** |
| 2 RT/Tag | 5 | 104,7 % | reißt (NVDA) |
| **2 RT/Tag** | **2** | **41,9 %** | **hält** |
| 1 RT/Tag | 2 | 20,9 % | hält |

**Zwei tragfähige Auslegungen:** 4 Round-Turns je Tag **ohne Hebel**, oder 2 Round-Turns je
Tag bei **Hebel 2**. Beides ist weit von „mehrere Trades je Tag mit Hebel 5" entfernt. Die
Kostenlast skaliert linear in Umschlag **und** Hebel — jede Verdopplung des einen muss durch
eine Halbierung des anderen bezahlt werden.

### Und ab welchem Horizont wird p\* komfortabel?

Aufgelöst nach S: `p* ≤ x ⟺ S ≥ K / (2·(x − 0,5))`. Für x = 56 % gilt S ≥ 8,33 × K.

| Instrument | K (bp) | nötiges S für 56 % | als Vielfaches des ATR-Medians |
|---|---:|---:|---:|
| EURUSD | 1,10 | 9,18 bp | 0,91 × ATR |
| GBPJPY | 1,84 | 15,29 bp | 1,30 × ATR |
| XAUUSD | 0,85 | 7,06 bp | 0,17 × ATR |
| DE40 | 0,87 | 7,28 bp | 0,27 × ATR |
| NVDA | 4,19 | 34,90 bp | 0,38 × ATR |

Bei Wurzel-t-Skalierung entspricht ein Stopabstand von n × ATR(H1) rund n² Stunden
Haltedauer. Für GBPJPY heißt das: erst ab rund 1,3 × ATR, also knapp zwei Stunden, wird
das Kostentor grün.

---

## Der Swap — getrennt ausgewiesen

Der Swap ist **nicht** Teil von K. Bei Stundenhorizont kreuzt nur ein Teil der Positionen
den Rollover; der Anteil ist eine **Schätzung**, keine Messung:

> Bei gleichverteiltem Einstieg über den Handelstag und einer mittleren Haltedauer von
> 24/RT Stunden kreuzt ein Anteil von Haltedauer/24 den täglichen Rollover-Zeitpunkt. Bei
> 4 Round-Turns je Tag sind das 6 Stunden Haltedauer und damit **25 %** der Trades.

Bei 4 RT/Tag und den Admirals-Sätzen ergibt sich als Zuschlag auf K: EURUSD +0,31 bp
(p\* 55,5 → 57,0 %, **kippt auf gelb**), XAUUSD +0,44 bp (51,0 → 51,5 %), DE40 +0,33 bp
(51,6 → 52,2 %), NVDA +0,52 bp (52,3 → 52,6 %). Nur EURUSD kippt.

**6 von 18 Zeilen tragen gar keinen Swap in Basispunkten**, weil die Quelle den Satz in
„Punkten je Lot" veröffentlicht und den dafür nötigen Pip-Wert **nicht**. Ein geratener
Pip-Wert wäre genau die stille Annahme, die dieses Paket ausschließt; die Zeilen fallen
sichtbar aus der Swap-Rechnung.

---

## Was gegen dieses Urteil noch spricht

Aus der adversarischen Gegenprüfung übernommen, weil es zum Urteil gehört:

1. **P/L-proportionale Kosten fehlen strukturell.** Eine Währungsumrechnungsgebühr (Konto in
   EUR, Instrument in USD/JPY) wirkt als konstanter Aufschlag auf p\*, der von einem großen
   ATR **nicht** verdünnt wird: +0,15 bis +0,50 Prozentpunkte bei 0,3 bis 1,0 % Gebühr.
   Betroffen sind alle Instrumente außer DE40.
2. **Der gemessene Spread des Demo-Feeds liegt bei EURUSD 3,3- bis 6,7-fach über dem
   veröffentlichten** der drei Raw-Broker (0,172 bp Median gegen 0,052–0,086 bp). Bei
   XAUUSD, DE40 und NVDA wirkt die Gegenprobe dagegen entlastend.
3. **Die Mindestkommission je Ticket** ist nur bei Admirals/NVDA dokumentiert und dort nicht
   eingerechnet; unterhalb von rund 12 Aktien je Position kippt diese Zeile auf gelb.

Keiner dieser Punkte kippt M1 für sich. Zusammen erklären sie, warum das Urteil „grün ohne
Reserve" lautet und nicht einfach „grün".
