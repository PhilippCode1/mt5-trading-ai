# Auflösung (A1)

Kann eine Ereignisstudie den gesuchten Effekt überhaupt von Null trennen? Diese Frage
wird hier **vor** jeder Messung beantwortet, weil eine Studie, die es nicht kann, trotzdem
eine Zahl liefert — und die Zahl ist dann Rauschen.

Bedingung, wie in `mt5_trading_ai/backtest/resolution.py` umgesetzt:

    nötige_Sharpe(N, T) × Fensterstreuung  ≤  3 × K

Sie gilt nur oberhalb der beiden Untergrenzen, unter denen `ereignisstudie.bestaetige`
gar nicht erst bestätigt (30 messbare Ereignisse, 20 Out-of-Sample-Beobachtungen).
Darunter gibt `assess` kein Urteil, sondern einen Fehler: „auflösbar, aber nicht
bestätigungsfähig" ist keine Aussage. Die 30 Zeilen der Tabelle unten sind davon nicht
berührt — die kleinste Kombination führt N = 193 und damit 65 Beobachtungen.

Beleg: `tests/test_resolution.py` (39 Fälle), Rohausgabe in
[`07-AUSGABEN/aufloesung.txt`](07-AUSGABEN/aufloesung.txt), Messdatei
`config/aufloesung.json`, Reihen-Manifeste in `config/reihen/`.
Das messende Werkzeug selbst: `tests/test_aufloesung_werkzeug.py` (17 Fälle).

Parameter des Laufs: T = 12 Versuche, Deflationsschwelle 0,95, Kostenfaktor 3,0.

---

## 0. Vorbehalt zur gesamten Tabelle (nachgetragen)

**Jedes Verhältnis in dieser Datei ist gegen die volle Ereigniszahl N gerechnet. Die
Deflation, die die Rechnung umkehrt, sieht aber nur ein Drittel davon. Alle Zahlen unten
sind damit rund Faktor √3 ≈ 1,7 zu günstig — ausnahmslos in der schmeichelnden
Richtung.**

Der Zusammenhang: `required_sharpe(N, T)` beantwortet genau eine Frage — „welche Sharpe je
Beobachtung erreicht die Deflationsschwelle?". Gestellt wird diese Frage nur an einer
Stelle, in M6.2, und dort läuft der DSR auf dem Out-of-Sample-Teil der Ereignisse
(`backtest/ereignisstudie.py`, `OOS_ANTEIL = 1/3`). Für N gehört also die Zahl der
Beobachtungen eingesetzt, die der DSR **sieht**, nicht die Zahl der Ereignisse, die es
gibt.

Mit demselben Modul nachgerechnet kippen **6 der 30 Kombinationen**, alle sechs von
„auflösbar" auf „blind". Auflösbar bleiben 7 statt 13:

| Instrument | Fenster | Frequenz | N | Beobachtungen | Verh. gedruckt | Verh. nachgerechnet |
|---|---|---|---:|---:|---:|---:|
| DE40 | 1h | täglich | 3.535 | 1.179 | 0,61 | **1,05** |
| GBPJPY | 1h | monatlich | 193 | 65 | 0,62 | **1,11** |
| EURUSD | 1d | täglich | 6.959 | 2.320 | 0,69 | **1,20** |
| XAUUSD | 4h | täglich | 5.589 | 1.863 | 0,78 | **1,35** |
| EURUSD | 1h | monatlich | 193 | 65 | 0,78 | **1,40** |
| NVDA | 4h | täglich | 5.777 | 1.926 | 0,82 | **1,42** |

**Für K3 ist das keine Korrektur an der zweiten Stelle, sondern der Wegfall der
Begründung.** §4 gibt K3 das 1h-Fenster, weil dort 0,62 steht. Gegen die
Deflationsstichprobe lautet die Zahl 1,11 — und in den beiden anderen Fenstern 1,82 (4h)
und 4,45 (1d). K3 war in **keinem** Fenster auflösbar und hätte nach M6.0 vor der Messung
ausgesondert gehört, kostenfrei. Die Studie lief trotzdem, und die widerlegende Zahl stand
in ihrem eigenen Protokoll: [`07-AUSGABEN/ereignisstudie.txt`](07-AUSGABEN/ereignisstudie.txt)
meldet für K3 „DSR 0,180 auf 64 OoS-Ereignissen" — für 64 Beobachtungen rechnet dasselbe
Modul 1,12. Festgehalten in
`tests/test_resolution.py::test_k3_gbpjpy_war_gegen_die_deflationsstichprobe_nie_aufloesbar`.

