# Stufe 8 — Testwirkung statt Testdeckung

*Gefahren in der Nacht vom 2026-08-19 auf den 2026-08-20 auf Anweisung des
Auftraggebers („stufe 8"). Belege in [`belege/`](belege/), sechs Dateien. Bestätigt durch
Ausführung — jede Ausgabe liegt bei.*

---

## 0. Zur Zulässigkeit — unverändert die Entscheidung des Auftraggebers

Es gilt weiter, was in [Stufe 4](../04-risikokern/bericht.md) §0 steht: §1 schließt die
Stufen 4–10 für den Ausgang (B) aus, der Auftraggeber hat sie angewiesen (E-009).
**Diese Stufe misst keinen Vorteil und behauptet keinen.**

---

## 1. Was gemessen wurde

Beleg [`01-messung-vorher.txt`](belege/01-messung-vorher.txt), gegen einen eigenen
Arbeitsbaum auf Commit `610e4eb`.

| # | Forderung | vorher |
|---|---|---|
| A1 | Mutationstor mit Tötungsrate als blockierender Schwelle | **fehlte ganz** |
| A2 | Importpfad vom Diensteinstiegspunkt für jede Datei des Sicherheitsverzeichnisses | **20 von 21** |
| A3 | Negativtests für jeden Prüfer | **ungeprüft** |
| A4 | Deckung von Zeilen auf Zweige je Datei | **nicht konfiguriert** |

**A1.** Keine Mutationsprüfung im Repo, keine Abhängigkeit (`mutmut`, `cosmic_ray`,
`mutpy` alle nicht installiert). Die Proben der Stufen 4 bis 7 liefen **von Hand, je
einmal**. Das war richtig und reicht nicht: eine Probe, die nur läuft, wenn ich daran
denke, ist keine Sperre.

**A2.** `gates/learning_phase.py` war von **keinem** der 24 Diensteinstiegspunkte aus
erreichbar — ein Modul mit vier ausformulierten Grenzen, grünen Eigentests und **null**
Aufrufern im Ausführungspfad. Genau die Krankheit, die §0 des Auftrags benennt.

**A4.** `coverage` war installiert, aber weder `branch` noch eine Schwelle konfiguriert.
Gemessen ergab sich:

| | Zeilen | Zweige |
|---|---:|---:|
| Paket gesamt | 92,8 % | **86,9 %** |
| schwächste Datei (`execution/schwebende_auftraege.py`) | 79,9 % | **67,9 %** |

Die schwächste Datei ist die Akte der ungeklärten Aufträge aus Stufe 5 — **meine eigene**.
Was dort fehlte, waren genau die fail-closed-Zweige: unlesbare Datei, defektes JSON,
unvollständiger Eintrag. Also die Zweige, wegen derer das Modul existiert.

---

## 2. Was geändert wurde

### 2.1 `tools/mutationstor.py` — das Mutationstor

**16 Sonden**, von Hand geschrieben, nicht erzeugt. Jede ist ein echter Rückfall: eine
Vergleichsrichtung umgedreht, eine Grenze verschoben, eine Sperre übersprungen. Ein
Zufallsmutator hätte den umgekehrten Fehler — er erzeugt viel Belangloses (Docstrings,
Protokolltexte), und eine Tötungsrate über Belanglosem misst nichts.

Der Katalog deckt die Befunde aller bisherigen Stufen ab: Reduce-only-Sperre,
Kontoprüfung, schwebender Auftrag, Schwebeakte-Persistenz, Auflösung ohne Befund,
Überlappungsgewichtung, Mindestmenge, Schemahash, Erkundungs-Positivliste,
Echtgeld-Sperre, inverse Gewichtung, Kostenprämisse, Stop-Kostenboden,
Margen-Obergrenze, geschlossene Kerze, Journal-Zeitstempel.

**Die Schwelle ist 1,0**, und das ist eine Entscheidung: der Katalog ist handverlesen,
jeder Eintrag ein echter Defekt. Eine Rate von 0,9 hieße, dass einer davon unbemerkt
durchginge — und welcher, wäre Zufall.

**Gefahren:** `Toetungsrate: 1.000 (16/16)`
([`03-mutationstor.txt`](belege/03-mutationstor.txt)).

### 2.2 `tools/zweigdeckung.py` — Zweige statt Zeilen, je Datei

Eine Zeilendeckung von 95 % kann bedeuten, dass jede `if`-Bedingung genau einmal
gelaufen ist — immer in dieselbe Richtung. Der Sinn einer Sperre liegt aber im
**anderen** Zweig, dem ablehnenden.

**Je Datei, nicht als Gesamtzahl.** Eine Gesamtdeckung von 87 % kann eine Datei mit 99 %
und eine mit 40 % bedeuten, und die mit 40 % ist die interessante.

Schwelle **80 % je Datei**, gesetzt **vor** dem Aufräumen der schwächsten Datei — nicht
danach auf den vorgefundenen Wert. Nach den neuen fail-closed-Fällen:

| Datei | Zeilen | Zweige |
|---|---:|---:|
| `execution/schwebende_auftraege.py` | 93,3 % | **92,9 %** *(vorher 67,9 %)* |
| `venue/mt5.py` | 87,6 % | 80,0 % |
| `costs/model.py` | 92,6 % | 83,3 % |
| `risk/leverage.py` | 90,5 % | 83,3 % |
| `gates/herausforderer.py` | 91,9 % | 85,7 % |
| übrige sieben | ≥ 87,5 % | ≥ 87,5 % |
| **Paket gesamt** | **93,1 %** | **87,3 %** |

### 2.3 `gates/learning_phase.py` verdrahtet

Der Trainingslauf ranglistet jetzt, was er gesehen hat, bevor er vorschlägt — über
`rank_strategies`. Das ist ein **substantieller** Aufruf, kein Feigenblatt: ein
Trainingslauf, der aus Trades Parameter ableitet, sollte wissen, wie diese Trades
gelaufen sind.

Der Unterschied zu `evaluate_llm_gate` (Stufe 6, §8) ist benennbar und bleibt bestehen:
jenes Tor bewacht etwas, das es nicht gibt — ein LLM im Entscheidungspfad. Ein Aufrufpunkt
dafür wäre erfunden. `rank_strategies` dagegen hat einen echten Gegenstand.

**Ehrlich dazugesagt:** Das Journal führt keine Ergebnisspalte in R, also gehen die Zeilen
mit `net_pnl_r = 0.0` in die Rangliste. Die ausgewiesene Zahl steht damit für die
**Handelsfrequenz**, nicht für einen Ertrag — und genau so steht es im Code und in der
Ausgabe.

### 2.4 Die fehlenden fail-closed-Zweige

Elf neue Fälle für `execution/schwebende_auftraege.py`: leere Akte, kein Objekt, fehlende
Eintragsliste, Eintrag ohne Kennung, unvollständiger Eintrag (zählt trotzdem), unlesbare
Zeit (zählt trotzdem), unlesbarer Pfad, doppelter Vermerk, Auflösung einer unbekannten
Kennung.

---

## 3. Abnahme

**Die verlangten zwei Sätze, wörtlich geprüft:**

> „die Mutationssonden färben den Lauf rot"

`test_das_mutationstor_laeuft_und_toetet_jede_sonde` fährt das Werkzeug als Unterprozess
und verlangt `Toetungsrate: 1.000`. Überlebt eine Sonde, ist der Lauf rot.

> „keine Testdatei prüft mehr eine Funktion ohne Produktionsaufrufer"

`test_jede_datei_des_sicherheitsverzeichnisses_ist_vom_einstiegspunkt_erreichbar` — **21
von 21** erreichbar, gegen 20 von 21 vor der Stufe.

**`tests/test_stufe8_testwirkung.py`, 34 Fälle**, Beleg
[`05-abnahme.txt`](belege/05-abnahme.txt). Darunter drei, die die Prüfungen selbst
prüfen:

- **jede Sonde findet ihren Anker im heutigen Code** — der Fall, der eine verrottende
  Sonde fängt (siehe §4),
- **keine Sonde mutiert das Mutationstor selbst**,
- **der Katalog trifft die kritischen Dateien** und nicht nur die bequemen.

**Negativtests für jeden Prüfer (A3):** sieben Prüfer, jeder mit einem Testfall, der von
ihm einen **Fehlschlag** erwartet. Ein Prüfer, der nur grün gefahren wird, belegt nicht,
dass er je ablehnt.

**Torlauf** ([`06-torlauf.txt`](belege/06-torlauf.txt)): **neun** Tore je **Exit 0** —
neu darunter das Mutationstor und die Zweigdeckung. `pytest` **1.550 bestanden, 0
fehlgeschlagen**.

---

## 4. Was schiefging

**Beim ersten Lauf fanden vier von sechzehn Sonden ihren Anker nicht.** Ursache: dieses
Repo läuft mit `core.autocrlf=true`, die Dateien liegen unter Windows als CRLF auf der
Platte, und der Katalog ist in LF geschrieben.

**Der Fall ist lehrreich, weil er beinahe still geblieben wäre.** Hätte ich das Werkzeug
so gebaut, dass eine nicht anwendbare Mutation als „getötet" zählt — die naheliegende
Abkürzung, denn der Testlauf ist ja grün —, dann hätte es `Toetungsrate: 1.000` gemeldet
und vier Sonden hätten nichts geprüft. Es meldet stattdessen `ANKER FEHLT`, und die Rate
fiel auf 0,750.

Das ist dieselbe Fehlerklasse wie F-005 (eine Zeichenkette gesucht, wo eine Sache gemeint
war) und wie die „Prüfung, die ihren Gegenstand nicht findet und deshalb besteht", gegen
die dieses Repo an mehreren Stellen gebaut ist. Ein Dauertor hält es jetzt fest.

---

## 5. Was diese Stufe ausdrücklich nicht behauptet

**Sechzehn Sonden sind keine Mutationsabdeckung.** Ein vollständiger Mutator erzeugt
Tausende Varianten; dieser Katalog ist eine Auswahl von Defekten, die in diesem Vorhaben
**tatsächlich vorkamen oder vorkommen könnten**. Er misst, ob die Testsuite gegen die
bekannten Rückfälle wirkt — nicht, ob sie gegen alle denkbaren wirkt.

**Die Schwellen sind gesetzt, nicht hergeleitet.** Tötungsrate 1,0 und Zweigdeckung 80 %
sind Wahlen; sie stehen als benannte Konstanten im Code, damit das sichtbar bleibt.

**Die Zweigdeckung sagt nichts über die Güte einer Zusicherung.** Ein Zweig kann
durchlaufen werden, ohne dass irgendetwas geprüft wird. Genau deshalb steht das
Mutationstor daneben: es misst Wirkung, wo die Deckung nur Berührung misst.

**`evaluate_llm_gate` bleibt ohne Aufrufer** — der offene Punkt aus Stufe 6, §8, ist von
dieser Stufe nicht berührt. Er steht in `gates/` und damit im Sicherheitsverzeichnis; die
Erreichbarkeitsprüfung findet ihn trotzdem, weil `backtest/llm_compare.py` nicht in den
drei geprüften Teilpaketen liegt. Das ist eine bewusste Grenze der Prüfung und keine
Lücke, die ich übersehen hätte — sie steht hier, damit niemand sie später für eine hält.
