# Datenlage (A1.1 / A1.2)

Woher die Kurse kommen, wie tief sie reichen, und ob man ihnen glauben kann. Die Antwort
auf die dritte Frage hat in diesem Paket alles andere überholt.

**Kurzfassung:** Der Terminal-Feed ist ausgezeichnet — er stimmt mit einer unabhängigen
institutionellen Quelle auf **0,09 bp** je Stundenrendite überein. Aber seine Zeitstempel
sind **nicht UTC**: sie tragen die Serverzeit des Brokers (EET/EEST, also UTC+2 im Winter
und UTC+3 im Sommer) und werden vom Adapter als UTC ausgegeben. Wer das nicht korrigiert,
legt jedes Ereignisfenster zwei bis drei Stunden neben das Ereignis.

---

## 1. Historientiefe (A1.1)

Gelesen über `RealMt5Terminal` mit `allow_write=False` auf dem Demokonto. Jede Scheibe
wurde bei leerer Antwort ein zweites Mal abgefragt; das vollständige Abrufprotokoll mit
Zeitstempeln steht in `config/aufloesung.json` unter `retrieval_log`.

| Instrument | TF | Kerzen | von | bis | Jahre |
|---|---|---:|---|---|---:|
| EURUSD | D1 | 7.181 | 1999-01-04 | 2026-08-17 | 27,6 |
| EURUSD | H4 | 43.012 | 1999-01-04 | 2026-08-17 | 27,6 |
| EURUSD | H1 | 99.998 | 2010-07-07 | 2026-08-17 | 16,1 |
| GBPJPY | D1 | 8.658 | 1993-04-19 | 2026-08-17 | 33,3 |
| GBPJPY | H4 | 44.470 | 1993-04-19 | 2026-08-17 | 33,3 |
| GBPJPY | H1 | 99.998 | 2010-07-06 | 2026-08-17 | 16,1 |
| XAUUSD | D1 | 5.699 | 2004-06-11 | 2026-08-17 | 22,2 |
| XAUUSD | H4 | 33.976 | 2004-06-11 | 2026-08-17 | 22,2 |
| XAUUSD | H1 | 99.998 | 2009-07-17 | 2026-08-17 | 17,1 |
| DE40 | D1 | 3.537 | 2012-08-06 | 2026-08-17 | 14,0 |
| DE40 | H4 | 16.739 | 2012-08-06 | 2026-08-17 | 14,0 |
| DE40 | H1 | 60.450 | 2012-08-06 | 2026-08-17 | 14,0 |
| NVDA | D1 | 5.760 | 2003-09-10 | 2026-08-14 | 22,9 |
| NVDA | H4 | 11.539 | 2003-09-10 | 2026-08-14 | 22,9 |
| NVDA | H1 | 40.566 | 2003-09-10 | 2026-08-14 | 22,9 |

Drei Dinge an dieser Tabelle sind nicht selbsterklärend:

**EURUSD beginnt 1999, nicht früher.** Das Terminal liefert Tageskerzen ab 1981-08-18,
nahtlos angesetzt (Schluss 1,17240 am 31.12.1998, Eröffnung 1,18010 am 04.01.1999). Den
Euro gibt es seit dem 01.01.1999; die 4.480 Kerzen davor sind eine zurückgerechnete
Korbreihe und kein gehandelter Kurs. Sie sind verworfen —
`tools/aufloesung.py::FRUEHESTE_KERZE`, gesichert durch
`tests/test_resolution.py::test_eurusd_reihe_beginnt_nicht_vor_dem_euro`.

**99.998 ist eine Terminal-Einstellung, keine Broker-Grenze.** Drei Instrumente landen auf
exakt dieser Zahl bei drei verschiedenen Anfangsdaten; DE40 und NVDA liegen darunter und
sind vollständig. Das ist die Obergrenze „Max bars in chart" (Vorgabe 100.000). **Das ist
der einzige Punkt dieses Pakets, an dem eine Handlung des Betreibers etwas verbessern
würde:** wird die Grenze im Terminal angehoben und die Historie nachgeladen, wächst die
Stundenhistorie über 16 Jahre hinaus, und mit ihr N für jeden Kandidaten. Nötig ist es
nicht — alle sieben Studien lösen auch so auf.