**Das ist die zweite Ausprägung von Fehler 6** aus
[`09-EIGENE-FEHLER.md`](09-EIGENE-FEHLER.md). Dort lief M6.0 gegen die geplante statt die
messbare Ereigniszahl, hier gegen die gemessene statt die deflationierte; beide Male ist
die eingesetzte Stichprobe größer als die, auf der das Urteil fällt. Beide zusammen treffen
K5 doppelt: von 5.983 geplanten Ereignissen waren 472 messbar, davon sieht die Deflation
158 — das Verhältnis für NVDA/1h steigt damit von 0,49 auf **3,02**. Die Kosten sind
dieselben wie bei Fehler 6: Versuche, verbraucht für Fragen, die nicht zu beantworten
waren. Sie werden nicht stillschweigend gestrichen.

**Was behoben ist und was nicht.** Behoben ist die Maschine: `resolution.assess` verlangt
`oos_share` als pflichtiges Argument ohne Vorgabewert — ein Vorgabewert wäre der stille
Rückfall auf ebendiesen Fehler —, `tools/aufloesung.py` liest den Anteil aus
`ereignisstudie.py`, statt ihn zu wiederholen, und `python tools/aufloesung.py --check`
rechnet jetzt jede Zeile nach, statt nur zu zählen, ob welche da sind. Gegen die abgelegte
`config/aufloesung.json` fällt dieses Tor rot, mit der Liste der kippenden Zeilen.

**Nicht behoben sind die Zahlen in dieser Datei und in `config/aufloesung.json`.** Sie
stammen aus einem Lauf über den lesenden MT5-Pfad und werden nicht nachträglich
überschrieben; die Spalte oben ist die Nachrechnung, keine zweite Messung. Solange die
Messdatei nicht gegen `OOS_ANTEIL` gerechnet ist, verlangt
`tests/test_resolution.py::test_die_echte_aufloesungsdatei_ist_in_sich_stimmig`, dass
dieser Vorbehalt hier steht.

### 0.1 Nachtrag: der Melder maß zuerst das Falsche

Der Satz, der hier zuvor stand — „er kann nicht verschwinden, ohne dass neu gemessen
wurde" — **war falsch**, und zwar auf genau die Art, gegen die dieser ganze Abschnitt
geschrieben ist. Ein Prüfer hat es ausgeführt: `pruefen()` und der zugehörige Test
fragten `"oos_share" not in roh`, also die **Anwesenheit** eines Schlüssels statt seinen
**Wert**. Wer der unverändert falsch gerechneten `config/aufloesung.json` die eine Zeile
`"oos_share": 1.0` nachtrug, drehte das Tor von rot auf grün: Rückgabe 0, Ausgabe
„ok — 13 von 30 Kombinationen auflösbar", alle sechs oben genannten Zeilen wieder als
auflösbar geführt — ohne dass eine einzige Zahl gemessen worden wäre. Die Zusicherung
auf diesen Vorbehalt lief danach überhaupt nicht mehr; er wäre löschbar gewesen.

Acht Befunde des Prüfers betrafen diesen Bereich; alle acht sind behoben, jeder mit
einem Eichfall, der ohne die Behebung rot ist. Die drei schwersten:

| Befund | Behebung | Eichfall |
|---|---|---|
| Melder prüfte die Anwesenheit des Schlüssels | Abgleich des **Werts** gegen `OOS_ANTEIL` | `test_pruefen_faellt_auf_einen_nachgetragenen_anteil_rot` |
| Im Fehlschlag stand „ok …" samt Tabelle auf stdout, der Befund erst danach auf stderr | im Fehlschlag **kein Wort** auf stdout | `test_pruefen_druckt_im_fehlschlag_kein_wort_auf_stdout` |
| `assess` ließ Stichproben durch, die `bestaetige` verwirft (18 Beobachtungen: Verhältnis 0,975, „auflösbar" — `bestaetige` wirft dort „Out-of-Sample-Drittel zu klein: 18") | Untergrenzen 30/20, gegen die echte `bestaetige` geeicht | `test_die_untergrenzen_sind_die_der_bestaetigung` |

