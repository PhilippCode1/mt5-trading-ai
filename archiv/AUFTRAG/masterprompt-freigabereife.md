# Dauerauftrag: Handelssystem auf Freigabereife

**Einfügen in Claude Code. Unverändert. Beliebig oft.**
Dieser Text ist kein Einzelauftrag, sondern ein Dauerauftrag. Du startest ihn immer wieder mit demselben Wortlaut. Der Fortschritt liegt nicht in deinem Kontext, sondern in `AUFTRAG/zustand.md` im Arbeitsverzeichnis.

---

## Bismillah.

---

## 0 · Was du nicht anstreben sollst

Du wirst diesem Auftrag entnehmen wollen, dass das Ziel „Note 10 in allen Bereichen" lautet. Das ist es nicht, und der Grund steht im Prüfbericht, den dieses Projekt über sich selbst erstellt hat: Kein einziger der sechzehn Bereiche hat dort ein Potenzial über 8. Der Mittelwert aller ausgewiesenen Potenzialdeckel ist 6,94. Der Rest ist nicht Code, sondern mehrjährige Betriebshistorie, echte Antworten eines zugänglichen Handelsplatzes und ein Vorteil nach Kosten, der entweder existiert oder nicht.

**Du darfst dir keine Note geben, keine Note behaupten und keine Note anstreben.** Wenn du an irgendeiner Stelle dieses Auftrags feststellst, dass eine Handlung eine Kennzahl verbessert, ohne die zugrunde liegende Wirklichkeit zu ändern, ist das der Beweis, dass du die Handlung nicht ausführen darfst.

Dasselbe Projekt hat dokumentiert, woran es krankt: Module ohne Aufrufer, Gates ohne Auslösung, Kennzahlen, die die eigene Ausgabe messen, eine Absicherungsmaschinerie, die umfangreicher ist als das, was sie absichern soll. Ein Auftrag, der eine Note verlangt, verstärkt genau das. Dieser Auftrag verlangt stattdessen Belege.

---

## 1 · Das Ziel

Der Auftrag ist erfüllt, wenn **eine** der beiden folgenden Aussagen belegt ist:

**(A)** Es existiert ein positiver Erwartungswert nach Kosten, out-of-sample, auf unabhängig beschaffter Historie, auch unter 1,5-facher Kostenannahme — ausgewiesen mit Trefferzahl, Konfidenzintervall, Regime, Zeitrahmen und Stand des Versuchszählers.

**(B)** Es existiert keiner. Belegt mit demselben Apparat, denselben Daten, derselben Vorregistrierung.

**Beide Ergebnisse sind Erfolg.** (B) beendet den Auftrag ebenso gültig wie (A) — und zwar, bevor weiterer Aufwand in Absicherung, Ausführung, Oberfläche oder Betrieb fließt. Ein System, dessen Vorteil widerlegt ist, wird nicht abgesichert. Es wird zurückgebaut oder aufgegeben.

Alles andere in diesem Auftrag ist Vorbedingung dafür, dass (A) oder (B) überhaupt aussagekräftig gemessen werden kann.

---

## 2 · Stufe 0 — bevor du irgendetwas anfasst

Es gibt begründeten Zweifel, welches Repository den lebenden Stand trägt. Ein Prüfbericht vom 19.08.2026 bewertet `bitget-btc-ai`. Ein Vermerk vom 12.08.2026 hält fest, dass `mt5-trading-ai` an dessen Stelle getreten ist und dass Bitget-Anbindung, OpenAI-Anbindung und News-Engine gestrichen wurden. Der Bericht bewertet genau diese drei ausführlich.

**Erster Arbeitsschritt, vor jeder Änderung:**

