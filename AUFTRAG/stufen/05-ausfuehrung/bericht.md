# Stufe 5 — Ausführungserfahrung erzeugen

*Gefahren am 2026-08-19 auf Anweisung des Auftraggebers („weiter mit stufe 5"). Belege
in [`belege/`](belege/), sechs Dateien. Bestätigt durch Ausführung — jede Ausgabe liegt
bei.*

---

## 0. Zur Zulässigkeit — unverändert die Entscheidung des Auftraggebers

Es gilt weiter, was in [Stufe 4](../04-risikokern/bericht.md) §0 steht: §1 des Auftrags
schließt die Stufen 4–10 für den Ausgang (B) ausdrücklich aus. Der Auftraggeber hat sie
angewiesen (E-009). **Diese Stufe misst keinen Vorteil und behauptet keinen.**

---

## 1. Was der Auftrag verlangt — und was davon hier fahrbar war

> Gegen die Demoumgebung: Platzierung, Abbruch, doppelte Auftragskennung, falsche
> Signatur, abweichende Uhr — als redigierte Aufzeichnungen einchecken.
> Nicht-endgültigen Zustand „Antwort blieb aus, Auftrag könnte leben" einführen, der
> sichtbar bleibt und vor der nächsten Eröffnung aufgelöst werden muss.
>
> **Abnahme:** mindestens eine echte, aufgezeichnete Antwort des Handelsplatzes liegt im
> Repo; drei Testfälle sichern Datenbankzustand, genau einen Auftrag beim Gegenüber und
> den Riegelzustand zu.

Die Stufe zerfällt in zwei Hälften, und sie sind unterschiedlich fahrbar:

| Teil | Braucht ein Demokonto? | Stand |
|---|---|---|
| Aufzeichnungen einchecken (Platzierung, Abbruch) | **nein** — sie existierten bereits | **erledigt** |
| Aufzeichnungen: falsche Signatur, abweichende Uhr, doppelte Kennung *am Handelsplatz* | **ja** | **offen**, §6 |
| Nicht-endgültiger Zustand | nein | **erledigt** |
| Abnahme: eine echte Antwort im Repo | nein | **erledigt** |
| Abnahme: drei Testfälle | nein | **erledigt** |

Mein Vorbehalt aus dem Schlussbericht der Stufe 4 („Stufe 5 ist hier nicht fahrbar") war
**zu weit gefasst**. Er trifft auf drei der fünf aufzuzeichnenden Situationen zu, nicht
auf die Stufe. Das gehört korrigiert, bevor der Rest steht.

---

## 2. Was gemessen wurde — der Zustand lag im Prozessgedächtnis

`Mt5Venue.submit_order` hielt schon fest, wenn ein Sendeversuch mit einer Ausnahme endete
(`_unklare_sendeversuche`). Gemessen wurde, ob dieser Zustand die drei Eigenschaften hat,
die der Auftrag verlangt. Beleg [`01-messung-vorher.txt`](belege/01-messung-vorher.txt) —
gefahren gegen einen eigenen Arbeitsbaum auf Commit `64b4423`, also gegen den
tatsächlichen Stand vor dieser Stufe:

| Forderung | vorher | nachher |
|---|---|---|
| eingeführt | ✔ `['unklar-1']`, Halt gelatcht | ✔ |
| **bleibt sichtbar** über einen Neustart | ✘ frisches Venue meldete `[]` | ✔ Akte auf der Platte |
| **muss vor der nächsten Eröffnung aufgelöst werden** | ✘ nach `clear_halt()` **DURCHGELASSEN** | ✔ `schwebender_auftrag` |
| Auflösung verlangt einen Befund | — gab es nicht | ✔ leerer Befund wirft |

Zwei echte Lücken:

**Lücke 1 — `clear_halt()` gab die Eröffnung frei, während der Eintrag noch stand.**
Der Sendeversuch latcht den Global-Halt *und* vermerkt die Kennung. `clear_halt()` löst
nur den Halt; die Arbeitsliste bleibt ausdrücklich stehen (so dokumentiert). Wer also nur
den Halt sieht — und im Betrieb sieht man zuerst den Halt — gibt ihn frei und eröffnet
weiter, an einer Order vorbei, die beim Broker liegen könnte.

**Lücke 2 — der Zustand überlebte keinen Neustart.** Dieselbe Fehlerklasse, gegen die
`risiko_zustand.py` gebaut wurde (dort begann der Drawdown nach jedem Prozessstart bei
null, gemessen: 22 Eröffnungen an einem Konto-Tag gegen eine Kappe von 10). Hier wiegt sie
schwerer: was verschwindet, ist die Kenntnis davon, dass möglicherweise Geld am Markt
steht — und ein Neustart ist der wahrscheinlichste Zustand nach genau dem Zwischenfall,
der den Eintrag erzeugt hat.

---

## 3. Was geändert wurde

### 3.1 Die Akte — `execution/schwebende_auftraege.py`

Ein kleiner, eigener Speicher für „Antwort blieb aus". **Kein zweiter Risikozustand:**
`risiko_zustand.py` führt Halt, Tageszähler und Equity-Fenster — Größen mit Tagesrhythmus
und einer Zwei-Schreiber-Vereinigung, die je Abschnitt eine eigene Irrtumsrichtung kennt.
Ein schwebender Auftrag hat keinen Tagesrhythmus, keine Zählung und nur eine
Irrtumsrichtung: **im Zweifel sperren**.

**Geteilt wird der Ort, nicht die Struktur.** `standard_zustandsordner` trägt die
vollständige Begründung, warum Zustand außerhalb des Arbeitsbaums liegt (kein
`git checkout` als stille Freigabe, kein `git clean -xdf` als Löschung, kein Kontoabdruck
im Verlauf). Diese Regel ein zweites Mal hinzuschreiben wäre genau der Fehler, den sie
verhindert.

Die Irrtumsrichtung, je Befund:

| Befund | Urteil |
|---|---|
| Datei fehlt | nichts schwebt — der Regelfall |
| Datei leer | nichts schwebt |
| Datei unlesbar / defekt | **Sperre mit Grund** |
| unbekannte Formatfassung | **Sperre mit Grund** |
| Eintrag unvollständig | **Sperre**, und der Eintrag zählt weiter |

Geschrieben wird **sofort** und über eine Nebendatei mit anschließendem Umbenennen: der
Zustand entsteht in dem Augenblick, in dem auch der Prozess wegbrechen kann.

### 3.2 Die Sperre im Orderpfad

`_verweigere_bei_schwebendem_auftrag()` steht im Eröffnungszweig **vor** dem Global-Halt
und trägt einen eigenen Grund (`schwebender_auftrag`). Gelesen wird die **Akte**, nicht
der Speicher dieses Prozesses — nach einem Neustart ist der Speicher leer, die Akte nicht,
und genau dieser Fall ist der gefährliche.

Reduzierende Aufträge sind unberührt (V5): die Sperre steht im Eröffnungszweig.

### 3.3 Die Auflösung ist eine menschliche Geste

`sendeversuch_aufloesen(kennung, befund=...)` verlangt einen **Befund** — den Text dessen,
was beim Broker nachgesehen wurde. Ein leerer Befund wirft. Das ist kein Formalismus: der
einzige Weg, diesen Zustand ehrlich zu beenden, führt über einen Menschen, der beim
Gegenüber nachgesehen hat. Ein Programm, das ihn selbst abräumt, hat nichts nachgesehen —
es hat nur aufgehört zu fragen.

Der Global-Halt bleibt davon unberührt. Das sind zwei Entscheidungen desselben Menschen,
aber nicht notwendig im selben Augenblick.

### 3.4 Dauerhaft nur auf Ansage — und das ist ablesbar

Die Akte ist ohne gesetzte Umgebungsvariable **flüchtig**. Das ist keine Nachlässigkeit,
sondern die Regel, die `RiskManager._zustand_waehlen` für den Risikozustand schon fährt:
eine Bibliothek schreibt nicht ungefragt in das Zustandsverzeichnis des Benutzers, nur
weil jemand ein Objekt gebaut hat.

Und wie dort ist die Flüchtigkeit **ablesbar** (`SchwebeAkte.dauerhaft`) — eine flüchtige
Akte verhält sich bis zum Neustart genau wie eine dauerhafte. Wer das erst am Neustart
merkt, merkt es an dem Tag, an dem es zählt.

**Diese Regel ist hier keine Theorie, sondern eine Messung:** ohne sie schrieb der
Testlauf dieses Repos in `%LOCALAPPDATA%` des Entwicklers, und die dort hinterlassenen
Kennungen sperrten anschließend **87 Testfälle**, die mit der Sache nichts zu tun hatten.
Die Rückstände sind entfernt worden.

---

## 4. Die Aufzeichnungen — `aufzeichnungen/demo-2026-08-17.jsonl`

**Die echten Antworten existierten bereits.** 21 Journale mit **17.166 Sätzen** aus einem
Demolauf am 2026-08-17 lagen unter `betrieb/` — aber nicht **im Repo**: das Verzeichnis
steht in `.gitignore`, und das zu Recht (Laufzeitdatenhalde). Die Abnahme verlangt
ausdrücklich „liegt im Repo".

`tools/aufzeichnung_redigieren.py` schlägt die Brücke. Beleg
[`03-aufzeichnung.txt`](belege/03-aufzeichnung.txt).

### 4.1 Redigiert — irreversibel, ohne Schlüssel

| Feld | wird zu |
|---|---|
| `konto` | `KONTO-1` |
| `order_id` | `ORDER-0001` |
| `position_id` | `POSITION-01` |
| `client_order_id` | `KENNUNG-0001` |
| `lauf` | `LAUF-01` |
| `pfad` | `<entfernt>` |

**Laufende Nummern, keine Hashes.** Eine Kontonummer hat so wenig Entropie, dass ein Hash
davon in Sekunden zurückgerechnet ist; ein gesalzener Hash bräuchte ein Salz, das
irgendwo liegen muss. Die laufende Nummer hält gleiche Werte gleich — die Aufzeichnung
bleibt lesbar — und trägt nichts vom Original in sich. Es gibt keine gespeicherte
Zuordnung.

Erhalten bleiben Preise, Volumina, Zeitstempel, Symbole, Gründe und die **Fehlertexte des
Handelsplatzes**. Das ist der Inhalt, um dessentwillen die Aufzeichnung existiert.

Gegenprobe auf der eingecheckten Datei: **0 Treffer** für Ziffernfolgen von 6–12 Stellen,
für Windows-Pfade, für den Benutzernamen und für die Original-Kennungen.

### 4.2 Verkleinert — und die Verkleinerung steht drin

| | Sätze |
|---|---:|
| behalten | **110** |
| weggelassen | **17.056** |

Weggelassen sind vier Arten, die zusammen 98 % ausmachen und keine Antwort des
Handelsplatzes tragen: `kurs` (7.010), `signal` (4.343), `eroeffnungsversuch` (4.343),
`takt` (1.360). **Die Zahl steht je Art im Kopf der Datei.** Eine stille Verkleinerung
wäre eine Aufzeichnung, die vollständig aussieht und es nicht ist — und genau das soll
eine Aufzeichnung nicht können.

### 4.3 Was drinsteht — echte Antworten

| Art | Sätze | was sie belegt |
|---|---:|---|
| `eroeffnet` | 16 | **Platzierung** mit Einstiegspreis vom Handelsplatz |
| `geschlossen` | 26 | Schließungen mit Ausstiegspreis |
| `schliessen_fehlgeschlagen` | 7 | **Abbruch** — im Wortlaut: „Handelsplatz hat abgelehnt: Done" |
| `vom_broker_geschlossen` | 6 | serverseitige Schließungen |
| `halt_erklaert` | 4 | Reconcile-Drift, die den Halt gesetzt hat |
| `buch_uebernommen` | 6 | `adopt_book` nach Neustart |
| `start` / `ende` / `stoppdatei` | 45 | Lauf-Ränder |

Ein Dauertor prüft, dass die Datei liegt, echte Antworten trägt, keine unredigierten Werte
enthält und mit den Journalen übereinstimmt (`--pruefen`).

---

## 5. Abnahme

**Die drei namentlich verlangten Testfälle** — `tests/test_stufe5_ausfuehrung.py`,
**17 Fälle**, je Tor rot und grün, Beleg [`05-abnahme.txt`](belege/05-abnahme.txt):

| Verlangt | Fälle |
|---|---|
| **Datenbankzustand** | überdauert den Neustart; ohne Zwischenfall leer; sperrt bei unlesbarer Akte; sperrt bei unbekannter Fassung; Flüchtigkeit ablesbar; flüchtig wirkt im Lauf |
| **Genau ein Auftrag beim Gegenüber** | dieselbe Kennung → `order_send_calls == 1`, zweiter Ruf ist `idempotent_replay`; zwei verschiedene Kennungen → 2 Aufträge |
| **Riegelzustand** | schwebender Auftrag sperrt; `clear_halt()` allein gibt **nicht** frei; Auflösung ohne Befund abgewiesen; Auflösung mit Befund gibt frei; der erste Grund bleibt stehen |

**Mutationsprobe** ([`04-mutationsprobe.txt`](belege/04-mutationsprobe.txt)) — vier
Rückfälle eingebaut:

| Mutation | rote Fälle |
|---|---:|
| M1 Sperre aus dem Orderpfad genommen | **4** |
| M2 Akte nur noch im Speicher | **8** |
| M3 Auflösung ohne Befund erlaubt | **1** |
| M4 Kontonummer in die Aufzeichnung geschmuggelt | **2** |

Nach jeder Mutation aus einer **vor** dem Eingriff angelegten Kopie zurückgestellt (F-010);
alle drei Prüfsummen danach identisch.

**Torlauf** ([`06-torlauf.txt`](belege/06-torlauf.txt)): `ruff`, `mypy --strict`,
`check_docs_claims`, `check_doc_numbers`, `gen_docs --check`, `kopien_abgleichen --pruefen`,
`aufzeichnung_redigieren --pruefen` je **Exit 0**; `pytest` **1.448 bestanden, 0
fehlgeschlagen**.

---

## 6. Was schiefging

**F-011 — einen „Vorher"-Beleg gegen den Nachher-Stand gefahren.** Der erste Anlauf von
`01-messung-vorher.txt` lief gegen den Arbeitsbaum, in dem die Änderung bereits stand, und
trug trotzdem einen Kopf, der Commit `64b4423` behauptete. Aufgefallen beim Durchsehen:
die Ausgabe nannte einen Ablehnungsgrund, den es vor dieser Stufe nicht gab. Berichtigt
über einen eigenen Arbeitsbaum auf `64b4423`. Vollständig in
[`../../fehler.md`](../../fehler.md), F-011.

**Der Testlauf schrieb in das Zustandsverzeichnis des Entwicklers.** Die erste Fassung der
Akte griff ohne Umgebungsvariable auf den Standardpfad zu; damit legte der Testlauf dort
Kennungen ab, die anschließend 87 fremde Fälle sperrten. Ursache und Behebung stehen in
§3.4; die Rückstände sind entfernt.

---

## 7. Was offen bleibt — und warum es hier nicht zu schließen ist

Der Auftrag nennt fünf aufzuzeichnende Situationen. **Zwei liegen aufgezeichnet vor**
(Platzierung, Abbruch). Drei nicht:

| Situation | warum nicht |
|---|---|
| **doppelte Auftragskennung** | Als Verhalten des Standes ist sie festgenagelt (der Idempotenz-Fall). Aufgezeichnet ist sie nicht: der Demolauf hat sie nie ausgelöst, und sie am Handelsplatz zu provozieren verlangt eine Sitzung. |
| **falsche Signatur** | Verlangt einen absichtlich fehlerhaften Zugang gegen das Terminal. |
| **abweichende Uhr** | Verlangt einen Lauf mit verstellter Systemzeit gegen das Terminal. |

**Alle drei brauchen ein verbundenes Demokonto.** `MetaTrader5` ist installiert, aber es
liegt **keine Terminal-Konfiguration** vor (`.env`, `.env.local`, `config/mt5.json` fehlen
alle). Zugangsdaten beizustellen ist Sache des Auftraggebers; ich beschaffe keine und
umgehe keine Zugangsbeschränkung (V8).

**Was daraus folgt, ohne Beschönigung:** Die Abnahme dieser Stufe ist erfüllt — sie
verlangt „mindestens eine echte, aufgezeichnete Antwort" und drei Testfälle, und beides
liegt vor. Die Aufzählung der fünf Situationen ist es **nicht**. Wer diese Stufe als
vollständig lesen will, muss die drei fehlenden Aufzeichnungen nachholen, sobald ein
Demokonto erreichbar ist.