Die fünf übrigen: das `except` in `pruefen()` umschloss den `assess`-Aufruf, aber nicht
die Zeilen, die tatsächlich warfen (eine Messdatei ohne `ratio` riss das Tor mit einem
`KeyError` ab, statt es rot zu färben); `pruefen()` las von jeder Zeile nur `ratio` und
`resolvable` und ließ `oos_share`, `deflation_events`, `required_sharpe`,
`detectable_bps` und `needed_bps` ungeprüft; `min_events_for_resolution` warf an seiner
eigenen unteren Suchgrenze, statt `int | None` zu liefern, und sein Aufruf im Messlauf
lag außerhalb des `try` — ein Messlauf wäre dort nach der gedruckten Tabelle und **vor**
dem Schreiben von `config/aufloesung.json` abgebrochen; der Kopplungstest gegen
`bestaetige` lief auf einer Ereigniszahl, bei der Abschneiden und Runden zufällig
dasselbe ergeben, und konnte die Rundungsart, die er festnageln soll, nicht
unterscheiden (er läuft jetzt zweimal, einmal mit N ≡ 1 mod 3); und er hing über das
Repo-Register `TRIALS.jsonl` an einer Datei, die nicht versioniert ist — auf jedem
frischen Klon war er rot. Belegt: dieselben zwei Testdateien in einem `git worktree`
ohne `TRIALS.jsonl` gaben vorher „1 failed, 56 passed" (`TrialsLedgerError: Register …
fehlt`), nach der Reparatur laufen dort 70 Fälle grün durch.

An der Tabelle oben ändert das alles nichts: die sechs kippenden Zeilen und die sieben
verbleibenden auflösbaren stehen unverändert, und die neuen Untergrenzen greifen bei
keiner der 30 Kombinationen. `python tools/aufloesung.py --check` fällt gegen die
abgelegte Messdatei weiterhin rot, jetzt aber ohne grüne Zeile davor — und auch dann,
wenn jemand den Schlüssel nachträgt.

**Am Urteil ändert das nichts.** Alle sieben Studien sind schon an M6.1 gescheitert,
Abbruchbedingung 6 ist ausgelöst ([`05-URTEIL.md`](05-URTEIL.md)). Der Vorbehalt macht das
Ergebnis nicht schlechter, sondern die Begründung ehrlich: mindestens einer der sieben
Versuche lief auf eine Frage, die vorher als beantwortbar galt und es nie war.

---

## 1. Was §1 genähert hat und was gemessen wurde

§1 des Auftrags hat die Fensterstreuung als `ATR(H1) × √Fensterlänge` geschätzt. Gemessen
wird sie hier als Standardabweichung der Rendite über **nicht überlappende** Fenster der
tatsächlichen Reihe.

| Instrument | Fenster | genähert (bp) | gemessen (bp) | Abweichung |
|---|---|---:|---:|---:|
| EURUSD | 1h | 10,04 | 10,66 | +6 % |
| EURUSD | 4h | 20,08 | 23,69 | +18 % |
| EURUSD | 1d | 49,19 | 57,58 | +17 % |
| GBPJPY | 1h | 11,72 | 14,15 | **+21 %** |
| GBPJPY | 4h | 23,44 | 34,10 | **+45 %** |
| GBPJPY | 1d | 57,42 | 83,22 | **+45 %** |
| XAUUSD | 1h | 41,80 | 21,40 | **−49 %** |
| XAUUSD | 4h | 83,60 | 44,63 | **−47 %** |
| XAUUSD | 1d | 204,78 | 110,14 | **−46 %** |
| DE40 | 1h | 26,81 | 28,59 | +7 % |
| DE40 | 4h | 53,62 | 54,73 | +2 % |
| DE40 | 1d | 131,34 | 129,05 | −2 % |
| NVDA | 1h | 91,18 | 141,09 | **+55 %** |
| NVDA | 4h | 182,36 | 236,22 | **+30 %** |
| NVDA | 1d | 446,69 | 541,38 | **+21 %** |

**Warum die Näherung dort abweicht, wo sie um mehr als 20 % abweicht** — der Auftrag
verlangt für jeden solchen Fall eine Zeile:

- **XAUUSD, alle drei Fenster (−46 bis −49 %).** Die Näherung überschätzt am stärksten
  dort, wo der ATR am wenigsten über die Schluss-zu-Schluss-Bewegung sagt. Der ATR misst
  die **Spanne** einer Kerze, die Streuung misst die **Rendite** von Schluss zu Schluss.
  Gold läuft innerhalb einer Stunde weit und kehrt darin zurück; die Spanne ist groß, die
  Nettobewegung klein. Das ist keine Kleinigkeit: nur wegen dieses Unterschieds wird
  XAUUSD unten von „blind" auf „auflösbar" gedreht.
- **GBPJPY, alle drei Fenster (+21 bis +45 %).** Hier zeigt die Näherung in die andere
  Richtung. Der ATR wurde auf H1 gemessen; die Wurzelskalierung unterstellt, dass
  Stundenrenditen unkorreliert sind. Bei GBPJPY sind sie es nicht — der Yen trägt Trends
  über Stunden hinweg, Bewegungen setzen sich fort statt sich auszugleichen. Wo Renditen
  positiv korrelieren, wächst die Streuung **schneller** als mit √t, und die Näherung
  fällt zu niedrig aus.
- **NVDA, alle drei Fenster (+21 bis +55 %).** Dieselbe Ursache, andere Herkunft: eine
  Aktie handelt nicht rund um die Uhr. Über Nacht und übers Wochenende sammeln sich
  Nachrichten, die beim nächsten Auftakt in einer einzigen Bewegung stehen. Ein Fenster,
  das eine solche Lücke enthält, trägt eine Rendite, die keine Stundenkerze je gezeigt
  hat, und die √t-Skalierung kennt sie nicht. Auf dem 1h-Fenster ist die Abweichung mit
  +55 % am größten, weil die Stundenreihe bis 2003 zurückreicht und damit den Herbst 2008
  enthält — der ATR-Median aus §1 stammt aus einem viel kürzeren, ruhigeren Ausschnitt.

Die Näherung liegt also nicht zufällig daneben, sondern **systematisch in beide
Richtungen** — je nachdem, ob ein Instrument innerhalb der Kerze zurückkehrt (XAUUSD, zu
hoch geschätzt) oder über Kerzen hinweg trendet und springt (GBPJPY, NVDA, zu niedrig
geschätzt). Sie taugt zur Vorsortierung und nicht zur Entscheidung. Festgehalten in
`tests/test_resolution.py::test_wurzel_t_naeherung_ist_kein_ersatz_fuer_die_messung`.

EURUSD und DE40 sind die Fälle, in denen die Näherung nahe genug bleibt (−2 bis +18 %
bzw. −2 bis +7 %) — und ausgerechnet dort ändert sie am Urteil nichts.

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
| täglich, 1h | EURUSD | 252 | 4.060 | 0,60 | **0,17** | −72 % | auflösbar → auflösbar |
| täglich, 1h | GBPJPY | 252 | 4.060 | 0,42 | **0,13** | −68 % | auflösbar → auflösbar |
| monatlich, 4h | GBPJPY | 300 | 399 | 0,77 | **1,03** | +34 % | auflösbar → **blind** |
| monatlich, 4h | EURUSD | 300 | 331 | 1,10 | **1,32** | +20 % | blind → blind |

Zwei Zeilen kippen, in entgegengesetzte Richtungen:

- **XAUUSD/4h/täglich wird auflösbar** (1,36 → 0,78), allein wegen der überschätzten
  Streuung. §1 hatte XAUUSD als „knapp blind" geführt — zu Unrecht.
- **GBPJPY/4h/monatlich wird blind** (0,77 → 1,03). Das ist der Kandidat **K3
  (Monatsende-Fixing)**. Er fällt knapp, um 3 %, und die Schwelle ist die Schwelle. Im
  **1h-Fenster** löst dieselbe Frage jedoch auf (0,62) — dazu Abschnitt 4. Auch diese
  0,62 stehen unter dem Vorbehalt aus §0: gegen die Stichprobe, die die Deflation
  wirklich sieht, sind es 1,11, und K3 löst dann in keinem Fenster auf.

Die 1h-Zeilen weichen am stärksten ab (−68 bis −72 %), und das liegt nicht an der
Streuung, sondern an N: §1 rechnete mit 252 Ereignissen aus einem Jahr, tatsächlich
verfügbar sind gut sechzehn Jahre H1-Historie und damit 4.060.

**Die vollständige Messung: 13 von 30 Kombinationen sind auflösbar.** (Gegen die
Deflationsstichprobe sind es 7 von 30 — §0.)

| Instrument | Fenster | Frequenz | N | Streuung (bp) | K (bp) | 3×K (bp) | nachweisbar (bp) | Verhältnis |
|---|---|---|---:|---:|---:|---:|---:|---:|
| GBPJPY | 1h | täglich | 4.060 | 14,15 | 1,84 | 5,51 | 0,74 | **0,13** |
| EURUSD | 1h | täglich | 4.060 | 10,66 | 1,10 | 3,30 | 0,55 | **0,17** |
| GBPJPY | 4h | täglich | 8.398 | 34,10 | 1,84 | 5,51 | 1,23 | **0,22** |
| EURUSD | 4h | täglich | 6.959 | 23,69 | 1,10 | 3,30 | 0,94 | **0,28** |
| XAUUSD | 1h | täglich | 4.305 | 21,40 | 0,85 | 2,54 | 1,08 | **0,43** |
| NVDA | 1h | täglich | 5.777 | 141,09 | 4,19 | 12,56 | 6,15 | **0,49** |
| GBPJPY | 1d | täglich | 8.398 | 83,22 | 1,84 | 5,51 | 3,01 | **0,55** |
| DE40 | 1h | täglich | 3.535 | 28,59 | 0,87 | 2,62 | 1,59 | **0,61** |
| GBPJPY | 1h | monatlich | 193 | 14,15 | 1,84 | 5,51 | 3,43 | **0,62** |
| EURUSD | 1d | täglich | 6.959 | 57,58 | 1,10 | 3,30 | 2,29 | **0,69** |
| XAUUSD | 4h | täglich | 5.589 | 44,63 | 0,85 | 2,54 | 1,98 | **0,78** |
| EURUSD | 1h | monatlich | 193 | 10,66 | 1,10 | 3,30 | 2,58 | **0,78** |
| NVDA | 4h | täglich | 5.777 | 236,22 | 4,19 | 12,56 | 10,29 | **0,82** |

Die 17 übrigen Kombinationen sind blind. Drei Muster:

1. **Das 1h-Fenster löst überall auf**, an allen fünf Instrumenten, für tägliche
   Ereignisse (0,13 bis 0,61). Das kurze Fenster schlägt die größere Ereigniszahl des
   langen: 4.060 Ereignisse bei 10,66 bp Streuung sind besser als 6.959 bei 23,69 bp.
2. **Monatliche Fragen lösen nur im 1h-Fenster auf**, und nur bei EURUSD und GBPJPY
   (0,62 und 0,78). In jedem anderen Fenster und an jedem anderen Instrument sind sie
   blind (1,03 bis 12,83). Festgehalten in
   `tests/test_resolution.py::test_monatliche_kandidaten_loesen_nur_im_stundenfenster_auf`.
3. **Das Tagesfenster ist der schlechteste Schnitt** — es löst nur bei EURUSD und GBPJPY
   auf, wo die Historie am tiefsten reicht, und auch dort nur knapp.

---

## 3. Fünf eigene Fehler in diesem Schritt

Alle fünf sind beim Nachrechnen der jeweils vorigen Fassung aufgefallen; vier von ihnen
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

**Fehler 5 — die Grenze war die der Abfrage, nicht die der Historie.** Nach Fehler 3 stand
der H1-Abruf auf elf Jahren, weil zwölf Jahre zweimal leer zurückkamen. Auch das war zu
kurz gegriffen, und es fiel nur auf, weil **alle fünf** Instrumente ihre H1-Reihe auf den
Tag genau an meiner Abfragegrenze begannen — dasselbe Muster wie in Fehler 3. Die Probe,
die es klärte, fragte ein *kleines* Fenster *tief* in der Vergangenheit ab: der Abruf
2013–2016 liefert 18.505 Stundenkerzen, der Abruf 2005–2006 klemmt auf den 07.07.2010.
Es gibt also H1-Historie weit vor der Elfjahresgrenze; nur **eine einzelne Abfrage** über
mehr als rund 70.000 Kerzen kommt leer zurück — und zwar leer, nicht als Fehler. Behoben,
indem `_hole()` die Reihe in Fünfjahresscheiben holt und zusammensetzt: H1 reicht damit
16,1 statt 11,0 Jahre, N für die täglichen 1h-Kandidaten steigt von 2.769 auf 4.060, für
K3 von 131 auf 193.

Dabei wurde die **echte** Grenze sichtbar: EURUSD, GBPJPY und XAUUSD liefern auf H1 alle
exakt 99.998 Kerzen, bei drei verschiedenen Anfangsdaten. DE40 (60.450) und NVDA (40.566)
liegen darunter und sind vollständig. Das ist keine Eigenschaft des Brokers, sondern die
Obergrenze des Terminals selbst („Max bars in chart", Vorgabe 100.000). Sie ist eine
Einstellung und kein Naturgesetz — wer sie anhebt, bekommt tiefere Stundenhistorie. Das
steht in [`02-DATENLAGE.md`](02-DATENLAGE.md) als offener Punkt für den Betreiber.

Die Lehre aus Fehler 2 ist dieselbe wie beim NVDA-Kommissionsfehler aus Paket 2
([`../ABSCHLUSS/09-EIGENE-FEHLER.md`](../ABSCHLUSS/09-EIGENE-FEHLER.md)): eine zweite
Umsetzung derselben Rechnung ist keine Bequemlichkeit, sondern eine zweite Fehlerquelle.
Die Lehre aus 3, 4 und 5 ist neu und unbequemer: **eine Grenze, die man selbst gesetzt
hat, sieht in der Ausgabe genauso aus wie eine Grenze der Daten.** Dreimal stand in der
Tabelle eine glatte Zahl — „2,0 Jahre", „25,0 Jahre", „11,0 Jahre" —, und dreimal war sie
mein Echo, nicht die Antwort des Terminals. Was schließlich half, war kein besserer Blick
auf die Zahl, sondern eine Probe, die **gegen** die eigene Annahme gebaut war: nicht „geht
mehr?", sondern „was liegt an einer Stelle, an der nach meiner Annahme nichts liegen
darf?".

---

## 4. Was das für das Kandidatenfeld heißt

§5 legt Kandidaten über Ereignisart, Zeitpunkt und Instrument fest, **nicht über die
Fensterlänge**. Die Fensterlänge ist damit Teil des Studienaufbaus. Regel, hier
festgeschrieben, bevor eine Wirkung gemessen wird: **je Kandidat wird das Fenster mit dem
niedrigsten Verhältnis genommen.** Das ist keine Auswahl auf das Ergebnis — die
Auflösungsrechnung kennt nur N, Streuung und K und weiß nichts über den gesuchten Effekt.

| Kandidat | Ereignis | Instrument | Fenster | Verhältnis | Stand |
|---|---|---|---|---:|---|
| K1 | London-Fixing 16:00 | EURUSD | 1h | 0,17 | **bleibt** |
| K1 | London-Fixing 16:00 | GBPJPY | 1h | 0,13 | **bleibt** |
| K2 | Tokioter TTM 09:55 JST | GBPJPY | 1h | 0,13 | **bleibt** |
| K3 | Monatsende-Fixing | GBPJPY | **1h** | 0,62 | **bleibt, Fenster geändert** |
| K4 | Täglicher Rollover | EURUSD | 1h | 0,17 | **bleibt** |
| K4 | Täglicher Rollover | GBPJPY | 1h | 0,13 | **bleibt** |
| K5 | NASDAQ-Schlussauktion | NVDA | 1h | 0,49 | **bleibt** |

**Alle fünf Kandidaten bleiben, das Feld behält seine 7 Versuche von 12.** K3 wechselt vom
4h- ins 1h-Fenster: im 4h-Fenster ist die Frage blind (1,03), im 1h-Fenster auflösbar
(0,62). K3 ist damit der knappste Kandidat im Feld und der einzige, der auf nur 193
Ereignissen steht — gut sechzehn Jahre H1-Historie mal zwölf Monatsenden. Fällt in der Datenlage
etwas an der H1-Reihe aus, fällt K3 zuerst.

**Genau dieser Zuschnitt trägt nicht.** Nach dem Vorbehalt aus §0 lautet K3s Verhältnis im
1h-Fenster 1,11 statt 0,62; blind ist er dort ebenso wie im 4h- und im Tagesfenster. Die
Regel „je Kandidat das Fenster mit dem niedrigsten Verhältnis" bleibt richtig, nur führt
sie für K3 zu keinem Fenster mehr — er hätte nach M6.0 vor der Messung ausgesondert
gehört. Die übrigen sechs Zeilen dieser Tabelle bleiben auch gegen die
Deflationsstichprobe auflösbar (0,23 bis 0,85) — für K5 allerdings nur, solange man die
geplante Ereigniszahl einsetzt; mit den 472 tatsächlich messbaren Ereignissen aus Fehler 6
sind es 3,02.

**Zu XAUUSD und DE40:** §5 hält die fünf Reserveversuche ausdrücklich für den Fall bereit,
„falls die gemessene Streuung aus A1 sie doch auflösbar macht". Genau das ist eingetreten
— XAUUSD löst im 1h-Fenster mit 0,43 auf, DE40 mit 0,61. Ein Nachrücken wäre also
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
