# Nachtrag zu Stufe 10 — die Ausstiegsverlässlichkeit, aufgeschlüsselt und behoben

*Gefahren am 2026-08-20 auf Anweisung des Auftraggebers („Ausstiegsverlässlichkeit
beheben"). Belege in [`belege/`](belege/), vier neue Dateien. Bestätigt durch Ausführung.*

---

## 0. Der Anlass

Stufe 10 hat drei Dienstgüteziele gemessen und alle drei verfehlt. Das schlechteste
Ergebnis des ganzen Standes war die **Ausstiegsverlässlichkeit: 78,8 % (26 von 33
Schließversuchen)**, Fehlerbudget zu 424 % verbraucht. Der Bericht der Stufe nennt sie
„die schwerste Zahl", weil ein misslungener Ausstieg Geld am Markt lässt.

Dieser Nachtrag schlüsselt die sieben Fehlschläge auf, statt die Zahl zu deuten.

---

## 1. Was gemessen wurde

Beleg [`ausstieg-aufschluesselung.txt`](belege/ausstieg-aufschluesselung.txt). Die sieben
Fehlschläge zerfallen in **zwei Klassen mit völlig verschiedenen Ursachen** — die
aggregierte Zahl hatte sie verdeckt.

| Klasse | Fälle | Wortlaut | Stand |
|---|---:|---|---|
| A | 2 | `Handelsplatz hat abgelehnt: Done` / `Done (retcode=0)` | **bereits behoben** |
| B | 5 | `Real-Terminal: Schreibpfad gesperrt (allow_write=False)` | **war offen** |

### Klasse A — eine ausgeführte Schließung galt als Ablehnung

Dieser Broker meldet Erfolg mit `retcode=0` und `comment='Done'` — samt gültiger
Order-Kennung, Deal-Kennung, Volumen und Preis. Eine Prüfung allein auf
`TRADE_RETCODE_DONE` (10009) hielt das für eine Ablehnung.

Die beiden Fälle datieren auf **14:57:23 und 14:58:42 UTC**. Der Fix `82c81c3`
(`_send_angenommen`: dokumentierter Erfolgscode **oder** `retcode == 0` *zusammen mit*
dem Beweis einer Ausführung) ist von **15:03:59 UTC** — fünf Minuten nach dem zweiten
Fall. Gepinnt in
`tests/test_schreibpfad_wirkung.py::test_der_gemessene_retcode_null_bleibt_ein_fill`
(„Der reale Fall vom 2026-08-17"), 29 Fälle grün.

**Diese Klasse ist Geschichte, nicht Arbeit.** Sie ist hier trotzdem aufgeführt, weil
sonst zwei Siebtel der gemessenen Fehlerrate unerklärt blieben — und weil sie in die
gefährliche Richtung falsch lag: der Schluss ging beim Broker durch, das System hielt
ihn für gescheitert.

### Klasse B — der Lauf sagte einen Ausstieg zu, den er nicht halten konnte

Zwei Läufe (`journal-20260817T173413`, `journal-20260817T182800`), beide **ohne
`--scharf`**, also ohne Schreibrecht. Beide haben beim Start über `adopt_book()` fremde
Positionen übernommen — das Journal `173413` weist **23.002,90 belegte Marge** aus —,
einen Takt lang beaufsichtigt, und **erst beim Herunterfahren** gemerkt, dass sie den
zugesagten Ausstieg nicht fahren können.

Der Fehler liegt nicht im Glattstellen. Er liegt darin, dass der Lauf **eine Zusage
annimmt, die er von Anfang an nicht halten kann.**

---

## 2. Der Befund, der die Stufe-10-Messung selbst betrifft

Beide Läufe haben einen `start`- und einen `ende`-Satz. **`laufabschluss` zählt sie als
saubere Läufe.** Und `ausstiegsverlässlichkeit` sieht nur einzelne Schließversuche, nicht
das Ergebnis.

> Keine der drei Kennzahlen aus Stufe 10 sah den schlimmsten Zustand, den dieser Stand
> je erreicht hat: **ein beendeter Lauf mit offenen Positionen am Broker.**

Der `ende`-Satz führte es die ganze Zeit mit:

```
"offen_geblieben": ["EURUSD", "GBPUSD", "XAUUSD"]
"offen_geblieben": ["EURUSD", "GBPUSD"]
```

Gelesen hat es niemand. Das ist ein Messfehler meiner eigenen Stufe 10 — nicht falsch
gerechnet, sondern **das Falsche gezählt.**

Was schon richtig war und beim Nachsehen bestätigt wurde: der Lauf endet **nicht** still.
`tools/live_betrieb.py` schreibt eine Warnung auf die Fehlerausgabe und endet mit
`return 4`. Mein anfänglicher Verdacht auf einen stillen Abschluss war falsch; der
Exit-Code existiert, er ist nur nirgends aufgesammelt worden.

---

## 3. Was geändert wurde

### (1) Der Riegel — `tools/live_betrieb.py::ausstiegszusage_pruefen`

Eine reine Funktion, gerufen in `main()` **vor `adopt_book()`**: übernommen wird nur, was
dieser Lauf auch wieder loswerden kann. Sagt der Lauf ein Glattstellen zu, kann es aber
nicht halten, und stehen Positionen offen → **kein Start**, `return 2`, mit Nennung der
offenen Symbole.

Drei Auswege, alle ausdrücklich in der Meldung genannt — ein Riegel ohne Ausweg wird
umgangen:

* `--scharf` — der Lauf bekommt das Schreibrecht.
* `--am-ende-offen-lassen` — der Lauf verspricht den Ausstieg gar nicht erst; die
  Verantwortung bleibt beim Menschen, **und er hat es hingeschrieben**.
* Die Positionen vorher von Hand schließen.

Die Stelle ist bewusst dieselbe wie beim AutoTrading-Vorcheck darunter, und aus demselben
Grund: eine Unfähigkeit, die erst beim Senden auffällt, sieht dann aus wie ein Fehler der
Software.

### (2) Die Metrik — `betrieb/dienstguete.py::ausstiegsdeckung`

Anteil der beendeten Läufe, die **keine** Position offen zurückgelassen haben. Nicht
„wurde es versucht", sondern „ist es aus".

### (3) `Messwert.unbeurteilbar` — V3 an einer leicht zu übersehenden Stelle

`offen_geblieben` fehlt in Aufzeichnungen von vor seiner Einführung. Solche Läufe sagen
über den Ausstieg **nichts**. Sie als sauber zu zählen ersetzte einen fehlenden Messwert
durch einen Standardwert — und zwar durch den schmeichelnden; als gescheitert zu zählen
wäre ebenso falsch, nur in die andere Richtung.

Sie stehen deshalb **nicht im Nenner** und werden **angezeigt**. Ein Anteil aus 8
Vorgängen, während 11 weitere gar nicht beurteilbar waren, sagt etwas anderes als ein
Anteil aus 19; sie stillschweigend wegzulassen wäre dieselbe Lüge wie sie mitzuzählen.

### (4) Alarmregel + Handlungsanweisung

`position_offen_geblieben` → `RUNBOOK.md` §„Position offen geblieben". Der Abschnitt
stellt die Reihenfolge um, die bei diesem Alarm zählt: **erst im Terminal nachsehen und
entscheiden, dann Ursachensuche.** Was das Journal sagt, ist was der Lauf *wusste*; was
der Broker sagt, ist was *ist*.

---

## 4. Zur Schwelle — offen gesagt

Das neue Ziel steht auf **1,00, also ohne Fehlerbudget**. Bei den anderen drei ist ein
Restanteil vertretbar; hier nicht: es gibt keinen Anteil an unbeaufsichtigt am Markt
stehendem Geld, der in Ordnung wäre.

**Diese Schwelle wurde nach der Messung gesetzt.** Das steht so in der Begründung im Code
und wird hier nicht anders dargestellt. V6 verbietet, eine Schwelle nachträglich zu
bewegen, damit ein Ergebnis passt — diese ist **strenger** als der Befund (75,0 %) und
lässt ihn deutlicher durchfallen, als jede vorher plausibel gesetzte Zahl es getan hätte.
Eine nachträgliche Verschärfung ist nicht die Anpassung, gegen die V6 gebaut ist.

Die drei Schwellen aus Stufe 10 sind **unverändert**.

---

## 5. Was das an den Zahlen ändert — und was nicht

Beleg [`dienstguete-nach-ausstiegsdeckung.txt`](belege/dienstguete-nach-ausstiegsdeckung.txt).

| Ziel | Ist | Soll | Fehlerbudget verbraucht |
|---|---:|---:|---:|
| Buchtreue | 98,5 % (1.340/1.360) | 99,0 % | 147 % |
| Ausstiegsverlässlichkeit | 78,8 % (26/33) | 95,0 % | 424 % |
| Laufabschluss | 90,5 % (19/21) | 95,0 % | 190 % |
| **Ausstiegsdeckung** *(neu)* | **75,0 % (6/8)** | **100 %** | kein Budget |

**Die historischen Zahlen sind unverändert und bleiben es.** Die Journale werden nicht
umgeschrieben (E-007); 78,8 % ist und bleibt, was am 2026-08-17 gemessen wurde. Was sich
geändert hat, ist nicht die Vergangenheit, sondern

* dass **Klasse B nicht wieder auftreten kann** — der Riegel greift vor dem ersten Takt,
* und dass der Fall, den keine Kennzahl sah, jetzt **eine eigene Kennzahl, eine
  Alarmregel und eine Handlungsanweisung** hat.

Von den sieben Fehlschlägen sind damit **alle sieben ursächlich adressiert**: zwei durch
einen Fix, der seit dem 17.08. steht und gepinnt ist, fünf durch den neuen Riegel. Die
Zahl selbst wird erst ein Betrieb bewegen, der stattgefunden hat.

---

## 6. Was schiefging

**Ein nicht reproduzierbarer Fehlschlag, dem ich nachgegangen bin.**
`test_live_betrieb_sperren.py::test_ein_reconcile_halt_aus_einer_erkannten_schliessung_wird_aufgeloest`
fiel einmal mit `AttributeError: 'HaltVenue' object has no attribute 'get_instrument'`
und war in drei unmittelbar folgenden Läufen grün.

Nach der Lehre aus F-013 („ein einzelner, nicht reproduzierbarer Fehlschlag ist kein
Rauschen") habe ich zuerst geprüft, ob **meine** Änderung ihn verursacht: `git stash` →
grün, `git stash pop` → nicht mehr reproduzierbar. Er ist **nicht** von dieser Arbeit
verursacht.

Die Ursache ist dieselbe Krankheit wie F-013, eine Ebene tiefer: der Hilfsaufruf `_takt`
in jener Testdatei ruft `takt(...)` **ohne** `jetzt=`-Parameter, während die vier
Geschwister derselben Datei `jetzt=T0` übergeben. Ohne ihn nimmt `takt` die Wanduhr, und
ob der Takt nach dem aufgelösten Halt weiter in `run_signal` läuft — und dort auf die
absichtlich unvollständige Attrappe trifft — hängt von der realen Uhrzeit ab. Der
Fehlschlag trat um 00:07 Ortszeit auf.

Das ist ein **eigener Befund, außerhalb dieses Auftrags** und als eigene Aufgabe
festgehalten, statt hier den Rahmen zu erweitern.

**Zwei Testfälle fielen durch die neue Metrik** — korrekt: sie zählten den Messwertsatz
von Hand auf, und `pruefe_alarme` wirft bei einer fehlenden Metrik. Genau die Fehlrichtung,
für die dieser Wurf gebaut wurde. Der Hilfssatz wird jetzt aus `METRIKEN` abgeleitet; ein
Testwerkzeug, das denselben Fehler ein zweites Mal machen kann, ist eins zu viel.

---

## 7. Abnahme

Beleg [`ausstieg-tests.txt`](belege/ausstieg-tests.txt) — `tests/test_ausstiegsdeckung.py`,
**11 Fälle, alle grün**, rot und grün je Eigenschaft (V4):

| Eigenschaft | rot | grün |
|---|---|---|
| Der Riegel | der gemessene Fall vom 17.08. wird abgewiesen | ohne offene Position / mit `--scharf` / mit `--am-ende-offen-lassen` |
| Der Riegel hängt im Werkzeug | Aufruf steht vor `adopt_book()`, Abbruch endet mit `return 2` | — |
| Die Metrik | ein Lauf mit offener Position zählt nicht als sauber | lauter saubere Läufe ergeben volle Deckung |
| V3 | ein fehlendes Feld zählt **nicht** als sauber (Nenner bleibt 1, `unbeurteilbar` = 2) | — |
| Auf echten Daten | die Regel schlägt auf den 21 Journalen wirklich an | — |
| Bindungen der Regel | Metrik, Runbook-Abschnitt, Schwelle = Ziel | — |
| Kein Fehlerbudget | `verbraucht` gibt `None` statt durch null zu teilen | — |

Elf Tore je Exit 0 — ruff, mypy `--strict`, `check_docs_claims`, `check_doc_numbers`,
`gen_docs --check`, `kopien_abgleichen`, `aufzeichnung_redigieren`, `torzaehlung`,
Mutationstor (**16/16, Tötungsrate 1,000**), Zweigdeckung (**jede Geldpfad-Datei über
80 %**), `pytest` (**1.598 Fälle grün**).

---

## 8. Was dieser Nachtrag ausdrücklich nicht behauptet

* **Die Ausstiegsverlässlichkeit ist nicht „repariert".** Sie ist aufgeschlüsselt, und
  beide Ursachen sind adressiert. Ob die Zahl steigt, sagt erst ein Betrieb, der
  stattgefunden hat — und dieser Stand hat seit dem 17.08. nicht gehandelt.
* **Der Riegel ist gegen die Attrappe geprüft, nicht am Terminal.** Ein verbundenes
  Demokonto liegt weiterhin nicht vor.
* **Kein Vorteil.** Befund (B) aus Stufe 3 steht unverändert.
