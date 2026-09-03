# Stufe 10 — Betrieb und Analystenpfad absichern

*Gefahren am 2026-08-20 auf Anweisung des Auftraggebers („stufe 10"). Belege in
[`belege/`](belege/), sechs Dateien. Bestätigt durch Ausführung — jede Ausgabe liegt bei.*

---

## 0. Zur Zulässigkeit — unverändert die Entscheidung des Auftraggebers

Es gilt weiter, was in [Stufe 4](../04-risikokern/bericht.md) §0 steht: §1 des Auftrags
schließt die Stufen 4–10 für den Ausgang (B) aus, der Auftraggeber hat sie angewiesen
(E-009). **Diese Stufe misst keinen Vorteil und behauptet keinen.**

---

## 1. Was gemessen wurde

Der Auftrag verlangt vier Dinge und nennt drei Abnahmesätze. Der Ist-Zustand vor dieser
Stufe, Punkt für Punkt:

| Forderung | vorher |
|---|---|
| Alarmzustellung bis zu einem Menschen | **fehlte ganz** |
| Handlungsanweisung je Alarmregel | **fehlte ganz** — es gab keine Alarmregeln |
| Dienstgüteziele mit Fehlerbudget | **fehlten ganz** |
| Geprobter Wiederanlauf | Mechanik vorhanden (Zustandsdatei, Schwebeakte), **nie am Stück geprobt** |
| Markierter Datenblock für Fremdtext an ein Sprachmodell | **kein Sprachmodellpfad, keine Schlagzeilenaufnahme** |

### Die drei Dienstgüte-Kennzahlen, aus den 21 echten Betriebsjournalen

Beleg [`dienstguete-ist.txt`](belege/dienstguete-ist.txt). Gemessen wurde an den
Journalen, die frühere Läufe hinterlassen haben — nicht an einem für diesen Zweck
erzeugten Datensatz (V2).

| Ziel | Ist | Soll | Fehlerbudget | verbraucht |
|---|---:|---:|---:|---:|
| Buchtreue | 98,5 % (1.340/1.360 Takte) | 99,0 % | 1,0 % | **147 %** |
| Ausstiegsverlässlichkeit | 78,8 % (26/33 Schließversuche) | 95,0 % | 5,0 % | **424 %** |
| Laufabschluss | 90,5 % (19/21 Läufe) | 95,0 % | 5,0 % | **190 %** |

**Alle drei Ziele sind verfehlt, alle drei Alarmregeln schlagen an.** Das ist der Befund
dieser Stufe, nicht ihr Scheitern. Die Ziele wurden **vor** der Messung gesetzt und mit
Begründung im Code festgeschrieben (`betrieb/dienstguete.py::ZIELE`); sie
nachträglich zu senken, bis sie passen, wäre genau die Schwellenverschiebung, die V6
verbietet.

Die schwerste der drei ist die mittlere: **jeder fünfte Schließversuch ist misslungen.**
Ein misslungener Ausstieg lässt Geld am Markt, während das System glaubt, es sei draußen.

---

## 2. Was gebaut wurde

### `mt5_trading_ai/betrieb/dienstguete.py`

Drei Metriken (je eine Funktion, die aus dem Journal rechnet), drei Ziele mit
Fehlerbudget und Begründung, drei Alarmregeln. Jede Regel nennt **ihre Metrik** und den
**exakten Abschnittstitel** ihrer Handlungsanweisung; beides wird von einem Dauertor
gegengeprüft.

`pruefe_alarme` **wirft**, wenn eine Regel auf eine Metrik zeigt, die es nicht gibt. Das
ist die Fehlrichtung, auf die es ankommt: eine Regel ohne Metrik darf nicht
stillschweigend als „kein Alarm" durchgehen — so entsteht die gefährlichste Anzeige des
Betriebs, alles grün, weil nichts gemessen wird.

`Messwert.anteil` gibt bei leerem Nenner `None` zurück, nicht 0 %. „Nichts gemessen" ist
etwas anderes als „alles gescheitert" (V3).

### `RUNBOOK.md`

Vier Abschnitte: einer je Alarmregel plus einer über den Zustellkanal selbst. Jeder Regel-
Abschnitt hat dieselbe Gliederung — *Was der Alarm sagt*, *Zuerst nachsehen*, *Was zu tun
ist*, *Was ausdrücklich nicht zu tun ist*. Der letzte Punkt ist der wichtigste: bei
„Buchtreue unter Ziel" steht dort, den Halt nicht ohne Lesen des Grundes freizugeben —
die Freigabe ist kein Aufräumen, sondern die Behauptung, nachgesehen zu haben.

### `tools/dienstguete.py` — die Zustellstelle

Erhebt, hält gegen die Ziele, rechnet das verbrauchte Fehlerbudget, schreibt jeden Alarm
in eine Datei **und** auf die Fehlerausgabe, und endet mit einem Rückgabewert ungleich 0,
sobald ein Alarm steht. Ein Werkzeug, das einen Alarm nur ausdruckt und mit 0 endet, wird
in jeder Automatik übersehen.

**Bewusst kein Netzdienst.** Eine Zustellung, die still scheitert, weil ein Anbieter nicht
antwortet, ist schlechter als keine — sie erweckt den Eindruck, jemand sei benachrichtigt
worden. Schlägt das Schreiben fehl, wirft `stelle_zu`, und der Lauf endet laut.

### `tools/wiederanlaufprobe.py` — der geprobte Wiederanlauf

Beleg [`wiederanlaufprobe.txt`](belege/wiederanlaufprobe.txt), **12 von 12 Prüfungen**.

Die Probe setzt Zustand (Drawdown-Halt gelatcht, Tageszähler, ungeklärter Sendeversuch),
lässt den Lauf **hart enden** — kein sauberes Herunterfahren — und baut einen zweiten Lauf
auf denselben Dateien.

Der Kern ist die Frage, die sie dem zweiten Lauf stellt: nicht „steht der Halt in einem
Feld", sondern **„hält er eine Eröffnung auf, bei wieder vollem Konto".** Ein Halt, den
man nur im Zustand sieht, der aber keine Order mehr aufhält, ist keiner. Und die
Erholung ist der Fall, an dem eine naive Fassung scheitert: sie fände nichts mehr zu
halten und ließe durch.

Gemessen: der Halt wirkt (`risk_drawdown_halt_gelatcht`), der Grund überdauert mit, der
ungeklärte Sendeversuch überdauert, die Auflösung ohne Befund wird abgewiesen, und erst
die menschliche Freigabe löst ihn.

Ausdrücklich festgehalten, was **nicht** überdauert: **das Buch.** Es kommt beim Start vom
Handelsplatz (`adopt_book`). Eine gespeicherte Fassung wäre eine zweite Wahrheit neben der
des Brokers — und bei Abweichung gewinnt immer der Broker, weil dort das Geld liegt.

---

## 3. Der erste Abnahmesatz, ehrlich gefahren

> *ein Testsatz manipulierter Schlagzeilen verschiebt keinen Entscheidungswert*

Es gibt in diesem Stand **keinen Sprachmodellpfad und keine Schlagzeilenaufnahme**. §8 des
Auftrags verbietet ausdrücklich, „weitere geteilte Bibliotheken oder Kontrollmodule ohne
Verdrahtung" zu bauen — einen Bereiniger für einen nicht existierenden Pfad zu schreiben
wäre genau das, und wäre obendrein der Eindruck durchgesetzter Kontrolle, die nicht
stattfindet.

Also wurde die Eigenschaft **an der bestehenden Grenze gemessen statt an einer neu
gebauten**: zehn manipulierte Schlagzeilen (Anweisungsübernahme, Stimmungstext,
eingeschmuggelte Zahlen, Steuerzeichen, Überlänge, Homoglyphen, als CSV getarnte Zeile)
werden dort hineingegeben, wo Text im System überhaupt hereinkommt, und der
Entscheidungswert wird vorher/nachher verglichen.

Beleg [`schlagzeilen-messung.txt`](belege/schlagzeilen-messung.txt):
**Entscheidungswerte verschoben: 0 von 10.**

Der Entscheidungswert ist dabei nicht nur die Kennzahl am Ende, sondern die **Folge der
Signale** plus Nettoergebnis, Trade-Zahl und Trade-Protokoll. Eine Manipulation, die den
Weg verschiebt, aber zufällig auf dieselbe Endzahl kommt, wäre sonst unsichtbar.

### Was dabei gefunden wurde

Neun Schlagzeilen sterben an Feldzahl und Typen. Die zehnte — **als CSV-Zeile getarnt, mit
sechs gültigen Feldern** — kommt an `from_csv` vorbei: `from_csv` prüft Feldzahl und
Typen, aber **keine Reihenfolge der Zeitstempel**. Gehalten wird sie eine Schicht höher,
in `load_verified_csv`, und dort **zweifach**:

1. **Sicherung 1, Herkunft:** die Prüfsumme weicht ab — die Datei wurde nach dem
   Festschreiben verändert.
2. **Sicherung 2, Struktur:** auch wenn der Angreifer die Prüfsumme *mitdreht* (neu
   signiertes Manifest), hält das Qualitätstor: `duplicate_timestamps`,
   `timestamps_not_monotonic`.

Der Befund ist **festgehalten statt geglättet**:
`test_rot_ohne_die_verifizierte_grenze_kommt_die_getarnte_zeile_durch` pinnt, dass
`from_csv` allein sie durchlässt, und begründet damit, warum die Abnahme an
`load_verified_csv` misst.

---

## 4. Der zweite Abnahmesatz: vier Anbieter, vier Ausfälle

> *ein simulierter Anbieterausfall unterdrückt keine Schutzfunktion*

Vier Anbieter können ausfallen, und jeder hat seine eigene milde Fehlrichtung. Die Probe
ist jedes Mal dieselbe: **sperrt es noch?**

| Ausfall | gemessenes Verhalten |
|---|---|
| Kursanbieter (`tick` liefert nichts) | `OrderRejectedError: … Frische nicht bewertbar` — nicht „Frische ok" |
| Handelsplatz (`order_send` antwortet nicht) | Schwebeeintrag gelatcht, Halt gesetzt; die **nächste** Eröffnung wird mit Nennung der Kennung gesperrt |
| Positionsauskunft (`positions` wirft) | Ausnahme **vor** dem Senden: `order_send_calls == 0` |
| Platte (Zustand nicht schreibbar) | Drawdown wird trotzdem bewertet, Halt latcht, Grund ist ein Drawdown-Grund |

Der letzte Fall ist der, den `risk_manager.py` als gemessenen Fehler dokumentiert: früher
kam der Schreibfehler **vor** der Limitauswertung, und ein Drawdown wurde während eines
Plattenausfalls gar nicht erst bewertet — erholten sich Platte und Equity, war die nächste
Order wieder genehmigt. Der Test prüft deshalb nicht nur, *dass* abgelehnt wird, sondern
**mit welchem Grund**.

### Die Gegenrichtung, und der Grund für den ganzen Abschnitt

„Unterdrückt keine Schutzfunktion" gilt in beide Richtungen: eine Sperre, die während
eines Ausfalls den **Ausstieg** blockiert, ist selbst der Schaden.
`test_v5_der_abbau_geht_trotz_ausfall_durch` setzt den Halt und schickt einen
reduzierenden Auftrag: er geht durch und kommt beim Broker an (`order_send_calls == 1`).

---

## 5. Der dritte Abnahmesatz: Regel ↔ Metrik ↔ Anweisung, in beide Richtungen

> *jede Alarmregel hat eine existierende Metrik und eine existierende Handlungsanweisung*

Geprüft wird in **beide** Richtungen: keine Regel ohne Abschnitt, und kein Abschnitt ohne
Regel. Ein verwaister Abschnitt verspricht eine Aufsicht, die es nicht gibt. Die eine
Ausnahme („Wenn die Zustellung selbst scheitert" beschreibt den Kanal, nicht eine Metrik)
steht namentlich im Test, damit sie nicht stillschweigend wächst.

**Das Tor hat beim allerersten Lauf einen echten Fehler gefunden:** die Regel
`laeufe_brechen_ab` zeigte auf `"Laeufe brechen ab"`, der Abschnitt heißt `"Läufe brechen
ab"`. Ein Alarm, der um einen Umlaut danebenzeigt, weckt jemanden ohne Anweisung. Der
Verweis ist auf den exakten Titel korrigiert, samt Kommentar an der Fundstelle.

Zusätzlich hält ein Fall die Schwelle **jeder Regel gegen das Ziel derselben Metrik** (V6)
— zwei Zahlen, die dasselbe bedeuten, an zwei Stellen sind die klassische Stelle, an der
eine davon später leise nachgibt.

---

## 6. Was schiefging

### F-014 — die Schlagzeilen-Messung war grün aus dem falschen Grund

Der erste Anlauf gab die Schlagzeilen an `from_csv` und war **10 von 10 grün**. Falsch:
`to_csv` endet mit einem Zeilenumbruch, also entstand beim Anhängen eine **Leerzeile**,
und die Ablehnung galt ihr — die Schlagzeile wurde nie gelesen. Alle zehn Ablehnungen
lauteten wortgleich `CSV-Zeile mit 1 Feldern: ''`.

Gefunden, weil die Meldung für alle zehn identisch war. Ein durchgehend gleiches Ergebnis
bei zehn völlig verschiedenen Eingaben ist kein Erfolg, sondern ein Hinweis, dass die
Eingabe gar nicht ankommt — der Verdachtsfall, den der Auftrag benennt. Nach der Korrektur
trat der eigentliche Befund hervor (§3).

### F-015 — mein Verdrahtungstor drängte auf schlechteren Code

Der Stufe-9-Fall „keine öffentliche Funktion ohne Aufrufer" meldete die drei neuen
Metriken als verwaist. Sie **werden** bei jedem Erheben gerufen — aber als Werte einer
Verteilertabelle (`METRIKEN`), nie als `buchtreue(...)`. Der Zähler sah nur `ast.Call`.

Ein Tor, das zu einer schlechteren Verdrahtung drängt — drei Funktionen in eine zu gießen,
nur damit ein Zähler steigt — misst das Falsche. Der Zähler zählt jetzt auch den Verweis,
**mit ausdrücklich benannter Grenze** im Docstring: ein Verweis belegt nicht, dass die
Tabelle selbst erreichbar ist. Dazu ein roter Eichfall
(`test_rot_eine_nirgends_erwaehnte_funktion_gilt_als_verwaist`), damit die Lockerung den
Fall nicht leerlaufen lässt.

### Kleinigkeiten

* Die README-Kennzahlen drifteten (42 Module, 1.372 Testfunktionen, 16.555 Zeilen) und
  ließen `check_doc_numbers.py` rot laufen — das Tor, das laut Erfahrungsspeicher **nicht**
  Teil von pytest ist. Nachgezogen.
* `MODULES.md` war nach dem neuen Modul veraltet; neu erzeugt.

---

## 7. Abnahme

Beleg [`abnahme-tests.txt`](belege/abnahme-tests.txt) — `tests/test_stufe10_betrieb.py`,
**40 Fälle, alle grün**, jeder Abnahmesatz mit rotem *und* grünem Eichfall (V4).

| Abnahmesatz des Auftrags | Fälle | Stand |
|---|---|---|
| Manipulierte Schlagzeilen verschieben keinen Entscheidungswert | 15 | erfüllt, an `load_verified_csv` gemessen |
| Simulierter Anbieterausfall unterdrückt keine Schutzfunktion | 5 | erfüllt, vier Ausfälle + Gegenrichtung V5 |
| Jede Alarmregel hat Metrik und Handlungsanweisung | 11 | erfüllt, beide Richtungen |
| Geprobter Wiederanlauf | 3 + 12 Proben | erfüllt |
| Dienstgüteziele mit Fehlerbudget | 6 | gebaut; **alle drei Ziele verfehlt** |

Das volle Tor-Set (elf Tore) ist gefahren — Beleg
[`tor-set.txt`](belege/tor-set.txt): ruff, mypy `--strict`, `check_docs_claims`,
`check_doc_numbers`, `gen_docs --check`, `kopien_abgleichen`,
`aufzeichnung_redigieren --pruefen`, `torzaehlung`, Mutationstor (**16/16, Tötungsrate
1,000**), Zweigdeckung (**jede Datei des Geldpfads über 80 %**), `pytest` (**1.587 Fälle
grün**).

---

## 8. Was diese Stufe ausdrücklich nicht behauptet

* **Kein Vorteil.** Befund (B) aus Stufe 3 steht unverändert.
* **Kein bewiesener Sprachmodell-Schutz.** Bewiesen ist, dass es **keinen Pfad gibt**, auf
  dem Fremdtext zu einem Entscheidungswert würde — und dass die Textgrenze hält. Käme je
  ein Sprachmodell hinzu, ist der markierte, längenbegrenzte, normalisierte Datenblock
  **dann** zu bauen; `backtest/llm_compare.py::evaluate_llm_gate` ist die fail-closed
  Zulassungsstelle davor.
* **Keine erreichten Dienstgüteziele.** Die Schicht misst; der Stand verfehlt alle drei.
  Eine Dienstgüteschicht, die auf den eigenen Daten sofort Alarm schlägt, misst etwas —
  aber sie hat noch nichts verbessert.
* **Keine Zustellung an einen erreichbaren Menschen im Ernstfall.** Zugestellt wird in
  Datei und Fehlerausgabe. Ein Kanal, der nicht bestätigt, dass ein Mensch die Nachricht
  gesehen hat, ist keine Zustellung bis zu einem Menschen — das steht so in `RUNBOOK.md`
  und bleibt offen.
* **Die drei fehlenden Aufzeichnungsfälle aus Stufe 5** (doppelte Auftragskennung *am
  Handelsplatz*, falsche Signatur, abweichende Uhr) brauchen weiterhin ein verbundenes
  Demokonto. Es existiert keine Terminalkonfiguration.
