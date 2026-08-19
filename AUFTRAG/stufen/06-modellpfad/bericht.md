# Stufe 6 — Modellpfad schließbar machen

*Gefahren am 2026-08-19 auf Anweisung des Auftraggebers („weiter mit stufe 6"). Belege
in [`belege/`](belege/), fünf Dateien. Bestätigt durch Ausführung — jede Ausgabe liegt
bei.*

---

## 0. Zur Zulässigkeit — unverändert die Entscheidung des Auftraggebers

Es gilt weiter, was in [Stufe 4](../04-risikokern/bericht.md) §0 steht: §1 schließt die
Stufen 4–10 für den Ausgang (B) aus, der Auftraggeber hat sie angewiesen (E-009).
**Diese Stufe misst keinen Vorteil und behauptet keinen.**

---

## 1. Zuerst die Frage, die vor allem anderen steht: gibt es hier einen Modellpfad?

Der Vermerk zu diesem Stand hält fest, dass OpenAI-Anbindung und News-Engine gestrichen
wurden, und `backtest/llm_compare.py` sagt ausdrücklich: der Entscheidungspfad ist
**LLM-frei**. Es wäre bequem gewesen, daraus „kein Modellpfad, nichts zu tun" zu machen.

Gemessen ist es anders. **Der Modellpfad dieses Standes ist
`gates/learning_phase.py`:** aus beobachteten Trades entstehen **Parametersätze**
(`Proposal`). Das ist ein Modell im Sinne dieser Stufe — eine aus Daten abgeleitete
Größe, die später Entscheidungen färben soll — und alle sechs Forderungen greifen daran.

*(Nebenbefund, nicht Gegenstand dieser Stufe: `evaluate_llm_gate` hat **keinen Aufrufer
im Ausführungspfad**, nur Tests. §8.)*

---

## 2. Was gemessen wurde

Beleg [`01-messung-vorher.txt`](belege/01-messung-vorher.txt), gefahren gegen einen
eigenen Arbeitsbaum auf Commit `d3943f9` — also gegen den tatsächlichen Stand vor dieser
Stufe.

| # | Forderung | vorher |
|---|---|---|
| A1 | Beförderung standardmäßig aus | **erfüllt** |
| A2 | Artefakt erreicht den auswertenden Dienst und überlebt Neustarts | **Lücke** |
| A3 | Freigabeteilung auf den gesäuberten Vorwärtstest | **Lücke** |
| A4 | Trainingsmindestmenge im Verhältnis zur Merkmalszahl | **Lücke** |
| A5 | Trainingsendpunkte authentifizieren | **teilweise** |
| A6 | Überlappende Zielwerte gewichten | **Lücke** |
| B1 | Trainingslauf erzeugt einen Herausforderer im Wartezustand | **Lücke** (kein Lauf) |
| B2 | Falscher Schemahash führt zum Verwerfen | **Lücke** (kein Hash) |
| B3 | Artefakt nach Neustart noch da | **Lücke** |

Die Zahlen dazu, alle aus dem Beleg:

- **A4:** eine Rangliste entstand aus **einem einzigen Trade** (`min_trades` steht auf 1).
  **Acht Parameter** ließen sich vorschlagen, ohne dass die Beobachtungszahl irgendwo
  einging.
- **A6:** fünf **vollständig deckungsgleiche** Trades — dieselbe Marktbewegung fünfmal —
  zählten als `trades=5, hit_rate=1.0`. Fünf unabhängige Belege, wo einer ist.
- **A5:** leere Prüfsumme und leerer Codestand wurden abgewiesen (vom Ledger), aber
  `data_checksum="egal"` ging **durch**. Eine Herkunft, die jeder Text sein darf,
  authentifiziert nichts.
- **A2/B2/B3:** kein Schemahash, kein Artefakt, keine Lesefunktion. Der Vorschlag landete
  als Versuchszeile im Ledger — **ohne seinen Zustand** (`'state' in Eintrag → False`).

---

## 3. Was geändert wurde

### 3.1 `gates/herausforderer.py` — das Artefakt

Ein `Herausforderer` entsteht im Zustand **`wartend`** und sagt selbst, worauf er wartet
(`freigabeteilung`). Er trägt Herkunft, rohe Beobachtungszahl **und** die um die
Überlappung bereinigte.

**Die Beförderung ist kein Programmschritt.** Es gibt im Modul keine Funktion, die einen
Zustand ändert — ein Dauertor am Syntaxbaum hält das fest und wird rot, sobald jemand
eine schreibt. Und sie ist auch **kein Feld in einer Datei**: ein Artefakt, das sich
selbst zum Champion erklärt, wird beim Lesen verworfen.

### 3.2 Die zwei Rechenregeln

**Mindestmenge je Merkmal** — `max(50, 30 × Parameterzahl)` effektive Beobachtungen:

| Parameter | nötige effektive Beobachtungen |
|---:|---:|
| 1 | 50 |
| 2 | 60 |
| 4 | 120 |
| 8 | 240 |

Die Zahl ist keine Wissenschaft und wird auch nicht als solche verkauft. Sie ist eine
**vorab gesetzte** Schranke gegen genau den Fall, den die Messung gefunden hat: acht
Parameter aus drei Trades. Verschärfen ist erlaubt, senken nicht (V6).

**Überlappung** — belegte Zeit (Vereinigung der Haltespannen) geteilt durch die mittlere
Haltedauer, je Instrument:

| Lage | roh | effektiv |
|---|---:|---:|
| 5 deckungsgleiche Trades | 5 | **1,00** |
| 5 disjunkte Trades | 5 | **5,00** |
| 5 + 5 auf zwei Instrumenten | 10 | **2,00** |

Das ist dieselbe Überlegung wie Purge/Embargo in `backtest/splits.py`: dort wird
verhindert, dass Trainings- und Testfenster dieselbe Bewegung sehen, hier, dass eine
Bewegung mehrfach als Beleg zählt.

**Was die Regel ausdrücklich nicht leistet, und das steht im Code:** sie behandelt die
zeitliche Überlappung, die man ohne Marktmodell sehen kann. EURUSD und GBPUSD an einem
Dollartag laufen eng zusammen und werden trotzdem doppelt gezählt. Das bleibt offen und
wird nicht als gelöst ausgegeben.

### 3.3 Der Schemahash — kein Formalismus

Gehasht werden **Feldnamen und Feldtypen** des Artefakts. Über die Typen, nicht nur die
Namen: eine Umdeutung von `int` nach `float` ändert die Bedeutung einer Zahl, ohne ihren
Namen anzufassen — genau die Änderung, die diese Stufe selbst vorgenommen hat
(`effektive_beobachtungen`).

Der gefährliche Fall ist nicht der Absturz, sondern die stille Fehldeutung: `beobachtungen`
hieß früher „Trades", heißt jetzt etwas anderes, und dieselbe Zahl bedeutet plötzlich
nicht mehr dasselbe. Ein Artefakt mit fremdem Hash wird **verworfen, nicht zurechtgebogen**.

**Je Datei ein Artefakt.** Ein defektes nimmt nur sich selbst mit; eine Sammeldatei hätte
bei einem einzigen Formatfehler alle verworfen, und der Betrieb stünde ohne jeden
Kandidaten da, ohne zu wissen warum.

### 3.4 Herkunft authentifiziert

`data_checksum` muss eine SHA-256-Hexprüfsumme sein — 64 Zeichen aus `[0-9a-f]`. Gemessen
nach der Änderung: `"egal"`, 63 Zeichen, 65 Zeichen und `"z"×64` werden alle abgewiesen,
eine echte Prüfsumme geht durch.

### 3.5 `tools/modelllauf.py` — der Trainingslauf

Der Einstiegspunkt, den die Abnahme verlangt. Er liest ein Journal, leitet einen
Parametersatz ab, und legt ihn als Artefakt ab — **wenn** er die Schranken nimmt.

Was er ausdrücklich nicht tut: **nichts befördern** (kein Schalter dafür), **nicht
optimieren** (der Vorschlag ist eine Ableitung, kein Suchlauf über einen Parameterraum —
ein Suchlauf wäre nach dem Ergebnistor ein neuer Versuch je Punkt), und **nicht ins
Versuchsregister schreiben** (ein wartender Kandidat hat nichts gemessen; wer hier zählte,
zählte Absichten statt Messungen und verschärfte die Deflation aller späteren Läufe für
nichts).

---

## 4. Der Lauf auf den echten Daten — und was er sagt

Gegen die in Stufe 5 eingecheckte Aufzeichnung
([`02-messung-nachher.txt`](belege/02-messung-nachher.txt)):

```
Geschlossene Trades: 16
Parametersatz     : {'max_haltedauer_stunden': 2.41}
Noetig dafuer     : 50 effektive Beobachtungen

KEIN HERAUSFORDERER — 1 Parameter verlangen 50 effektive Beobachtungen,
vorhanden sind 16.0 (aus 16 Trades, der Rest ist Ueberlappung).
```

**Das ist das wichtigste Einzelergebnis dieser Stufe.** Auf den einzigen echten
Betriebsdaten, die dieser Stand besitzt, trägt die Beobachtungsmenge **nicht einmal einen
einzigen Parameter**. Der Lauf legt nichts an — es entsteht nichts, was später aussähe,
als hätte es einmal gegolten.

Eine Schranke, die auf den eigenen Daten sofort greift, ist keine Zierde.

---

## 5. Abnahme

**`tests/test_stufe6_modellpfad.py`, 30 Fälle**, je Tor rot und grün, Beleg
[`04-abnahme.txt`](belege/04-abnahme.txt). Die drei namentlich verlangten:

| Verlangt | Fälle |
|---|---|
| **Herausforderer im Wartezustand, kein Champion** | Lauf legt `zustand=wartend` an; kein Zustandswechsel im Modul (Syntaxbaum); Artefakt mit `champion` wird nicht gelesen |
| **Falscher Schemahash → verwerfen** | fremder Hash verworfen; richtiger gelesen; Hash hängt an den Feldern; unlesbare Datei genannt; ein Defekt nimmt die anderen nicht mit |
| **Artefakt nach Neustart noch da** | zweite Ablage auf demselben Ordner findet es samt Zustand und Herkunft; leere Ablage meldet leer statt zu werfen |

**Mutationsprobe** ([`03-mutationsprobe.txt`](belege/03-mutationsprobe.txt)):

| Mutation | rote Fälle |
|---|---:|
| M1 Überlappungsgewichtung ausgeschaltet | **3** |
| M2 Mindestmenge auf 1 gesetzt | **2** |
| M3 Schemahash zur Konstante gemacht | **1** |
| M4 Herkunftsprüfung wirkungslos | **3** |
| M5 Zustandswechsel eingebaut (`befoerdere()`) | **1** |

Nach jeder Mutation aus einer **vor** dem Eingriff angelegten Kopie zurückgestellt
(F-010); Prüfsumme danach identisch: `fe931c98…500`.

**Torlauf** ([`05-torlauf.txt`](belege/05-torlauf.txt)): sieben Tore je **Exit 0**;
`pytest` **1.478 bestanden, 0 fehlgeschlagen**.

---

## 6. Was schiefging

**Eine zu naive Zusicherung.** Der Abnahmefall zu B1 prüfte zunächst, dass das Wort
„champion" in der Ausgabe des Werkzeugs nicht vorkommt. Es kommt vor — im Banner des
Werkzeugs selbst („nie einen Champion"). Der Fall prüft jetzt den ausgegebenen
**Zustand** statt ein Wort. Das ist derselbe Fehlertyp wie F-005: eine Zeichenkette
gesucht, wo eine Sache gemeint war.

---

## 7. Was diese Stufe ausdrücklich nicht behauptet

**Die Schranken sind gesetzt, nicht hergeleitet.** 30 Beobachtungen je Parameter und 50
absolut sind eine vorab gesetzte Konvention gegen einen gemessenen Missstand — keine aus
der Statistik abgeleitete Größe. Sie stehen im Code als Konstanten mit Namen, damit
sichtbar bleibt, dass sie eine Wahl sind.

**Die Überlappungsrechnung ist zeitlich, nicht ökonomisch.** Sie sieht, was sich zeitlich
überschneidet. Korrelierte Instrumente sieht sie nicht (§3.2).

**Es gibt keinen Champion und keinen Weg zu einem.** Diese Stufe baut die Wartespur.
Wer einen Herausforderer befördern will, muss ihn durch den gesäuberten Vorwärtstest und
das Sechs-Bedingungen-Tor schicken — und das ist nach dem Ergebnistor ein
vorregistrierungspflichtiger Versuch (H-004).

---

## 8. Nebenbefund, nicht behoben

**`evaluate_llm_gate` hat keinen Aufrufer im Ausführungspfad** — nur Tests. Das ist genau
die Krankheit, die §0 des Auftrags benennt („Gates ohne Auslösung"), und V1 verlangt für
Code ohne Aufrufer die Löschung.

**Nicht in dieser Stufe angefasst**, und zwar aus einem benennbaren Grund: das Tor ist die
einzige Zulassungsstelle für ein Modell im Entscheidungspfad, und ein Regressionstest
verankert, dass das ganze Paket LLM-frei ist. Es zu löschen, während der Pfad LLM-frei
ist, hieße die Sperre zu entfernen, die den Zustand hält. Es zu verdrahten hieße, einen
Aufrufpunkt zu erfinden, den es nicht gibt.

Beides ist eine Entscheidung, keine Aufräumarbeit — sie gehört dem Auftraggeber
vorgelegt, nicht nebenbei getroffen. Der Widerspruch zu V1 steht damit ausdrücklich
offen.
