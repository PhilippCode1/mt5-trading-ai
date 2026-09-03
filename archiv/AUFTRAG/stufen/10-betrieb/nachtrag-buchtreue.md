# Nachtrag zu Stufe 10 — die Buchtreue, aufgeschlüsselt und korrigiert

*Gefahren am 2026-08-20 auf Anweisung des Auftraggebers („buchtreue beheben"). Belege in
[`belege/`](belege/), drei neue Dateien. Bestätigt durch Ausführung.*

---

## 1. Was gemessen wurde

Stufe 10 hat die Buchtreue mit **98,5 % (1.340 von 1.360 Takten)** gemessen, Ziel 99 %.
Beleg [`buchtreue-aufschluesselung.txt`](belege/buchtreue-aufschluesselung.txt).

**Alle 20 gesperrten Takte tragen denselben Grund:**
`reconcile_drift:notional_drift_exceeds_limit`. Kein einziger anderer.

Darin stecken aber **zwei völlig verschiedene Lagen**:

| Journal | Codestand | Takte | Halt | im Takt erklärt | wirklich gesperrt | Eröffnungsversuche in Halt-Takten |
|---|---|---:|---:|---:|---:|---:|
| `145606` | ohne Stempel | 3 | 2 | 0 | **2** | 0 |
| `160253` | ohne Stempel | 87 | 10 | 0 | **10** | 0 |
| `174305` | `4ad1683+aenderungen` | 46 | 4 | 0 | **4** | 0 |
| `182951` | **`d5c7133`** | **1.122** | 4 | 4 | **0** | **16** |

Die letzte Spalte entscheidet. In den 16 wirklich gesperrten Takten gab es **null**
Eröffnungsversuche — der Lauf hörte auf, es zu versuchen. In den vier erklärten Takten
liefen **je vier Eröffnungsversuche** normal durch, abgelehnt aus völlig anderen Gründen
(`cost_unverifiable`, `Trade disabled`, `throttle_cooldown_active`); in Takt 409 führte
einer sogar zu einer Eröffnung.

**Der Halt in diesen vier Takten hat nichts gesperrt.**

---

## 2. Zwei Befunde

### (a) Die Metrik widersprach ihrem eigenen Docstring

`buchtreue` zählte jeden Takt mit `halt=true`. Die Begründung im Docstring lautete
wörtlich: *„Beides sperrt jede Eröffnung."* Für 4 von 20 Halt-Takten stimmte dieser Satz
nachweislich nicht.

Die Ursache ist die Reihenfolge im Takt: der Scheduler läuft **vor** dem Buchabgleich.
Schließt der Broker zwischen zwei Takten eine Position — ein völlig normaler Stop-Fill —,
sieht der Reconcile sie noch im Buch und latcht fail-closed. Der Abgleich im selben Takt
erkennt die Schließung, löst auf, und die Eintritte laufen. Der `takt`-Satz wird **vor**
dieser Auflösung geschrieben und kann sie nicht kennen.

### (b) Alle Sperren sitzen in Code, den es nicht mehr gibt

Der einzige sauber gestempelte Codestand — `d5c7133`, der längste Lauf des Standes mit
1.122 der 1.360 Takte — hat **keinen einzigen gesperrten Takt**. Alle 16 stammen aus
Ständen ohne Versionsstempel oder mit `+aenderungen` (unsauberes Arbeitsverzeichnis;
zu welchem Quelltext die Zahlen gehören, weiß niemand).

Die Gesamtzahl mischt also mindestens vier Codestände. Das ist als **Ergebnis** richtig —
es ist der Betrieb, den es gegeben hat — aber als **Diagnose** unbrauchbar, und zwar in
beide Richtungen: ein behobener Defekt drückt die Zahl für immer, und ein neuer Defekt
verschwindet in der Geschichte, weil ein Lauf 82 % aller Takte stellt.

---

## 3. Was **nicht** geändert wurde, und warum

Naheliegend wäre, den Buchabgleich vor den Reconcile zu ziehen — dann entstünde gar kein
Halt. **Das wäre ein Rückschritt.**

Der Reconcile *ist* die Erkennung eines Desyncs. Läuft der Abgleich zuerst, stimmt das
Buch danach immer mit dem Broker überein, und die Erkennung könnte per Konstruktion nie
auslösen. Das ist genau die Hausfehlerklasse dieses Repositoriums: der Melder, der nie
feuern kann. Die jetzige Ordnung ist fail-closed und richtig — erst sperren, dann **genau
den einen** erkannten gutartigen Fall auflösen.

Auch der frühe Zeitpunkt des `takt`-Satzes bleibt: die Notbremse unter 2b kann vorher
zurückkehren, und ein später geschriebener Takt-Satz wäre dann ganz verloren.

Geändert wurde deshalb die **Aufzeichnung**, nicht die Ordnung.

---

## 4. Was geändert wurde

### (1) `halt_erklaert` trägt `weiter_gesperrt`

Der Scheduler wird nach dem `clear_halt()` erneut befragt; sein Ergebnis regiert die
Eintritte unter 4). Genau dieser Wert steht jetzt im Satz. Die Reihenfolge ist das
Eigentliche: würde das Feld vor der erneuten Befragung geschrieben, trüge es den alten
Zustand und sägte die Aussage ab, für die es da ist.

### (2) `buchtreue` zählt die Leiter, ohne Ersatzwerte (V3)