**Eine leere Antwort ist ein Zustand, kein Befund.** Eine einzelne Abfrage über mehr als
rund 70.000 Kerzen kommt leer zurück, nicht als Fehler. Genau daran wäre die H1-Tiefe
zweimal falsch bestimmt worden (siehe [`01-AUFLOESUNG.md`](01-AUFLOESUNG.md), Fehler 3 und
5). Der Abruf holt die Reihe deshalb in Fünfjahresscheiben.

---

## 2. Herkunft (A1.2)

Jede gelesene Reihe wird selbst gehasht, nicht die Datei: SHA-256 über Zeitstempel und
OHLC je Kerze, kanonisch als Text. So hängt die Prüfsumme an den Daten und nicht an einer
Formatierung. 15 Manifeste in `config/reihen/`, nach dem Muster von
`tests/fixtures/*.manifest.json`:

```json
{ "symbol": "EURUSD", "timeframe": "H1", "bars": 99998,
  "first": "2010-07-07T05:00:00+00:00", "last": "2026-08-17T...",
  "checksum": "…", "retrieved_at": "…", "source": "mt5-terminal-read-only" }
```

Diese Prüfsumme ist die `data_checksum`, die `gates/trials.py` je Versuch verlangt. Ohne
sie zählt eine Studie nach der eigenen Regel des Repos nicht.

