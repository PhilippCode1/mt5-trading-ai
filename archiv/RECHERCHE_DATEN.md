# RECHERCHE_DATEN.md — R2: Das Datenfundament

*Teil 3, Paket 2. Broker-interne CFD-Feeds sind synthetische Hauspreise; ein Backtest
darauf misst einen Broker, nicht den Markt. Ziel: eine externe Quelle, die das
Datenqualitätstor besteht. Abrufdatum aller Web-Quellen: **2026-08-12**.*

**Methode.** Sieben parallele Rechercheure (drei Anbieter-Gruppen, drei Methoden-
Dimensionen, ein Skeptiker). Jede Angabe mit Quelle und Marke (`measured`/`estimate`).

---

## 1. Datenquellen (≥3 Optionen, mehrere < 300 €/Monat)

**Kostenlos:**
| Quelle | Granularität | Historie EURUSD | Zugang | Marke |
|---|---|---|---|---|
| **Dukascopy** | Tick + Tages-/Stundenkerzen | ~2003+ | keyless HTTP (LZMA-bi5) | measured (gewählt) |
| HistData.com | Tick + M1 | 2000+ | manueller CSV je Monat | measured |
| TrueFX | Tick (ms) | 2009+ | Registrierung, ZIP | measured |
| Alpha Vantage Free | Daily (+Intraday) | ~20 J. | API-Key, 25 Req/Tag | measured |
| Yahoo (EURUSD=X) | Daily | ~2003+ | keyless JSON | measured (schmutzig¹) |
| Stooq | Daily | lang | CSV (jetzt Anti-Bot) | estimate |

**Günstig kommerziell (< 300 €/Monat):**
| Anbieter | Preis | Granularität | Lizenz |
|---|---|---|---|
| **EODHD** | 29,99 €/mo | M1 (2009+), EOD 30 J. | nur privat; Kommerz erst „Business" 299 $/mo |
| **Twelve Data** | 29 $/mo (Grow) | M1–D1 | nur privat/intern; Kommerz separat |
| **Polygon.io / Massive** | 49 $/mo | Tick + Aggregate | privat; Redistribution höhere Tiers |
| Tiingo / Finnhub / Databento | 30–199 $/mo | Intraday/Tick | „internal use", teils kein Spot-FX |

**Premium/Referenz (Einordnung, was „sauber" kostet):** TickData (~2 900 $ EURUSD
einmalig, Mindestbestellung 1 000 $), Refinitiv/LSEG (75 k–400 k $/J.), Bloomberg
(≈32 k $/Seat/J.), ICE/OneTick/Kaiko (fünf- bis sechsstellig/J.).

> **Größtes Risiko ist die Lizenz, nicht der Preis** (Skeptiker): fast alle gratis/
> günstigen Quellen sind **nur für den persönlichen Gebrauch**; kommerzielle Nutzung/
> Weiterverteilung braucht einen höheren, bezahlten Tier. Das ist für einen späteren
> Live-Betrieb entscheidend, nicht für den Backtest-Nachweis. Deshalb wird die Marktdaten
> **nicht** ins öffentliche Repo committet — nur Code, Prüfsumme und Qualitätsbericht.

---

## 2. Was gebaut und geladen wurde

`mt5_trading_ai/data/loader.py` (rein, getestet) dekodiert Rohquellen, normalisiert und
kettet sie an das bestehende Qualitätstor (`data/quality.py`); `tools/fetch_data.py` macht
den Netzabruf. Gewählte Quelle für den ersten Edge-Test: **Dukascopy Tageskerzen**
(institutionell, keyless, bid-Seite).

**Geladen und geprüft (Beleg beiliegend):**
```
Dukascopy EURUSD 2022-2024: 365 + 365 + 366 = 1096 Kalendertag-Bars
-> Mo-Fr gefiltert: 782 Bars (2022-01-03 .. 2024-12-31)
Qualitaetstor: BESTANDEN | globale Luecke 0.000 % | 0 Ausreisser | 0 OHLC-ungueltig
Block-Ausfall-Check (max. zusammenhaengende Luecke): bestanden
Bars-Pruefsumme:     78683f92b090b99c9204ebbb0e700efd0abeebd87cf03b63e2089f7ae2cc8602
Manifest-Pruefsumme: 0b3b8b5c2a433298e7d62aaacf58fac5f7caff3ff90671456ae08bf20c238a1c
```
Die **Manifest**-Prüfsumme bindet zusätzlich Instrument, Zeitrahmen, Quelle, Preis-Divisor,
Session und Urteil — eine reine Zahlen-Prüfsumme würde eine fehl-dekodierte Reihe (falscher
Divisor) genauso „reproduzierbar" zertifizieren. Reproduzierbar heißt: gleiche Daten +
gleiche Herkunft → gleiche Prüfsumme.

**Ehrliche Einordnung der „0 % Lücke":** Sie ist **kein Vollständigkeitsbeleg**. Dukascopy
liefert für **jeden Kalendertag** eine Bar (auch Feiertage, oft geglättet); nach dem Mo-Fr-
Filter ist damit jeder Wochentags-Slot belegt → 0 % gegen rohe Kalender-Wochentage ist teils
konstruktionsbedingt. Deshalb ergänzt der Lader einen **Block-Ausfall-Check** (max.
zusammenhängende fehlende Slots, > 3 → rot), den die globale Quote auf langen Reihen nicht
fängt. Die Messung gegen einen echten Handelstags-/Feiertagskalender bleibt offen (**S6**).