1. Stelle fest, welche Repositories und Arbeitsverzeichnisse tatsächlich vorliegen. Zähle je Kandidat: letzter Commit mit Datum, Anzahl Commits der letzten 30 Tage, Zeilen Produktionscode, Anzahl Dienste, ob der Handelsplatz-Adapter Bitget oder MT5 ist.
2. Schreibe das Ergebnis als Tabelle nach `AUFTRAG/stufen/00-bestand/bericht.md`.
3. Entscheide begründet, welcher Stand der lebende ist, und trage die Entscheidung samt verworfener Alternative in `AUFTRAG/entscheidungen.md`.
4. **Halte an und beende den Lauf**, wenn beide Stände tragende, nicht ineinander überführbare Substanz enthalten — etwa wenn in dem einen ein funktionierender Simulator und in dem anderen die aktuelle Ausführungsstrecke liegt. Trage das nach `AUFTRAG/haltepunkte.md` mit einer klaren Empfehlung und dem, was du gemessen hast. Das ist keine Niederlage, sondern der einzige Punkt, an dem eine falsche Wahl Monate kostet.

Läuft alles auf einen Stand hinaus: weiter mit Stufe 1. Der aufgegebene Stand wird nicht gepflegt, nicht mitgeschleppt und nicht „für später" behalten. Notiere in `AUFTRAG/geloescht.md`, was du stehenlässt und warum.

---

## 3 · Deine Vollmacht

Du entscheidest technisch selbst und fragst nicht nach. Ausdrücklich erlaubt und erwünscht:

- Module, Dienste, Bibliotheken und ganze Verzeichnisbäume **löschen**, wenn sie keinen Aufrufer im Ausführungspfad haben.
- Die Basis ändern: Datenmodell, Schemata, Ereignisfluss, Dienstschnitt, Abhängigkeiten, Sprachen. Wenn die Grundlage das Ziel nicht trägt, baust du die Grundlage um, statt darauf weiterzubauen.
- Ein Modul **neu bauen statt reparieren**, wenn der Neubau gegen einen engeren Vertrag weniger Aufwand ist als die Reparatur. Kriterium hinschreiben, nicht Gefühl.
- Doppelte Implementierungen auflösen, indem du **die hergeleitete behältst und die geratene entfernst** — nie umgekehrt, und nie beide.
- Tests löschen, die nichts prüfen. Ein Test, dessen Gegenstand keinen Produktionsaufrufer hat, ist kein Vermögenswert, sondern eine Falschaussage.
- Deckungs- und Qualitätstore umhängen, sodass sie den Geldpfad messen statt unbenutzten Code.

Versunkene Kosten zählen nicht. Etwas, in das viel Arbeit geflossen ist und das sich als tragend falsch erweist, wird gelöscht, nicht gerettet.

**Vollständiger Neuaufbau des gesamten Projekts** ist erlaubt, aber nur nach ausdrücklichem Befund: der Prüfbericht weist Architektur und Codequalität als den einzigen Bereich über 4 aus (5/10, bester Wert der Erhebung), mit einem bemerkenswert zyklenarmen Importgraphen über 723 Module. Wenn du das wegwirfst, wirfst du die einzige belegte Stärke weg. Begründe einen solchen Schritt in `AUFTRAG/entscheidungen.md` mit Messwerten, bevor du ihn tust.

---

## 4 · Wo du anhältst

Du beendest den Lauf mit einem Eintrag in `AUFTRAG/haltepunkte.md` — Sachlage, was du gemessen hast, deine Empfehlung, die Alternative — bei:

- **Geld.** Kostenpflichtige Datenquellen, Lizenzen, Dienste, Infrastruktur. Vorher freie und unabhängige Quellen ausschöpfen und das dokumentieren.
- **Zugangsdaten.** Widerruf, Neuausstellung, Rechtetrennung an einem Börsen- oder Anbieterkonto kann nur der Auftraggeber. Du meldest es, du versuchst es nicht.
- **Handelsplatz und Instrument.** Wechsel des Brokers, der Anlageklasse oder der Instrumentenart ist eine Geschäfts-, keine Technikentscheidung.
- **Rechtliche und aufsichtliche Grenzen.** Nenne sie früh, mit Quelle und Datum, und liefere die tragfähige Alternative gleich mit. Bekannt und hart: ESMA-Hebelgrenzen für Privatanleger, Krypto 2:1. Eine Grenze wird nie verschoben, damit etwas durchgeht.
- **Dem Ergebnistor aus Abschnitt 6, Stufe 3.**
- **Der offenen Halal-Vorfrage.** Ob die gewählte Instrumentenart tragfähig ist, entscheidet der Auftraggeber; die Produktbezeichnung eines Brokers ist dabei kein Beleg. Wenn deine Arbeit an einer Stelle davon abhängt, meldest du es, statt es zu unterstellen.

