# Ereignisstudie (A3)

Sieben Studien, sieben verbrauchte Versuche von zwölf. Rohausgabe in
[`07-AUSGABEN/ereignisstudie.txt`](07-AUSGABEN/ereignisstudie.txt), Register in
[`07-AUSGABEN/trials.jsonl`](07-AUSGABEN/trials.jsonl) — dem eingefrorenen Abzug des
nicht versionierten `TRIALS.jsonl` —, Code in `mt5_trading_ai/backtest/ereignisstudie.py`
und `tools/ereignisstudie.py`.

**Ergebnis in einem Satz: keine der sieben Studien besteht M6.1, keine besteht auch nur
eine der drei Prüfungen aus M6.2.**

---

## 1. Die Hypothese, vorab festgelegt

Alle fünf Kandidaten sind Zwangslagen: eine benannte Gruppe muss zu einem benannten
Zeitpunkt handeln. Die Mikrostruktur sagt dazu **Preisdruck und Umkehr** voraus — der
erzwungene Handel drückt den Kurs, und wer dagegenhält, wird mit der Rückkehr bezahlt.

    Vorzeichen(e) = −sign(Rendite der Stunde VOR dem Ereignis)

**Warum kein festes Vorzeichen.** Ob am Londoner Fixing per Saldo Euro gekauft oder
verkauft werden müssen, hängt an der Auftragslage des Tages; ob der Rollover den Halter
belastet oder entlastet, hängt am Zinsunterschied, und der hat in sechzehn Jahren mehrfach
das Vorzeichen gewechselt. Ein festes `+1` wäre ein Münzwurf mit Begründungstext davor.
Das bedingte Vorzeichen benutzt ausschließlich Information **vor** dem Fenster: die
Vorstunde ist abgeschlossen, bevor die Fensterstunde beginnt.

**Was „handelbar" heißt.** Das Fenster beginnt am ersten Kerzenanfang *ab* dem Ereignis,
nie davor, und die Rendite läuft von der **Eröffnung** dieser Kerze bis zu ihrem Schluss.
Wer stattdessen den vorigen Schluss nimmt, verdient am Sprung über die Kerzengrenze mit —
an einem Kurs, den es zum Einstiegszeitpunkt nicht mehr gab.

Hypothese, Fenster und Vorzeichenregel standen vor der ersten Messung fest. Eine
nachträgliche Änderung wäre eine zweite Hypothese und ein zweiter Versuch (M7).

---

## 2. Die Ergebnisse

| Kandidat | Instr. | gemessen / geplant | Brutto (Median) | 25 % / 75 % | Treffer | K | **Netto** |
|---|---|---:|---:|---|---:|---:|---:|
| K1 London-Fixing | EURUSD | 4.164 / 4.204 | +0,53 bp | −13,4 / +14,6 | 52,4 % | 1,10 | **−0,57 bp** |
| K1 London-Fixing | GBPJPY | 4.174 / 4.205 | +0,55 bp | −18,8 / +20,3 | 52,4 % | 1,84 | **−1,28 bp** |
| K2 Tokioter TTM | GBPJPY | 4.158 / 4.205 | +0,14 bp | −16,1 / +16,4 | 50,6 % | 1,84 | **−1,70 bp** |
| K3 Monatsende | GBPJPY | 192 / 193 | +1,36 bp | −19,4 / +23,0 | 57,3 % | 1,84 | **−0,48 bp** |
| K4 Rollover | EURUSD | 3.285 / 4.204 | +0,36 bp | −6,7 / +7,5 | 55,1 % | 1,10 | **−0,74 bp** |
| K4 Rollover | GBPJPY | 3.307 / 4.205 | +0,74 bp | −9,7 / +11,3 | 56,0 % | 1,84 | **−1,09 bp** |
| K5 NASDAQ-Schluss | NVDA | **472 / 5.983** | +0,00 bp | — | 36,0 % | 4,19 | **−4,19 bp** |

**Jeder Nettoeffekt ist negativ.** Der größte Bruttoeffekt im Feld sind 1,36 bp (K3) gegen
eine M6.1-Schwelle von 5,51 bp — ein Viertel dessen, was nötig wäre. Der Trefferanteil
liegt zwischen 50,6 % und 57,3 %; bei einem tragenden Effekt müsste er deutlich darüber
liegen. Die Streuung ist in jedem Fall zehn- bis zwanzigmal so groß wie der Median.

### M6.1 und M6.2 je Studie

| Kandidat | Instr. | M6.1 (Brutto ≥ 3×K) | Deflation (DSR ≥ 0,95) | Stabilität (beide Hälften ≥ 1,5×K) | Randomisierung (≤ 5 %) |
|---|---|---|---|---|---|
| K1 | EURUSD | 0,53 < 3,30 ✗ | 0,154 ✗ | +0,86 / +0,28 ✗ | 27,6 % ✗ |
| K1 | GBPJPY | 0,55 < 5,51 ✗ | 0,407 ✗ | +0,53 / +0,57 ✗ | 31,2 % ✗ |
| K2 | GBPJPY | 0,14 < 5,51 ✗ | 0,168 ✗ | −0,16 / +0,41 ✗ | 58,3 % ✗ |
| K3 | GBPJPY | 1,36 < 5,51 ✗ | 0,180 ✗ | +0,10 / +2,52 ✗ | 22,5 % ✗ |
| K4 | EURUSD | 0,36 < 3,30 ✗ | 0,418 ✗ | +0,36 / +0,37 ✗ | 38,0 % ✗ |
| K4 | GBPJPY | 0,74 < 5,51 ✗ | 0,686 ✗ | +0,73 / +0,74 ✗ | 14,0 % ✗ |
| K5 | NVDA | 0,00 < 12,56 ✗ | 0,025 ✗ | 0,00 / −0,00 ✗ | 100,0 % ✗ |