**Negativ gefahren:** 20 aufeinanderfolgende Bars entfernt → Tor **rot**
(`gap_ratio_above_limit`) → zurückgenommen → grün, gleiche Prüfsumme. Zusätzlich (Unit): ein
Block von 4 fehlenden Tagen bei nur 0,8 % Gesamtlücke → **rot** durch den Block-Ausfall-Check.

¹ **Yahoo-Tagesdaten sind zu schmutzig** (das Tor lehnt sie zu Recht ab): DST-Zeitstempel
(00:00/23:00 UTC gemischt → verschobene Wochentage) und ~2,4 % OHLC-ungültige Bars, bei
denen Yahoo `open=close` als Platzhalter außerhalb [Low,High] setzt (Feiertags-/Sonntags-
Bars). Yahoo dient hier nur als **Gegenprobe-Quelle**, nicht als Fundament.

---

## 3. Gegenprobe R2.2 — Broker/Feed vs. Referenz (in Basispunkten)

**Methode:** `Abweichung_bps(t) = |Close_A(t) − Close_B(t)| / Mid(t) × 10 000` je gemeinsamem
Handelstag (`tools/fetch_data.py: counter_check_bps`). 1 Pip EURUSD ≈ 0,93 bps.

**Ergebnis (Yahoo vorher auf OHLC-Gültigkeit gefiltert: 766 von 782 Tagen, 16 verworfen):**
**Median 28,2 bps**, Mittel 37,0 bps, max 209,5 bps. Der robuste Median liegt klar unter dem
Mittel — das Mittel wird von wenigen Ausreißer-Tagen hochgezogen, und der 209-bps-Max ist
mutmaßlich ein Rest-Artefakt (Cutoff/dünner Tag), kein typischer Wert. Auch der Median ist
erheblich (~0,28 %) und belegt: **welchen Feed man nimmt, zählt.** Die Abweichung hat
**mehrere** Ursachen — echte Feed-Differenz (Interbank-bid vs. Retail-Composite, plus ein
halber Spread bid-vs-mid) **und** der FX-Tag-Cutoff (§5). Der genaue Anteil ist ohne
zeitgleiche Snapshots **nicht** aufgeschlüsselt; hier wird kein Split behauptet.

---

## 4. Bias-Fallen (R2.3) und ihr technischer Ausschluss

- **FX ist NICHT survivorship-anfällig** (Paare delisten nicht). Aktien/Indizes schon
  (Rekonstitution, delistete Titel) → Point-in-Time-Universum nötig.
- **Bar-Timestamp-Look-ahead (die Kernfalle):** Signal auf dem Close, Fill zum *selben*
  Close ist physisch unmöglich. Ausschluss: **≥1 Bar Versatz** (`shift(1)`: Signal auf
  Tag-t-Close → Fill auf Tag-t+1-Open). Gehört fest in die Backtest-Maschine (Paket 3).
- **Fixe statt variabler Spreads** verfälschen (EURUSD ~1,2 Pip um 10:00 London, ~4 Pip um
  04:00, 3–5 Pip um News). Das Kostenmodell (Paket 1) rechnet den Spread aus echtem Bid/Ask.
- **Rückwärts-revidierte Makrodaten** (NFP/GDP-Vintages) erzeugen Look-ahead → nur
  Point-in-Time-Stände verwenden, falls Makro in den Signalpfad kommt.

---

## 5. Zeitzonen, Feiertage, DST (R2.4) — Quellen für scheinbaren Edge

- Die **FX-Woche ankert an New York 17:00** (Freitagsschluss), **nicht** an einer festen
  UTC-Grenze — in UTC verschiebt sich Open/Close saisonal zwischen 22:00 (Winter) und 21:00
  (Sommer). Broker-Serverzeit GMT+2/+3 erzeugt bewusst 5 saubere D1-Bars/Woche; UTC/GMT-
  Server einen 6. Mini-Sonntagsbar + verkürzten Freitag.
- **Größter DST-Look-ahead-Fehler:** historische Zeitstempel mit den *heute* gültigen
  DST-Regeln umrechnen. Immer über die IANA-Zeitzonendatenbank, nie fester Offset.
- **Bar-Konvention (Open- vs. Close-Label)** muss eindeutig sein; MT4/MT5 exponieren nur
  Serverzeit, nicht den GMT-Offset.

**Ehrliche Grenze des aktuellen Standes:** Der Lader filtert Dukascopy-Tageskerzen auf
Mo–Fr (UTC-Tag) **vor** dem Tor. Das ist eine **Näherung** — der präzise FX-Tag ankert an
NY-17:00, nicht an UTC-Mitternacht, und der echte Sonntagabend-Öffnungsbalken wird
mitgefiltert. Die „0 % Lücke" ist deshalb **kein** Beleg, dass die Näherung folgenlos ist
(§2). Der Cutoff ist einer von mehreren Beiträgen zur ~28-bps-Abweichung (§3), nicht
nachweislich der einzige. Den NY-Anker samt Session-Logik **im** Tor (statt Vorab-Filter)
sauber zu setzen, steht als **S6** in `SPAETER.md` — Pflicht vor einem Intraday-Edge-Test.

---

## 6. Offene Punkte

1. **Lizenz** für kommerzielle/Live-Nutzung (keine Gratisquelle deckt das) → bezahlter Tier
   (EODHD Business, o. ä.) bei einem echten Betrieb.
2. **FX-Tag-Cutoff** präzise auf NY-17:00 setzen, sobald Intraday nötig ist.
3. **Intraday-Granularität** für den eigentlichen Edge-Test (Tageshürde vs. 5 Trades/Tag):
   Dukascopy-Tick-Aggregation oder ein bezahlter M1-Feed — Entscheidung mit E4.
4. Datenquelle für den laufenden Betrieb → **Tor E4**.
