# Gelöscht und stehengelassen

*Was entfernt wurde und warum. Und — für Stufe 0 wichtiger — was stehenbleibt, ohne
gepflegt zu werden.*

---

## In Stufe 0 gelöscht

**Nichts.** Stufe 0 ist eine Bestandsaufnahme. Sie bewegt keinen Code.

Das ist ausdrücklich festgehalten, weil Sperre V1 („Kein Code ohne Wirkung") beim Abschluss
jeder Stufe greift: In Stufe 0 ist kein neuer Code entstanden, für den ein Importpfad
nachzuweisen wäre. Entstanden sind ausschließlich Dokumente unter `AUFTRAG/`.

---

## Stehengelassen, nicht gepflegt

Nach §2.4 des Auftrags: *„Der aufgegebene Stand wird nicht gepflegt, nicht mitgeschleppt
und nicht ‚für später' behalten."*

### 1. `C:\Users\Acer\OneDrive\Documents\Cursor1\bitget-btc-ai`

**Umfang:** 101.323 Zeilen Produktions-Python in 15 Diensten, rund 100.000 Zeilen
TypeScript, 93 SQL-Migrationen, 121 Commits.

**Warum aufgegeben.** Der Handelsplatz wird im Wirtschaftsraum des Auftraggebers nicht
betrieben — nach §9.2 des Auftrags eine harte Grenze, die kein Umbau aufhebt. Dazu:
gemessen kein Simulator mit Kostenmodell (0 Treffer für `fee|slippage|funding|commission|spread`
in `runner_replay.py`).

**Wird nicht gelöscht, weil:** dort liegen Zugangsdaten im Klartext, deren Widerruf nur der
Auftraggeber veranlassen kann (→ `haltepunkte.md`, H-003). Ein Verzeichnis zu löschen,
bevor die darin liegenden Schlüssel widerrufen sind, beseitigt die Kopie und nicht die
Gültigkeit — es macht die Lage unübersichtlicher, nicht sicherer. Die Löschung ist nach
H-003 fällig, nicht davor.

**Was daraus nicht übernommen wird und warum nicht:**

| Baustein | Warum er nicht mitkommt |
|---|---|
| 15 Dienste, Ereignisbus, Datenmodell | Der gewählte Stand ist bewusst ein einzelnes Paket ohne Dienst, Server, Container und Datenbank. Ein Dienstschnitt für ein System, das nie gehandelt hat, ist Aufwand ohne Wirkung. |
| Dashboard (~100.000 Zeilen TypeScript) | §8 des Auftrags: „Keine zusätzliche Oberflächenfläche." Der gewählte Stand hat eine nur lesende Oberfläche aus der Standardbibliothek (`tools/oberflaeche.py`). |
| Bitget-REST/WS-Anbindung (445 Dateien mit `bitget`) | Handelsplatz nicht erreichbar. §8: „Keine weiteren Broker-Adapter." |
| Signal-Engine mit sechs Scoring-Schichten | Die Gewichte sind gesetzt, nicht hergeleitet (0,22/0,20/0,22/0,10/0,18/0,08). Übernahme hieße, mehrere hundert freie Parameter zu importieren, für die kein Vorteilsnachweis existiert. §8: „Keine weiteren Entscheidungsschichten." |

### 2. `C:\Users\Acer\OneDrive\Documents\Cursor1\strategy-validation`

**Umfang:** 871 Zeilen eigener Code, 3.577 Zeilen vendoriert, 10 Commits.

**Warum aufgegeben.** Die eingefrorene Vorregistrierung prüft den Composite-Score des
verworfenen Standes auf Krypto-Daten von Binance. Beides — Score und Anlageklasse — handelt
der gewählte Stand nicht. Die Maschine, für die die Vorregistrierung geschrieben wurde,
existiert gemessen nicht (0 Simulator-Definitionen, 0 Ergebnisartefakte).

**Wird nicht gelöscht, weil:** es ist ein eigenes Git-Repository mit einer Datei, die
ausdrücklich als unveränderlich gekennzeichnet ist (`PREREGISTRATION.md`, „Status:
eingefroren"). Eine eingefrorene Vorregistrierung zu löschen, deren Lauf nie stattfand, ist
das Gegenteil dessen, wozu sie da ist: sie belegt, was **vorher** gedacht wurde. Sie bleibt
als Beleg liegen, nicht als Arbeitsstand.

**Was daraus nicht übernommen wird:** die neun Kriterien K1–K9. Nicht, weil sie schlecht
wären — sie sind der methodisch beste Teil aller drei Stände —, sondern weil der gewählte
Stand bereits eine gleichwertige, an den Simulator verdrahtete Fassung trägt
(`gates/criteria.py`, `ABBRUCH.md` §2 mit 60 vorregistrierten Versuchen). Zwei
Vorregistrierungen für dieselbe Frage wären der Fehler, den Sperre V6 verbietet.

### 3. Ohne Prüfung stehengelassen

| Pfad | Warum keine Messung |
|---|---|
| `Cursor1/HelioswarmTrading-Ai` | 25 Dateien, kein `.git` — keine tragende Substanz |
| `Cursor1/Ki Trading` | 0 Dateien |
| `bitget-btc-ai.zip`, `bitget-btc-ai.7z` (~1,4 GB) | Archive des verworfenen Standes. **Nicht geöffnet.** Sie enthalten nach Lage der Dinge dieselben Zugangsdaten wie das Arbeitsverzeichnis; das Öffnen zum Zweck der Ausgabe wäre ein Verstoß gegen V7. Sie gehören zu H-003. |

---

## In Stufe 1 gelöscht

**Nichts.** Stufe 1 hat beschafft, nicht entfernt. Die 15 vom Handelsplatz stammenden
Reihen-Manifeste unter `config/reihen/` bleiben ausdrücklich liegen, obwohl sie für
diesen Auftrag unbrauchbar sind: sie sind der Beleg dessen, was am 2026-08-17 gemessen
wurde, und dieselbe `checksum` steht als `data_checksum` in sieben Einträgen von
`TRIALS.jsonl`. Sie zu löschen hieße, die Herkunft von sieben gezählten Versuchen zu
kappen.

## In Stufe 2 gelöscht

**Nichts.** Stufe 2 hat eine Regel gebündelt, die es an einer Stelle gab und an fünf
fehlte — und dabei nur Code hinzugefügt und Aufrufe umgehängt.

## In Stufe 3 gelöscht

**`pruefe_sharpe_je_beobachtung` samt der Konstante `MAX_PLAUSIBLE_SHARPE_JE_BEOBACHTUNG`
in `gates/criteria.py`** — von mir gebaut und im selben Lauf wieder entfernt.

Grund: die Sperre brach 18 bestehende Testfälle, weil die synthetischen Prüfreihen des
Standes fast keine Streuung haben und Sharpes von 23,98 bis 3,06 × 10¹³ erzeugen — ein
Streuungsartefakt, kein Einheitenfehler. Nach der Rücknahme hatte der Helfer keinen
Aufrufer im Ausführungspfad mehr, und V1 verlangt dann die Löschung: „Neuer oder
geänderter Code, für den du beim Abschluss der Stufe keinen Importpfad von einem
Diensteinstiegspunkt bis zur Funktion nachweisen kannst, wird vor dem Abschluss
gelöscht." Ein Helfer, der nur noch in Tests lebt, ist genau das.

Vollständige Ursachenanalyse: `fehler.md`, F-007. Was an seiner Stelle geblieben ist —
die Feldwahl per Syntaxbaum festgenagelt — steht in `stufen/03-simulator/bericht.md` §1.3.

## Was nach dem Ergebnistor **nicht** gelöscht wurde, obwohl es naheläge

Befund (B) heißt nach §1: *„Es wird zurückgebaut oder aufgegeben."* Beides ist eine
Entscheidung des Auftraggebers (H-004), und beide Wege sind noch offen. **Ich habe
deshalb nichts entfernt** — 58 % des Pakets (8.889 von 15.440 Zeilen) sind
Handelsstrecke und stünden bei Option 2 zur Disposition, aber ein Rückbau, der die Wahl
vorwegnimmt, wäre keine Ausführung des Vertrags, sondern ihre Umgehung.

Was an jeder der drei Optionen hängt, ist beziffert in
[`rueckbau-bestandsaufnahme.md`](rueckbau-bestandsaufnahme.md).
