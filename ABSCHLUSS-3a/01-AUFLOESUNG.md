# Auflösung (A1)

Kann eine Ereignisstudie den gesuchten Effekt überhaupt von Null trennen? Diese Frage
wird hier **vor** jeder Messung beantwortet, weil eine Studie, die es nicht kann, trotzdem
eine Zahl liefert — und die Zahl ist dann Rauschen.

Bedingung, wie in `mt5_trading_ai/backtest/resolution.py` umgesetzt:

    nötige_Sharpe(N, T) × Fensterstreuung  ≤  3 × K

Beleg: `tests/test_resolution.py` (25 Fälle), Rohausgabe in
[`07-AUSGABEN/aufloesung.txt`](07-AUSGABEN/aufloesung.txt), Messdatei
`config/aufloesung.json`, Reihen-Manifeste in `config/reihen/`.

Parameter des Laufs: T = 12 Versuche, Deflationsschwelle 0,95, Kostenfaktor 3,0.

---

## 1. Was §1 genähert hat und was gemessen wurde

§1 des Auftrags hat die Fensterstreuung als `ATR(H1) × √Fensterlänge` geschätzt. Gemessen
wird sie hier als Standardabweichung der Rendite über **nicht überlappende** Fenster der
tatsächlichen Reihe.

| Instrument | Fenster | genähert (bp) | gemessen (bp) | Abweichung |
|---|---|---:|---:|---:|
| EURUSD | 1h | 10,04 | 9,84 | −2 % |
| EURUSD | 4h | 20,08 | 23,69 | +18 % |
| EURUSD | 1d | 49,19 | 57,58 | +17 % |
| GBPJPY | 1h | 11,72 | 14,29 | **+22 %** |
| GBPJPY | 4h | 23,44 | 34,10 | **+45 %** |
| GBPJPY | 1d | 57,42 | 83,22 | **+45 %** |
| XAUUSD | 1h | 41,80 | 20,87 | **−50 %** |
| XAUUSD | 4h | 83,60 | 44,63 | **−47 %** |
| XAUUSD | 1d | 204,78 | 110,14 | **−46 %** |
| DE40 | 1h | 26,81 | 26,17 | −2 % |
| DE40 | 4h | 53,62 | 54,73 | +2 % |
| DE40 | 1d | 131,34 | 129,05 | −2 % |
| NVDA | 1h | 91,18 | 111,40 | **+22 %** |
| NVDA | 4h | 182,36 | 236,22 | **+30 %** |
| NVDA | 1d | 446,69 | 541,38 | **+21 %** |

**Warum die Näherung dort abweicht, wo sie um mehr als 20 % abweicht** — der Auftrag
verlangt für jeden solchen Fall eine Zeile:

- **XAUUSD, alle drei Fenster (−46 bis −50 %).** Die Näherung überschätzt am stärksten
  dort, wo der ATR am wenigsten über die Schluss-zu-Schluss-Bewegung sagt. Der ATR misst
  die **Spanne** einer Kerze, die Streuung misst die **Rendite** von Schluss zu Schluss.
  Gold läuft innerhalb einer Stunde weit und kehrt darin zurück; die Spanne ist groß, die
  Nettobewegung klein. Das ist keine Kleinigkeit: nur wegen dieses Unterschieds wird
  XAUUSD unten von „blind" auf „auflösbar" gedreht.
- **GBPJPY, alle drei Fenster (+22 bis +45 %).** Hier zeigt die Näherung in die andere
  Richtung. Der ATR wurde auf H1 gemessen; die Wurzelskalierung unterstellt, dass
  Stundenrenditen unkorreliert sind. Bei GBPJPY sind sie es nicht — der Yen trägt Trends
  über Stunden hinweg, Bewegungen setzen sich fort statt sich auszugleichen. Wo Renditen
  positiv korrelieren, wächst die Streuung **schneller** als mit √t, und die Näherung
  fällt zu niedrig aus.