| Lage | gezählt als |
|---|---|
| `halt` nicht gesetzt | sauber |
| Halt, kein `halt_erklaert` | **gesperrt** — der Halt stand den Takt durch |
| Halt, erklärt, `weiter_gesperrt=false` | sauber |
| Halt, erklärt, `weiter_gesperrt=true` | **gesperrt** |
| Halt, erklärt, Feld fehlt | **unbeurteilbar** — nicht im Nenner |

Der vierte Fall ist der, der die Korrektur ehrlich hält: latcht der Scheduler sofort
wieder — aus einem anderen Grund —, war der Takt sehr wohl gesperrt. Ohne diesen Zweig
hieße „es gab eine Auflösung" pauschal „es war frei".

### (3) `nach_codestand` — die Diagnose neben dem Urteil

Dieselben Metriken, getrennt nach dem `version`-Stempel des Laufs. Zwei Gruppen tragen
ihre Einschränkung im Namen: `ohne Stempel` und alles mit `+aenderungen`.

**Sie ersetzt die Gesamtzahl nicht und darf es nicht** — sonst wäre sie die bequeme
Auswahl der guten Läufe. Die Ziele urteilen weiter über alle Journale zusammen; die
Tabelle beantwortet die andere Frage, die den Betrieb wirklich leitet: *passiert es noch?*

### (4) `RUNBOOK.md` §„Buchtreue unter Ziel"

Zwei Fragen an den Anfang gestellt, weil sie bei jedem zweiten Alarm die Antwort schon
sind: **Hat der Halt überhaupt gesperrt?** und **Sitzt es im lebenden Code?**

---

## 5. Was das an den Zahlen ändert

Beleg [`dienstguete-nach-buchtreue.txt`](belege/dienstguete-nach-buchtreue.txt).

| | vorher | nachher | Ziel |
|---|---:|---:|---:|
| Buchtreue | 98,53 % (1.340/1.360) | **98,82 % (1.340/1.356)** | 99,0 % |

**Die Korrektur rettet das Ziel nicht — und das ist der Punkt.** Ein Dauertor
(`test_die_korrektur_rettet_das_ziel_NICHT`) hält fest, dass der Wert unter der Schwelle
bleibt: hätte die Korrektur die Zahl darüber gehoben, wäre sie eine
Schwellenverschiebung durch die Hintertür gewesen, egal wie gut begründet. Die Schwelle
von 99 % ist **unverändert**.

Die Aufschlüsselung nach Codestand:

```
Codestand                    Buchtreue Ausstiegsverl Laufabschluss Ausstiegsdeck
4ad1683+aenderungen         91.5% (47)     40.0% (5)    100.0% (2)     50.0% (2)  !! nicht reproduzierbar
767ff87+aenderungen         100.0% (1)      0.0% (2)    100.0% (1)      0.0% (1)  !! nicht reproduzierbar
d5c7133                  100.0% (1118)    100.0% (9)      0.0% (1)            --
ohne Stempel               93.7% (190)    88.2% (17)    94.1% (17)    100.0% (5)  !! vor der Versionsstempelung
```

Sie ist ausdrücklich **nicht** schmeichelhaft: `d5c7133` hat zwar 100 % Buchtreue und
100 % Ausstiegsverlässlichkeit, aber **0 % Laufabschluss** — der eine lange Lauf unter
diesem Stand ist nie sauber zu Ende gekommen.

---

## 6. Abnahme

Beleg [`buchtreue-tests.txt`](belege/buchtreue-tests.txt) — `tests/test_buchtreue.py`,
**12 Fälle, alle grün**, rot und grün je Sprosse der Leiter:

| Eigenschaft | Fall |
|---|---|
| Takt ohne Halt | grün: sauber |
| Halt ohne Auflösung | rot: gesperrt (die 16 echten) |
| Halt im selben Takt aufgelöst | grün: sauber (die 4) |
| Aufgelöst, aber weiter gesperrt | rot: trotzdem gesperrt |
| Auflösung ohne das Feld | unbeurteilbar, nicht im Nenner (V3) |
| Fenstergrenze | eine Auflösung deckt nur ihren eigenen Takt |
| Redlichkeit | die Korrektur hebt den Wert **nicht** über die Schwelle |
| Der Schreiber | `weiter_gesperrt` wird **nach** der erneuten Befragung geschrieben |
| Aufschlüsselung | trennt Stände; ohne Stempel und `+aenderungen` erkennbar |
| Auf echten Daten | jeder sauber gestempelte Stand hat 100 % Buchtreue |

Elf Tore je Exit 0; pytest **1.610 grün**; Tötungsrate 1,000 (16/16); Zweigdeckung jede
Geldpfad-Datei über 80 % (Paket 88,1 % Zweige).

---

## 7. Was dieser Nachtrag ausdrücklich nicht behauptet

* **Die Buchtreue ist nicht auf 99 % gehoben.** Sie steht bei 98,82 %, der Alarm steht,
  und das ist richtig so — 16 Takte waren wirklich gesperrt.
* **Der Reconcile-Halt bei normaler Broker-Schließung ist nicht beseitigt.** Er entsteht
  weiter und wird weiter aufgelöst. Das ist Absicht: ihn zu vermeiden hieße, die
  Desync-Erkennung abzuschalten.
* **Die Aufschlüsselung nach Codestand ist Diagnose, kein Urteil.** Wer sie als Urteil
  liest, hat die guten Läufe ausgewählt.
* **Kein Vorteil.** Befund (B) aus Stufe 3 steht unverändert.