**Die Randomisierungsspalte ist die aufschlussreichste.** Von 1.000 zufällig um ganze Tage
verschobenen Ereignismengen erreichen 14 % bis 100 % denselben Median wie die echten
Ereignisse. Anders gesagt: was gemessen wurde, ist an den Ereigniszeitpunkten **nicht
besonders**. Es ist die allgemeine Eigenschaft der Stundenrendite, dass sie nach einer
Bewegung leicht zurückkehrt — an einem beliebigen Dienstag um 11 Uhr genauso wie am
Londoner Fixing.

Damit fällt auch die naheliegende Ausrede weg, die Effekte seien „klein aber echt". Sie
sind klein, und sie sind nicht an das Ereignis gebunden.

---

## 3. K5 war nicht messbar — und hätte nicht laufen dürfen

Von 5.983 geplanten Ereignissen ließen sich **472** messen, knapp 8 %. Der Grund ist
strukturell und hätte vor dem Lauf auffallen müssen:

NVDA handelt von 09:30 bis 16:00 New Yorker Zeit. Im Jahr 2024 hat die Reihe 252
Stundenkerzen um 15:00 NY und **19** um 16:00 — danach keine. **Nach der Schlussauktion
gibt es am selben Tag keine handelbare Stunde.** Die nächste Kerze kommt am Folgetag um
09:30 und liegt außerhalb der Zwei-Stunden-Grenze, die ein Ereignis als „messbar" gelten
lässt.

Die 472 gemessenen Ereignisse sind fast genau die Tage der Sommerzeitlücke — jener zwei
bis drei Wochen im Jahr, in denen die amerikanische und die europäische Umstellung
auseinanderliegen und die Sitzung deshalb um eine Serverstunde verschoben liegt. Das ist
keine Stichprobe der Fragestellung, das ist ein Rest.

**Der Fehler liegt in A1, nicht in A3.** Die Auflösungsrechnung setzte für K5 die
**geplante** Ereigniszahl ein (5.777) statt der **messbaren** (472):

| Ereigniszahl | nachweisbarer Effekt | nötig (3×K) | Verhältnis | Urteil |
|---|---:|---:|---:|---|
| geplant, 5.777 | 4,85 bp | 12,57 bp | 0,39 | auflösbar |
| messbar, 472 | 17,09 bp | 12,57 bp | **1,36** | **blind** |

Mit der richtigen Zahl wäre K5 **vor** der Messung ausgesondert worden — kostenfrei, wie
M6.0 es vorsieht. So hat er einen Versuch verbraucht. Er zählt trotzdem: das Register ist
anhängend, und ein Versuch, der aus meinem Fehler entstand, wird nicht stillschweigend
gestrichen. Nötig wären 867 messbare Ereignisse gewesen.

**Die Lehre:** M6.0 muss gegen die Zahl der Ereignisse laufen, für die es **Kurse im
Fenster** gibt, nicht gegen die Zahl der Kalendereinträge. Für die sechs übrigen Studien
macht das keinen Unterschied — dort wurden 78 % bis 99,5 % der geplanten Ereignisse
gemessen. Bei K5 ist es der Faktor 12.

---

## 4. Was gegen den eigenen Irrtum geprüft wurde

`tools/ereignisstudie.py --selbsttest` rechnet gegen eine synthetische Reihe mit bekanntem
Umkehreffekt von 12 bp und findet **12,00 bp** bei 100 % Trefferanteil — Betrag und
Vorzeichen also richtig. Dazu eine Gegenprobe auf derselben Reihe mit um drei Stunden
versetzten Fenstern: dort findet die Studie **−1,63 bp**, praktisch nichts. Ohne diese
Gegenprobe bestünde der Selbsttest auch dann, wenn das Werkzeug einfach immer 12 bp
meldete.

Der Selbsttest registriert **keinen** Versuch und ist die einzige Betriebsart, die im
Prüfstand läuft. Liefe dort die echte Studie, schriebe jeder CI-Lauf einen Versuch ins
anhängende Register und triebe die Deflationshürde mit der Zahl der CI-Läufe nach oben.

---

## 5. Zur Registrierung „vor dem Lauf"

Der Auftrag verlangt die Eintragung in `gates/trials.py` vor der Messung. Das Register
kennt aber nur abgeschlossene Zustände und ist anhängend — ein Eintrag „läuft gerade", der
später berichtigt wird, ist darin nicht vorgesehen. Umgesetzt ist deshalb die Substanz der
Regel: alles, was den Versuch ausmacht — Hypothese, Fenster, Vorzeichenregel, Instrument,
Zeitraum, `data_checksum`, `code_commit` — wird vor der Messung festgezurrt und ausgegeben;
der Eintrag folgt unmittelbar danach und **in jedem Ausgang**, auch bei Abbruch. Was die
Regel verhindern soll, ist damit verhindert: es gibt keinen Weg, erst zu messen und dann
zu entscheiden, ob der Versuch zählt.

Sieben Einträge stehen im Register, alle mit `outcome = completed`, jeder mit der
SHA-256-Prüfsumme der Stundenreihe aus A1.2 und dem Commit-Stand des Codes.

**Versuchsstand: 7 von 12 verbraucht, 5 verbleibend.**