Alles außerhalb dieser Liste entscheidest du selbst. Halte nicht an, um eine Erlaubnis einzuholen, die die Richtung nicht ändert.

---

## 5 · Sperren

Diese Verbote sind aus den zehn Mustern des Prüfberichts abgeleitet. Jedes beschreibt einen Fehler, den dieses Projekt nachweislich schon gemacht hat.

**V1 — Kein Code ohne Wirkung.** Neuer oder geänderter Code, für den du beim Abschluss der Stufe keinen Importpfad von einem Diensteinstiegspunkt bis zur Funktion nachweisen kannst, wird vor dem Abschluss gelöscht. Der Nachweis ist der Pfad, nicht die Behauptung.

**V2 — Kein Selbstbezug.** Keine Kennzahl speist sich aus der eigenen früheren Ausgabe. Kein Modell wird gegen eine Größe verglichen, die sein eigenes Eingabemerkmal ist. Kein Test rechnet die Implementierungsformel nach.

**V3 — Fehlender Wert sperrt.** Wo fail-closed behauptet wird, gilt fail-closed. Ein fehlender Messwert erzeugt niemals einen Standardwert, niemals eine übersprungene Prüfung, niemals „unauffällig". Er erzeugt eine Ablehnung mit benanntem Grund.

**V4 — Kein Gate ohne Auslösenachweis.** Jede Sperre braucht (a) einen Test, der sie tatsächlich rot färbt, (b) einen Test, der sie grün passieren lässt, (c) einen Betriebszähler je Ablehnungsgrund. Fehlt eines davon, ist die Sperre nicht fertig.

**V5 — Keine Sperre blockiert den Risikoabbau.** Reduzierende Aufträge sind von globalem Halt, Liquiditätswächter und Ersetzungssperre ausgenommen. Eine Infrastrukturstörung darf niemals eine offene Position einfrieren.

**V6 — Der Maßstab steht vor der Messung.** Schwellen werden vorher schriftlich festgelegt und danach nicht verhandelt. Eine Schwelle wird nie gesenkt, damit etwas durchgeht. Wenn zwei Schwellen für dieselbe Sache existieren, gilt die strengere, und die schwächere wird gelöscht.

**V7 — Keine Geheimnisse.** Du liest keine `.env`-Datei und keine Zugangsdatendatei zum Zweck der Ausgabe, du kopierst sie nicht, du zitierst keinen Wert, du schreibst keinen Wert in Bericht, Log, Commit oder Testdaten. Wenn du feststellst, dass Zugangsdaten im Klartext liegen, meldest du **das Faktum und den Dateipfad**, niemals den Inhalt.

**V8 — Kein echter Handel.** Kein Netzzugriff auf einen Live-Handelsendpunkt, keine echte Order, keine Umgehung geografischer oder aufsichtlicher Zugangsbeschränkungen. Demo- und Papierumgebungen sind erlaubt und erwünscht.

**V9 — Keine Behauptung ohne prüfbaren Beleg.** Jede Aussage in Doku, Bericht oder Commit-Nachricht trägt entweder eine ausführbare Belegstelle oder die Kennzeichnung „gelesen, nicht ausgeführt".

**V10 — Nichts aus der Liste in Abschnitt 8.**

---

## 6 · Belegregeln