- **NVDA, alle drei Fenster (+21 bis +30 %).** Dieselbe Ursache, andere Herkunft: eine
  Aktie handelt nicht rund um die Uhr. Über Nacht und übers Wochenende sammeln sich
  Nachrichten, die beim nächsten Auftakt in einer einzigen Bewegung stehen. Ein Fenster,
  das eine solche Lücke enthält, trägt eine Rendite, die keine Stundenkerze je gezeigt
  hat, und die √t-Skalierung kennt sie nicht.

Die Näherung liegt also nicht zufällig daneben, sondern **systematisch in beide
Richtungen** — je nachdem, ob ein Instrument innerhalb der Kerze zurückkehrt (XAUUSD, zu
hoch geschätzt) oder über Kerzen hinweg trendet und springt (GBPJPY, NVDA, zu niedrig
geschätzt). Sie taugt zur Vorsortierung und nicht zur Entscheidung. Festgehalten in
`tests/test_resolution.py::test_wurzel_t_naeherung_ist_kein_ersatz_fuer_die_messung`.

DE40 ist der einzige Fall, in dem die Näherung durchweg trifft (−2 bis +2 %) — und
ausgerechnet dort ändert sie am Urteil nichts.

---

## 2. Die Auflösungstabelle, neu gerechnet

Beide Spalten nebeneinander, wie in A1.3 verlangt. „Verhältnis" ist nachweisbarer Effekt
geteilt durch wirtschaftlich nötigen (3 × K); über 1 heißt blind.

| Kandidatenart | Instrument | N §1 | N gemessen | Verh. §1 | Verh. gemessen | Abw. | Urteil §1 → gemessen |
|---|---|---:|---:|---:|---:|---:|---|
| täglich, 4h | EURUSD | 6.300 | 6.959 | 0,24 | **0,28** | +19 % | auflösbar → auflösbar |
| täglich, 4h | GBPJPY | 6.300 | 8.398 | 0,17 | **0,22** | +32 % | auflösbar → auflösbar |
| täglich, 4h | NVDA | 5.770 | 5.777 | 0,59 | **0,82** | +39 % | auflösbar → auflösbar |
| täglich, 4h | XAUUSD | 5.594 | 5.589 | 1,36 | **0,78** | −43 % | blind → **auflösbar** |
| täglich, 4h | DE40 | 3.528 | 3.535 | 1,07 | **1,16** | +9 % | blind → blind |
| täglich, 1h | EURUSD | 252 | 2.769 | 0,60 | **0,19** | −69 % | auflösbar → auflösbar |
| täglich, 1h | GBPJPY | 252 | 2.769 | 0,42 | **0,16** | −61 % | auflösbar → auflösbar |
| monatlich, 4h | GBPJPY | 300 | 399 | 0,77 | **1,03** | +34 % | auflösbar → **blind** |
| monatlich, 4h | EURUSD | 300 | 331 | 1,10 | **1,32** | +20 % | blind → blind |

Zwei Zeilen kippen, in entgegengesetzte Richtungen:

- **XAUUSD/4h/täglich wird auflösbar** (1,36 → 0,78), allein wegen der überschätzten
  Streuung. §1 hatte XAUUSD als „knapp blind" geführt — zu Unrecht.
- **GBPJPY/4h/monatlich wird blind** (0,77 → 1,03). Das ist der Kandidat **K3
  (Monatsende-Fixing)**. Er fällt knapp, um 3 %, und die Schwelle ist die Schwelle. Im
  **1h-Fenster** löst dieselbe Frage jedoch auf (0,77) — dazu Abschnitt 4.

Die 1h-Zeilen weichen am stärksten ab (−61 bis −69 %), und das liegt nicht an der
Streuung, sondern an N: §1 rechnete mit 252 Ereignissen aus einem Jahr, tatsächlich
verfügbar sind elf Jahre H1-Historie und damit 2.769.

**Die vollständige Messung: 13 von 30 Kombinationen sind auflösbar.**