Die Geheimnisprüfung meldet für diese Dateien 20 Rohfunde („Hex High Entropy String") —
das sind die Prüfsummen selbst, plus fünf vorbestehende Testfixtures. Kein Geheimnis; der
Detektor tut, wofür er gebaut ist. Rohausgabe in
[`07-AUSGABEN/geheimnis_scan.txt`](07-AUSGABEN/geheimnis_scan.txt).

---

## 3. Die Gegenprobe — und was sie zutage brachte

Der Auftrag verlangt für EURUSD und GBPJPY die Gegenprobe auf D1 gegen Dukascopy, mit der
Regel: **weicht die Tagesrendite im Median um mehr als 2 bp ab, ist der Terminal-Feed für
diese Studie nicht brauchbar.**

### 3.1 Das Tor reißt

| Instrument | Zeitraum | verglichene Tage | Median | Mittel | Urteil |
|---|---|---:|---:|---:|---|
| EURUSD | 2023–2024 | 520 | **3,57 bp** | 4,66 bp | über der Schwelle |
| GBPJPY | 2023–2024 | 519 | **6,84 bp** | 10,62 bp | über der Schwelle |

Das ist der Befund, den A1.2 verlangt, und er steht. Nur bedeutet er nicht, was er auf den
ersten Blick zu bedeuten scheint.

### 3.2 Eine falsche Zwischendiagnose

Der erste Erklärungsversuch verglich die Abweichung nach Wochentagen und fand, dass sie
freitags auf ein Drittel fällt (EURUSD 1,01 statt 2,30 bp Niveauabweichung). Daraus wurde
geschlossen: die Quellen schneiden den Tag **um Minuten** verschieden, ein ganzer
Stundenversatz sei ausgeschlossen, weil ein solcher rund 13 bp erzeugen müsste.

**Dieser Schluss war falsch.** Die Freitagsbeobachtung stimmte — freitags schließt der
Markt selbst, und dann ist der letzte Kurs der Woche derselbe, ganz gleich wo man den Tag
schneidet. Sie ist mit einem Stundenversatz genauso vereinbar wie ohne. Aus einer
Beobachtung, die beide Erklärungen zulässt, wurde eine ausgeschlossen — und ausgerechnet
die richtige. Die 13 bp waren eine Überschlagsrechnung, keine Messung, und sie war zu groß.

### 3.3 Die Messung, die es klärte: dieselbe Probe auf H1

Der Auftrag hält fest, dass `tools/fetch_data.py` „nur D1" kann. Das stimmte; Dukascopy
legt Stundenkerzen aber monatsweise ab (`BID_candles_hour_1.bi5`), und der vorhandene
Dekoder liest sie unverändert. Die Gegenprobe wurde deshalb auf **H1** wiederholt — den
Zeitrahmen, auf dem alle sieben Studien laufen — und dabei über ganze Stundenverschiebungen
abgetastet:

| Verschiebung | EURUSD | GBPJPY |
|---|---:|---:|
| −4 h | 4,85 bp | 7,86 bp |
| **−3 h** | **0,28 bp** | **0,55 bp** |
| −2 h | 1,26 bp | 2,48 bp |
| −1 h | 4,85 bp | 7,96 bp |
| 0 h | 5,08 bp | 8,40 bp |
| +1 … +4 h | 5,17–5,33 bp | 8,31–8,42 bp |

Das Minimum ist kein flaches Tal, sondern eine Nadel. Der Terminal-Feed liegt **drei
Stunden vor UTC** — und richtig gelesen stimmt er mit der Fremdquelle auf **0,28 bp**
überein statt auf 5,08.

### 3.4 Der Versatz ist nicht konstant

Monatsweise gemessen, EURUSD 2024:

| Monat | Jan | Feb | Mär | Apr | Mai | Jun | Jul | Aug | Sep | Okt | Nov | Dez |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bester Versatz | −2 h | −2 h | −2 h | −3 h | −3 h | −3 h | −3 h | −3 h | −3 h | −3 h | −2 h | −2 h |

Ein **fester** Versatz wäre sieben Monate im Jahr falsch, ein fester von −2 h fünf Monate.
Das Muster ist die EU-Sommerzeit: **EET/EEST**, UTC+2 im Winter, UTC+3 im Sommer,
Umstellung am 31.03.2024 und 27.10.2024 — genau die Tage der Zeitzonendatenbank.

Gegenprobe mit dem Zeitzonenmodell statt mit einer festen Zahl: die Zeitstempel als naive
`Europe/Helsinki`-Ortszeit gelesen und nach UTC gedreht, ergibt für **jeden einzelnen
Monat**:

| Jan | Feb | Mär | Apr | Mai | Jun | Jul | Aug | Sep | Okt | Nov | Dez | gesamt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0,092 | 0,093 | 0,092 | 0,093 | 0,093 | 0,093 | 0,092 | 0,091 | 0,090 | 0,092 | 0,095 | 0,096 | **0,093 bp** |

Kein saisonaler Rest. Über 6.171 Stundenrenditen liegt der Median bei **0,093 bp** — ein
Neuntel eines Basispunkts. Das ist keine „brauchbare" Übereinstimmung, das ist dieselbe
Preisreihe.

### 3.5 Damit ist auch die D1-Abweichung erklärt

Vier Rechnungen auf denselben Daten, EURUSD 2023–2024:

| Rechnung | Median |
|---|---:|
| Terminal-D1 wie geliefert, nach Datumsetikett | 3,57 bp |
| Terminal-D1, Etikett um einen Tag verschoben | 39,7 / 40,1 bp |
| Tagesschluss **aus H1 gebaut, ohne Drehung** | **3,57 bp** |
| Tagesschluss aus H1 gebaut, **−3 h, Schnitt 00:00 UTC** | **1,12 bp** |

Die dritte Zeile trifft die erste auf die Stelle genau: die Tageskerze des Terminals ist
der letzte Stundenschluss des **Server**tages. Die vierte zeigt, was übrig bleibt, wenn man
den Tag schneidet wie die Fremdquelle — **1,12 bp, unter der Schwelle.**

**Das Urteil, präzise:** Das Tor aus A1.2 reißt so, wie es formuliert ist — mit 3,57 und
6,84 bp. Die Ursache ist aber nicht die Datenqualität, sondern die Zeitzonenauslegung.
Richtig gedreht besteht der Feed dieselbe Probe mit 0,28 bp auf H1 und 1,12 bp auf D1. Der
Feed ist brauchbar; **die naive Lesart der Zeitstempel ist es nicht.**

---

## 4. Ein Mangel im Adapter

`RealMt5Terminal._utc()` in [`mt5_trading_ai/venue/mt5.py:1007`](../mt5_trading_ai/venue/mt5.py)
lautet:

```python
@staticmethod
def _utc(epoch_seconds: Any) -> datetime:
    return datetime.fromtimestamp(int(epoch_seconds), tz=UTC)
```

MetaTrader liefert Balkenzeiten so, dass sie **als UTC gelesen die Server-Ortszeit
ergeben**. Die Funktion hängt darum das Etikett `UTC` an eine Zeit, die keine ist. Weder
ihr Name noch `Mt5Rate.ts` noch irgendein Kommentar im Modul erwähnt das; die einzige
Stelle im Repo, die über Handelsplatz-Zeitzonen nachdenkt, ist `FxSession` in
`data/loader.py`, und die betrifft die Fremdquelle.

Das ist ein Mangel und kein Streit über Konventionen: eine Zeit, die `+00:00` trägt und
keine UTC ist, ist für jeden Verbraucher falsch, der sie mit einer echten UTC-Zeit
vergleicht.

**Nicht in diesem Paket behoben, und zwar bewusst.** Die Korrektur gehört in den Adapter,
aber sie braucht die Serverzeitzone als Eingabe, und die kennt das Terminal nicht von
selbst — sie ist hier gemessen worden. Sie im Adapter fest zu verdrahten hieße, eine
gemessene Eigenschaft eines bestimmten Brokers in eine Schicht zu schreiben, die für jeden
Broker gilt. Paket 3a liest nur; der Umbau eines Schreibpfad-Moduls ist nicht sein
Auftrag. Der Weg für A2 ist deshalb: **die Zeitzone steht im Ereigniskalender, und die
Studie dreht dort.** Für den Betreiber bleibt es ein offener Punkt, den
[`05-URTEIL.md`](05-URTEIL.md) führt.

Was dieser Mangel **nicht** berührt: das Kostentor und die ATR-Messung aus Paket 2 rechnen
mit Kerzenabständen und Kursen, nicht mit Tageszeiten. Ein durchgehender Versatz aller
Zeitstempel um denselben Betrag verschiebt keinen Abstand. Betroffen ist genau das, was
eine **Uhrzeit** braucht — und das ist jede einzelne Studie dieses Pakets.

---

## 5. Nebenbefund: das Sessionmodell auf Intraday

Beim Ablegen der Stundenreihe fiel das Qualitätstor mit `gap_ratio_above_limit` durch,
Lücke 1,63 %. Nachgezählt: 26 fehlende Werktagsstunden, davon **24 an Freitagen um 22:00
und 23:00 UTC** (je zwölf) und zwei um 21:00. Das ist der Wochenschluss des Devisenmarkts,
kein Datenverlust — `WeekdaySession` hält jede Stunde von Montag bis Freitag für eine
Handelsstunde.

Das Repo hat die richtige Antwort bereits: `FxSession` verankert die Woche an New York
17:00 und ist sommerzeitfest. Sie war im H1-Pfad nur nicht benutzt — mein Fehler beim
Einbau, nicht ein Mangel von Paket 2. Mit `FxSession` und ohne den Wochentagsfilter (der
die gültigen Sonntagabend-Kerzen gelöscht hätte) besteht das Tor mit **0,00 %** Lücke.

---

## 6. Was das für A3 heißt

| Frage | Antwort |
|---|---|
| Reicht die Historie? | Ja, für alle sieben Studien. Tiefer ginge über die Terminal-Einstellung. |
| Gibt es Prüfsummen? | Ja, 15 Manifeste; `data_checksum` je Studie ist gedeckt. |
| Stimmt der Feed mit einer zweiten Quelle? | Ja: 0,09 bp je Stundenrendite, alle zwölf Monate. |
| Sind die Zeitstempel verwendbar? | **Nur gedreht.** Naiv gelesen liegt jedes Fenster 2–3 h daneben. |
| Blockiert etwas A3? | Nein — sofern die Drehung in A2 verbindlich verankert wird. |

Die letzte Zeile ist die Bedingung, unter der dieses Paket weitergeht. Sie ist in
[`03-KALENDER.md`](03-KALENDER.md) einzulösen, nicht zuzusichern.