- **Messen statt annehmen.** „Bestätigt durch Ausführung" schreibst du nur mit beigefügter Ausgabe. Sonst heißt es „gelesen, nicht ausgeführt".
- **Zahlen statt Adjektive.** Nicht „deutlich besser", sondern „von 0,075 auf 0,0001". Schätzungen kennzeichnest du als Schätzung.
- **Bezugsgröße immer hinschreiben.** „12 von 137 Eintrittspunkten", nie „die meisten". Der Beleg muss dieselbe Menge zählen wie der Befund.
- **Laut scheitern.** Eine Prüfung, die ihren Gegenstand nicht findet, meldet das und besteht nicht.
- **Über alle Instanzen messen.** Inhaltsabhängige Größen misst du an jeder Instanz, nie am Vertreter.
- **Abgelesenes von Erwartetem trennen.** Was du gemessen hast und was du erwartet hattest, stehen getrennt.
- **Überraschendes erst verstehen.** Ein unerwartet gutes Ergebnis ist ein Verdachtsfall, kein Erfolg. Suche zuerst den Fehler, der es erklären würde.
- **Eigene Fehler klar benennen.** Wenn du in einem früheren Lauf etwas falsch gemacht hast, steht das im Bericht, bevor die Korrektur steht.
- **Den billigsten entscheidenden Test wählen.** Nicht den umfassendsten.
- **Eigene Entscheidungen als eigene kennzeichnen.** Was du entschieden hast, ist nicht dasselbe wie was dir vorgegeben wurde.

---

## 7 · Reihenfolge

Bindend nach Abhängigkeit, nicht nach Aufwand. Eine Stufe beginnt erst, wenn die Abnahme der vorigen belegt im Abschlussordner liegt. Innerhalb einer Stufe entscheidest du Vorgehen und Zerlegung selbst.

### Stufe 0 — Bestand und Wahl des Stands
Siehe Abschnitt 2. **Abnahme:** Tabelle über alle Kandidaten mit gemessenen Zahlen; eine begründete Wahl in `entscheidungen.md`.

### Stufe 1 — Historie beschaffen
Mindestens drei Jahre feiner Kursdaten aus einer vom Handelsplatz unabhängigen Quelle, versioniert und gehasht, mit Lücken- und Ausreißerbericht. Kaltstartmenge und Aufbewahrungsfrist so ändern, dass Historie nicht laufend gelöscht wird.
**Abnahme:** ein eingecheckter Datensatzverweis mit Hash, Zeitraum, Zeilenzahl je Zeitrahmen und Qualitätsbericht; die Datenqualitätsprüfung liefert eine Zahl statt „unbekannt".
**Ohne diese Stufe ist jede folgende gegenstandslos.** Kosten meldest du als Haltepunkt, nachdem du die freien Quellen ausgeschöpft hast.

### Stufe 2 — Zeitschranken schließen
Alle Querabfragen, die „neuester Datenbankzustand" statt „Zustand zum Zeitpunkt des Bars" lesen, bekommen eine obere Zeitgrenze. Bestätigungszeitstempel auf Schlusszeit statt Startzeit. Feature-Verbund darf nie in die zum Entscheidungszeitpunkt laufende Kerze greifen.
**Abnahme:** ein Determinismus-Tor, das denselben Kursabschnitt zweimal verarbeitet — einmal chronologisch, einmal mit bereits vorhandenen späteren Zeilen — und Byte-Gleichheit erzwingt. Nachweis, dass es rot wird, sobald du eine Zeitschranke wieder entfernst. Ohne diesen roten Eichfall ist die Stufe nicht abgenommen.

### Stufe 3 — Simulator und Ergebnistor
Ein ereignisgetriebener Simulator, der die Entscheidungskette gegen die Historie fährt und je hypothetischem Trade Einstieg, Ausstieg, Gebühren, Spread, Slippage, Finanzierungskosten, Teilausführungen und Entscheidungslatenz ausweist. Rechenfehler in geldnahen Größen — Maximalverlust, Stückzahlberechnung, Kennzahleinheiten — vorher korrigieren, mit rotem Eichfall je Korrektur.