| Instrument | Fenster | Frequenz | N | Streuung (bp) | K (bp) | 3×K (bp) | nachweisbar (bp) | Verhältnis |
|---|---|---|---:|---:|---:|---:|---:|---:|
| GBPJPY | 1h | täglich | 2.769 | 14,29 | 1,84 | 5,51 | 0,90 | **0,16** |
| EURUSD | 1h | täglich | 2.769 | 9,84 | 1,10 | 3,30 | 0,62 | **0,19** |
| GBPJPY | 4h | täglich | 8.398 | 34,10 | 1,84 | 5,51 | 1,23 | **0,22** |
| EURUSD | 4h | täglich | 6.959 | 23,69 | 1,10 | 3,30 | 0,94 | **0,28** |
| XAUUSD | 1h | täglich | 2.769 | 20,87 | 0,85 | 2,54 | 1,31 | **0,52** |
| GBPJPY | 1d | täglich | 8.398 | 83,22 | 1,84 | 5,51 | 3,01 | **0,55** |
| NVDA | 1h | täglich | 2.768 | 111,40 | 4,19 | 12,56 | 7,02 | **0,56** |
| DE40 | 1h | täglich | 2.769 | 26,17 | 0,87 | 2,62 | 1,65 | **0,63** |
| EURUSD | 1d | täglich | 6.959 | 57,58 | 1,10 | 3,30 | 2,29 | **0,69** |
| GBPJPY | 1h | monatlich | 131 | 14,29 | 1,84 | 5,51 | 4,24 | **0,77** |
| XAUUSD | 4h | täglich | 5.589 | 44,63 | 0,85 | 2,54 | 1,98 | **0,78** |
| NVDA | 4h | täglich | 5.777 | 236,22 | 4,19 | 12,56 | 10,29 | **0,82** |
| EURUSD | 1h | monatlich | 131 | 9,84 | 1,10 | 3,30 | 2,92 | **0,88** |

Die 17 übrigen Kombinationen sind blind. Drei Muster:

1. **Das 1h-Fenster löst überall auf**, an allen fünf Instrumenten, für tägliche
   Ereignisse (0,16 bis 0,63). Das kurze Fenster schlägt die größere Ereigniszahl des
   langen: 2.769 Ereignisse bei 9,84 bp Streuung sind besser als 6.959 bei 23,69 bp.
2. **Monatliche Fragen lösen nur im 1h-Fenster auf**, und nur bei EURUSD und GBPJPY
   (0,77 und 0,88). In jedem anderen Fenster und an jedem anderen Instrument sind sie
   blind (1,03 bis 12,83). Festgehalten in
   `tests/test_resolution.py::test_monatliche_kandidaten_loesen_nur_im_stundenfenster_auf`.
3. **Das Tagesfenster ist der schlechteste Schnitt** — es löst nur bei EURUSD und GBPJPY
   auf, wo die Historie am tiefsten reicht, und auch dort nur knapp.

---

## 3. Vier eigene Fehler in diesem Schritt

Alle vier sind beim Nachrechnen der jeweils vorigen Fassung aufgefallen; drei von ihnen
hätten das Kandidatenfeld falsch beschnitten. Sie stehen hier, weil ein Befund ohne die
Fehlerliste, die zu ihm geführt hat, nur die halbe Wahrheit ist.

**Fehler 1 — N war die Fensterzahl statt der Ereigniszahl.** Der erste Lauf setzte für
das 4h-Fenster N = 38.882 ein: die Zahl aller Fenster der Reihe. Richtig ist die Zahl der
**Ereignisse**, und ein tägliches Ereignis liefert je Handelstag eines, auch wenn der Tag
sechs Vier-Stunden-Fenster hat. Der Fehler blähte N um das Sechsfache und senkte die
nötige Sharpe um Faktor √6 ≈ 2,4. Er ließ blinde Kombinationen auflösbar aussehen, also
**in genau der schmeichelnden Richtung**.