**Vor dem ersten Lauf** schreibst du nach `AUFTRAG/vorregistrierung/<datum>.md`: Mindestzahl Trades, Mindest-Erwartungswert nach Kosten, Signifikanzmaß, Kostenannahme einschließlich der 1,5-fachen, Zahl der bereits unternommenen Versuche. Diese Datei wird danach **nicht mehr geändert**. Jeder Lauf — auch ein abgebrochener — schreibt vor der Ergebnisausgabe einen Eintrag in `AUFTRAG/versuchsregister.jsonl`. Ohne Registereintrag kein Ergebnis.

**Das Ergebnistor:** Fällt das Ergebnis unter die vorregistrierte Schwelle, ist das der Befund (B) aus Abschnitt 1. Du justierst dann nicht nach, du suchst keine bessere Parametrierung, du erweiterst nicht den Suchraum. Du hältst an, meldest es als Haltepunkt mit vollständigen Zahlen und beendest den Lauf. Jede Parameteränderung nach Kenntnis des Ergebnisses ist ein neuer Versuch und erhöht den Versuchszähler, der in die Signifikanzrechnung eingeht — schreibe das in den Bericht, damit die Versuchung sichtbar bleibt.

**Abnahme bei (A):** Netto-Erwartungswert je Regime und Zeitrahmen mit Konfidenzintervall und Trefferzahl, auch unter 1,5-facher Kostenannahme, gegen den vorregistrierten Maßstab, mit Versuchszählerstand.

### Stufe 4 — Risikokern verdrahten und fail-closed stellen
Sicherheitsriegel in eine eigene Zustandstabelle statt in ein Protokoll. Jede fehlende Pflichtkennzahl blockiert, statt übersprungen zu werden. Portfoliozustand serverseitig aus den eigenen Beständen ableiten, nie aus der Anfrage. Reduzierende Aufträge von allen Sperren ausnehmen. Genau eine Größenberechnung und ein Stopbudget behalten.
**Abnahme:** zwei aufeinanderfolgende Eröffnungsaufträge werden **beide** abgelehnt; leere Kontodaten erzeugen eine Ablehnung mit Grund; bei erzwungenem Halt scheitert die Eröffnung und der Ausstieg läuft trotzdem. Je Tor ein roter und ein grüner Eichfall.

### Stufe 5 — Ausführungserfahrung erzeugen
Gegen die Demoumgebung: Platzierung, Abbruch, doppelte Auftragskennung, falsche Signatur, abweichende Uhr — als redigierte Aufzeichnungen einchecken. Nicht-endgültigen Zustand „Antwort blieb aus, Auftrag könnte leben" einführen, der sichtbar bleibt und vor der nächsten Eröffnung aufgelöst werden muss.
**Abnahme:** mindestens eine echte, aufgezeichnete Antwort des Handelsplatzes liegt im Repo; drei Testfälle sichern Datenbankzustand, genau einen Auftrag beim Gegenüber und den Riegelzustand zu.

### Stufe 6 — Modellpfad schließbar machen
Beförderung standardmäßig aus. Artefakt erreicht den auswertenden Dienst und überlebt Neustarts. Freigabeteilung auf den gesäuberten Vorwärtstest. Trainingsmindestmenge in ein Verhältnis zur Merkmalszahl setzen. Trainingsendpunkte authentifizieren. Überlappende Zielwerte gewichten.
**Abnahme:** ein Trainingslauf erzeugt einen Herausforderer im Wartezustand, nicht einen Champion; ein falscher Schemahash führt zum Verwerfen; das Artefakt ist nach Neustart noch da.

### Stufe 7 — Kaltstart öffnen
Der Kreis „ohne Modell keine Entscheidung, ohne Entscheidung keine Daten, ohne Daten kein Modell" wird aufgebrochen: protokollierter Erkundungspfad im Papierkonto mit mitgeschriebenen Ablehnungsgründen, Gewichtung nach Auswahlwahrscheinlichkeit im Training, Herkunftsspalte in den Auswertungen. Schwellen, die exakt auf dem Maximum der Ersatzheuristik liegen, davon entkoppeln.
**Abnahme:** die Auswertungstabelle enthält gekennzeichnete Zeilen aus abgelehnten Signalen; ein Trainingslauf weist den Anteil erkundender Beobachtungen aus.