**Fehler 2 — K ohne Währungsumrechnung.** Die Funktion, die K je Instrument holt, hatte
die Kostenformel aus `tools/kostentor.py` nachgebaut und dabei die Umrechnung der
Kommission verloren. Bei GBPJPY steht das Nominal in JPY und die Kommission in USD: ohne
Umrechnung fiel sie von 0,44 auf 0,003 bp, K von 1,84 auf 1,31 bp. Weil ein kleineres K
die nachzuweisende Wirkung 3 × K senkt, wanderte GBPJPY/4h/monatlich auf 1,52 statt 1,03
— K3 wäre aus dem falschen Grund gestorben. Behoben, indem der Nachbau **gelöscht** wurde:
`tools/aufloesung.py::_kosten_bps` ruft jetzt `tools/kostentor.py::_zeile` auf, dieselbe
Funktion, die das Kostentor aus Paket 2 führt. Seither decken sich alle fünf K-Werte
exakt mit §1 (1,10 / 1,84 / 0,85 / 0,87 / 4,19) — die einzige Abweichung gegen den
Auftrag war der Nachbau.

**Fehler 3 — die Historie zu kurz abgefragt.** Der Abruf stand auf 25 Jahren für D1/H4
und **zwei** Jahren für H1. Die zwei Jahre waren eine Notlösung, weil ein 25-Jahre-Abruf
auf H1 leer zurückkam; sie wurden nie nachgeprüft. Eine Treppenprobe (3, 5, 8, 9, 10, 11
Jahre) liefert bis **elf Jahre** an allen fünf Instrumenten — N für jedes 1h-Fenster war
um Faktor 5,5 zu klein. Auf D1 reicht EURUSD bis 1981 und GBPJPY bis 1993; mit 25 Jahren
fehlten GBPJPY rund 2.200 Handelstage. **Der Grund, warum es auffiel, steht im Auftrag
selbst:** „Eine leere Antwort heißt ‚noch nicht geladen', nicht ‚gibt es nicht.'" Das
Terminal lädt Historie auf Anfrage nach — der Abruf über zwölf Jahre kam zweimal sofort
leer zurück, und spätere Abrufe über elf Jahre lieferten trotzdem 68.324 Kerzen. Eine
leere Antwort ist hier ein Zustand, kein Befund.

**Fehler 4 — vier Jahrzehnte EURUSD, die es nie gab.** Der tiefere Abruf brachte
EURUSD-Tageskerzen ab 1981-08-18 zutage, nahtlos an die echte Reihe angesetzt: Schluss
1,17240 am 31.12.1998, Eröffnung 1,18010 am 04.01.1999. Den Euro gibt es seit dem
01.01.1999. Alles davor ist eine zurückgerechnete Korbreihe, kein gehandelter Kurs — 4.480
Kerzen, die N um 71 % aufgebläht hätten, aus einem anderen Streuungsregime (67,1 gegen
58,1 bp Tagesrendite). Ein Ereignis, das nie handelbar war, ist kein Ereignis. Der Schnitt
steht in `tools/aufloesung.py::FRUEHESTE_KERZE` und ist durch
`tests/test_resolution.py::test_eurusd_reihe_beginnt_nicht_vor_dem_euro` gesichert, damit
er nicht still wieder herausfällt.

Die Lehre aus Fehler 2 ist dieselbe wie beim NVDA-Kommissionsfehler aus Paket 2
([`../ABSCHLUSS/09-EIGENE-FEHLER.md`](../ABSCHLUSS/09-EIGENE-FEHLER.md)): eine zweite
Umsetzung derselben Rechnung ist keine Bequemlichkeit, sondern eine zweite Fehlerquelle.
Die Lehre aus 3 und 4 ist neu und unbequemer: **eine Grenze, die man selbst gesetzt hat,
sieht in der Ausgabe genauso aus wie eine Grenze der Daten.** Beide Male stand in der
Tabelle eine glatte Zahl — „2,0 Jahre", „25,0 Jahre" —, und beide Male war sie mein Echo,
nicht die Antwort des Terminals.