### Stufe 8 — Testwirkung statt Testdeckung
Mutationstor auf die kritischen Dateien des Geldpfads mit einer Tötungsrate als blockierender Schwelle. Für jede Datei im Sicherheitsverzeichnis den Importpfad vom Diensteinstiegspunkt nachweisen — sonst rot. Negativtests für jeden Prüfer. Deckung von Zeilen auf Zweige je Datei.
**Abnahme:** die Mutationssonden färben den Lauf rot; keine Testdatei prüft mehr eine Funktion ohne Produktionsaufrufer.

### Stufe 9 — Tote Tore verdrahten oder löschen
Ohne Zwischenzustand. Für jede gelesene Größe entweder einen Schreiber schaffen oder den Leser entfernen. Typprüfungstor vom unbenutzten Code auf den Auftragspfad umhängen. Ein Werkzeug, das Tore ohne Auslösung im Betrieb meldet.
**Abnahme:** für jedes verbliebene Tor existiert ein Test, der es auslöst, und eine Betriebszählung je Ablehnungsgrund.

### Stufe 10 — Betrieb und Analystenpfad absichern
Erst hier: Alarmzustellung bis zu einem Menschen, Handlungsanweisungen für jede Alarmregel, Dienstgütezielе mit Fehlerbudget, geprobter Wiederanlauf. Fremdtext an ein Sprachmodell nur in einem markierten, längenbegrenzten, normalisierten Datenblock; von einem Sprachmodell gesetzte Werte lösen niemals allein eine Marktschließung aus.
**Abnahme:** ein Testsatz manipulierter Schlagzeilen verschiebt keinen Entscheidungswert; ein simulierter Anbieterausfall unterdrückt keine Schutzfunktion; jede Alarmregel hat eine existierende Metrik und eine existierende Handlungsanweisung.

---

## 8 · Was nicht gebaut wird

Verbindlich. Aufwand hier verkleinert den Abstand zur Freigabe nicht.

- **Keine weiteren Entscheidungsschichten.** Keine zusätzlichen Spezialisten, Ensembles, Meta-Kerne, Konsensrunden. Jede Schicht erhöht nur die Zahl freier Parameter; das Projekt hat bereits mehrere hundert numerische Festwerte gegen eine Trainingsmindestmenge im zweistelligen Bereich.
- **Keine weiteren geteilten Bibliotheken oder Kontrollmodule ohne Verdrahtung.** Es liegen bereits mehrere tausend Zeilen ohne Diensteinbindung — handwerklich teils die besten des Projekts. Genau deshalb erzeugen sie den Eindruck durchgesetzter Kontrolle, die im Ausführungspfad nicht stattfindet.
- **Keine weiteren Broker-Adapter und keine zusätzlichen Handelsplätze.** Solange gegen den primären Handelsplatz keine einzige Order abgesetzt wurde, vervielfacht Breite nur die Zahl unbewiesener Pfade. Tiefe vor Breite.
- **Keine Fundamentmodelle, Inferenzserver, zusätzlichen Sprachmodell-Agenten.** Ein Stumpf, der den letzten Wert linear fortschreibt, darf nicht als Trainingsmerkmal in das handelsfreigebende Modell sickern. Richtig ist die Sperre im Konsumenten, nicht der Ausbau.
- **Keine Portierungen zur Beschleunigung.** Der Engpass ist kein Durchsatz. Das System hat nie gehandelt.
- **Keine zusätzliche Oberflächenfläche.** Weitere Anzeige macht einen unbelegten Zustand nur ausführlicher sichtbar. Bestehende Bedienpfade wirksam und zurechenbar zu machen ist Stufe 10; neue Flächen sind es nie.

Wenn du glaubst, eine dieser Sperren sei in deinem Fall falsch: das gehört als Haltepunkt gemeldet, nicht selbst entschieden.

---

## 9 · Vier Dinge, die du nicht erreichen kannst

Sie stehen hier, damit du sie nicht simulierst.

1. **Mehrjährige Betriebshistorie.** Datenqualität und Betriebsreife werden durch Zeit belegt, nicht durch Code. Du kannst die Aufzeichnung ermöglichen, nicht die Zeit.
2. **Echte Orderantworten von einem zugänglichen Handelsplatz.** Wenn der bisherige Handelsplatz im Wirtschaftsraum des Auftraggebers nicht mehr betrieben wird, ist das eine harte Grenze. Melden, nicht umgehen.
3. **Widerruf und Neuausstellung von Zugangsdaten.** Nur der Kontoinhaber.
4. **Einen Vorteil, der nicht existiert.** Wenn Stufe 3 (B) ergibt, ist das die Antwort. Sie zu überschreiben, wäre der größte Schaden, den dieser Auftrag anrichten könnte.

---

## 10 · Der Abschlussordner

`AUFTRAG/` liegt im Wurzelverzeichnis des gewählten Repositories und ist von außen abrufbar — bei Anbindung an eine Fernablage wird er nach jeder Stufe gepusht. **Er wird vor jedem Kontextende geschrieben, auch bei Abbruch, Absturz, Zeitmangel oder Fehlschlag.** Ein Lauf ohne aktualisierten Abschlussordner gilt als nicht stattgefunden.

```
AUFTRAG/
  zustand.md                    aktueller Stand, siehe Format unten
  stufen/<n>-<name>/
    bericht.md                  Ist, Getanes, Gemessenes, Abnahme
    belege/                     rohe Ausgaben, Prüfsummen, Aufzeichnungen
  vorregistrierung/<datum>.md   nach dem Schreiben unveränderlich
  versuchsregister.jsonl        append-only, auch abgebrochene Läufe
  entscheidungen.md             je Eintrag: Entscheidung, Begründung, verworfene Alternative
  haltepunkte.md                was nur der Auftraggeber entscheiden kann
  geloescht.md                  was entfernt wurde und warum
  fehler.md                     eigene Fehlgriffe samt Ursache
```

**Format von `zustand.md`:**

```
Stufe:            <n> — <Name>
Zustand:          laufend | abgenommen | angehalten | gescheitert
Zuletzt:          <Datum, Commit>
Abnahme belegt:   ja | nein — <Belegstelle>
Nächster Schritt: <ein Satz, so konkret, dass ein neuer Lauf ihn ohne Rückfrage aufnimmt>
Offene Haltepunkte: <Anzahl> — siehe haltepunkte.md
Ehrliche Restschätzung: <Zahl der verbleibenden Stufen und was daran unsicher ist>
```

---

## 11 · Rückmeldung am Ende jedes Laufs

Kurz, in dieser Reihenfolge, auf Deutsch:

1. **Was gemessen wurde** — mit Zahlen und Bezugsgröße.
2. **Was geändert wurde** — mit Commit und betroffenen Pfaden.
3. **Was abgenommen ist** — mit Belegstelle, oder ausdrücklich „gelesen, nicht ausgeführt".
4. **Was schiefging** — eigene Fehler zuerst.
5. **Haltepunkte** — was der Auftraggeber entscheiden muss, mit Empfehlung und Alternative.
6. **Nächster Schritt** — ein Satz.

Keine Zusammenfassung, die besser klingt als die Belege. Kein „erfolgreich abgeschlossen" ohne beigefügte Ausgabe. Wenn eine Stufe nicht fertig wurde, steht das in der ersten Zeile.

Ein Auftrag endet nicht mit einer Liste offener Punkte, die jemand anders aufnehmen soll. Was du im Rahmen der laufenden Stufe zu Ende bringen kannst, bringst du zu Ende, bevor du meldest.

---

## Bismillah.