---

## 4. Was das für das Kandidatenfeld heißt

§5 legt Kandidaten über Ereignisart, Zeitpunkt und Instrument fest, **nicht über die
Fensterlänge**. Die Fensterlänge ist damit Teil des Studienaufbaus. Regel, hier
festgeschrieben, bevor eine Wirkung gemessen wird: **je Kandidat wird das Fenster mit dem
niedrigsten Verhältnis genommen.** Das ist keine Auswahl auf das Ergebnis — die
Auflösungsrechnung kennt nur N, Streuung und K und weiß nichts über den gesuchten Effekt.

| Kandidat | Ereignis | Instrument | Fenster | Verhältnis | Stand |
|---|---|---|---|---:|---|
| K1 | London-Fixing 16:00 | EURUSD | 1h | 0,19 | **bleibt** |
| K1 | London-Fixing 16:00 | GBPJPY | 1h | 0,16 | **bleibt** |
| K2 | Tokioter TTM 09:55 JST | GBPJPY | 1h | 0,16 | **bleibt** |
| K3 | Monatsende-Fixing | GBPJPY | **1h** | 0,77 | **bleibt, Fenster geändert** |
| K4 | Täglicher Rollover | EURUSD | 1h | 0,19 | **bleibt** |
| K4 | Täglicher Rollover | GBPJPY | 1h | 0,16 | **bleibt** |
| K5 | NASDAQ-Schlussauktion | NVDA | 1h | 0,56 | **bleibt** |

**Alle fünf Kandidaten bleiben, das Feld behält seine 7 Versuche von 12.** K3 wechselt vom
4h- ins 1h-Fenster: im 4h-Fenster ist die Frage blind (1,03), im 1h-Fenster auflösbar
(0,77). K3 ist damit der knappste Kandidat im Feld und der einzige, der auf nur 131
Ereignissen steht — elf Jahre H1-Historie mal zwölf Monatsenden. Fällt in der Datenlage
etwas an der H1-Reihe aus, fällt K3 zuerst.

**Zu XAUUSD und DE40:** §5 hält die fünf Reserveversuche ausdrücklich für den Fall bereit,
„falls die gemessene Streuung aus A1 sie doch auflösbar macht". Genau das ist eingetreten
— XAUUSD löst im 1h-Fenster mit 0,52 auf, DE40 mit 0,63. Ein Nachrücken wäre also
vorgesehen und nicht nachträgliche Auswahl. **Es unterbleibt trotzdem, und zwar aus einem
Grund, der nichts mit den Zahlen zu tun hat:** ein Kandidat braucht nach der Regel des
Feldes dieselbe Begründungstiefe wie K1 bis K5, also eine benannte Gruppe, die zu einem
benannten Zeitpunkt handeln **muss**. Für XAUUSD wäre das die LBMA-Auktion, für DE40 die
Xetra-Schlussauktion; beides ist plausibel und beides ist hier nicht ausgearbeitet.
Kandidaten aufzunehmen, weil ihre Auflösungszahl passt, und die wirtschaftliche Begründung
nachzureichen, kehrt die Reihenfolge um, auf der das ganze Feld beruht.

Das ist eine endgültige Entscheidung, keine Vertagung: die Feldregel lässt Ergänzungen nur
zu, **bevor** die erste Studie läuft. Die Messung steht hier für ein späteres Paket bereit,
das dann seine eigene Versuchszahl mitbringt.

**Es bleibt mehr als ein Kandidat übrig, damit tritt der orange Ausgang aus A1.3 nicht ein
und A3 entfällt nicht.** Ob A3 tatsächlich laufen kann, entscheidet nicht diese Datei,
sondern die Datenlage — siehe [`02-DATENLAGE.md`](02-DATENLAGE.md).
