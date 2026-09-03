# RUNBOOK — Handlungsanweisungen je Alarmregel

*Entstanden in Stufe 10 des Dauerauftrags. Jede Regel in
`mt5_trading_ai/betrieb/dienstguete.py::ALARMREGELN` verweist auf **genau einen**
Abschnitt dieser Datei, und ein Dauertor prüft beides gegeneinander: eine Regel ohne
Abschnitt ist rot, ein Abschnitt ohne Regel auch.*

**Warum diese Datei existiert.** Ein Alarm ohne Handlungsanweisung weckt jemanden, der
dann nicht weiß, was zu tun ist — und beim dritten Mal schaltet er den Alarm ab. Der
Auftrag verlangt deshalb ausdrücklich „Handlungsanweisungen für jede Alarmregel", und
die Abnahme prüft, dass jede eine **existierende** hat.

**Was hier nicht steht.** Keine Zugangsdaten, keine Kontonummern, kein Broker-Support-
Kontakt. Diese Datei liegt im Repository; sie beschreibt Handgriffe, nicht Geheimnisse.

---

## Buchtreue unter Ziel

**Was der Alarm sagt.** Der Anteil der Takte ohne gesetzten Halt liegt unter 99 %. Das
lokale Buch und die Meldung des Handelsplatzes gehen zu oft auseinander, oder ein
Sendeversuch blieb unbeantwortet. Solange ein Halt steht, eröffnet der Lauf nichts mehr.

**Zuerst: hat der Halt überhaupt gesperrt?** Diese Frage steht vor allen anderen, weil
sie bei jedem zweiten Alarm die Antwort schon ist. Ein Reconcile-Halt, der im selben Takt
`halt_erklaert` mit `weiter_gesperrt: false` trägt, hat **nichts** blockiert: der Broker
hat zwischen zwei Takten eine Position geschlossen, der Reconcile sah sie noch im Buch
und sperrte fail-closed, der Abgleich löste im selben Takt auf. Das ist normaler
Marktbetrieb, kein Vorfall. Nur Takte **ohne** solche Auflösung zählen.

**Und danach: sitzt es im lebenden Code?** `python tools/dienstguete.py` zeigt unten die
Aufschlüsselung nach Codestand. Stammen die gesperrten Takte aus einem überholten Stand
oder aus einem mit `+aenderungen` (unsauberes Arbeitsverzeichnis), ist die Gesamtzahl
Geschichte und kein Auftrag. Ein Stand ohne `+aenderungen`, der Sperren zeigt, ist einer.

**Zuerst nachsehen.**

1. `python tools/betrieb_auswerten.py` — welche Takte tragen `halt=true`, und welcher
   Grund steht darin? `reconcile_drift:…` ist etwas anderes als `sendeversuch_unklar:…`.
2. Bei `sendeversuch_unklar:<Kennung>`: **zuerst beim Broker nachsehen**, ob zu dieser
   Kennung eine Order liegt. Erst danach weiter.
3. `python tools/modelllauf.py --ablage betrieb/herausforderer --lesen` ist hier
   irrelevant; die Schwebeakte liest man über den Betrieb.

**Was zu tun ist.**

- **Reconcile-Drift, Position beim Broker vorhanden, im Buch nicht:** Das Buch ist zu
  klein. `adopt_book()` beim nächsten Start übernimmt die Wahrheit des Brokers. Den Halt
  danach freigeben.
- **Reconcile-Drift, Position im Buch, beim Broker nicht:** Sie wurde serverseitig
  geschlossen (Stop, Margin, manuell). Das ist der häufigste Fall und harmlos — der Halt
  ist dann eine Übervorsicht. Freigeben.
- **Ungeklärter Sendeversuch:** Erst auflösen, dann freigeben. Die Auflösung verlangt
  einen Befund; „ich habe nichts gefunden" ist ein gültiger Befund, „ich habe nicht
  nachgesehen" nicht.

**Was ausdrücklich nicht zu tun ist.** Den Halt freigeben, ohne den Grund gelesen zu
haben. Die Freigabe ist kein Aufräumen, sondern die Behauptung, nachgesehen zu haben.

---

## Ausstieg misslingt

**Was der Alarm sagt.** Weniger als 95 % der Schließversuche gelingen. **Das ist der
ernsteste der drei Alarme:** ein misslungener Ausstieg lässt Geld am Markt, während das
System glaubt, es sei draußen.

**Zuerst nachsehen.**

1. Im Journal die Sätze `schliessen_fehlgeschlagen` — das Feld `fehler` trägt den
   **Wortlaut des Handelsplatzes**. „Trade disabled", „No money" und „Unsupported
   filling mode" sind drei völlig verschiedene Lagen.
2. Die offenen Positionen beim Broker gegen `book_snapshot()` halten.

**Was zu tun ist.**

- **„Trade disabled" / „AutoTrading disabled by client":** Der Schreibpfad ist am
  Terminal gesperrt. Kein Softwareproblem — im Terminal freigeben. Bis dahin **von Hand
  schließen**, nicht warten.
- **„Unsupported filling mode":** Die Füllart passt nicht zum Symbol. `_fuellart` in
  `venue/mt5.py` wählt sie je Symbol; der Broker hat die Spezifikation geändert.
- **„No money":** Die freie Marge reicht nicht einmal für die Schließung. Sofort von
  Hand eingreifen.
- **In jedem Fall:** Solange offene Positionen bestehen und der Ausstieg klemmt, ist der
  Not-Aus (`emergency_flatten`) der richtige Griff — er fährt Reduce-Only und wird von
  keiner Sperre blockiert.

**Was ausdrücklich nicht zu tun ist.** Auf den nächsten Takt hoffen. Ein Ausstieg, der
zweimal scheitert, scheitert auch beim dritten Mal.

---

## Position offen geblieben

**Was der Alarm sagt.** Ein Lauf wurde beendet, während eine Position noch offen stand.
**Das ist der ernsteste Zustand, den dieses System melden kann** — schlimmer als ein
misslungener einzelner Schließversuch, denn hier läuft anschließend *kein Prozess mehr*,
der die Position beaufsichtigt: keine Stop-Pflege, kein Abgleich, keine Höchsthaltedauer,
keine Verlustgrenze. Das Geld steht am Markt und niemand sieht hin.

**Sofort, vor jeder Ursachensuche.**

1. **Im Terminal nachsehen**, welche Positionen offen sind — nicht im Journal. Das Journal
   sagt, was der Lauf *wusste*; der Broker sagt, was *ist*.
2. Entscheiden: von Hand schließen oder bewusst stehen lassen. Beides ist vertretbar,
   „ich schaue morgen" ist es nicht.

**Erst danach: woran lag es.** Der `ende`-Satz führt die Symbole unter
`offen_geblieben`; die `schliessen_fehlgeschlagen`-Sätze davor tragen den Grund.

- **`Real-Terminal: Schreibpfad gesperrt (allow_write=False)`:** Der Lauf lief ohne
  `--scharf`, also ohne Schreibrecht, hatte aber offene Positionen übernommen. **Seit dem
  Startriegel kann das nicht mehr passieren** (`tools/live_betrieb.py`,
  `ausstiegszusage_pruefen`): ein Lauf ohne Schreibrecht, der ein Glattstellen zusagt,
  startet nicht mehr, solange Positionen offen stehen. Tritt es doch auf, ist der Riegel
  umgangen worden — dann ist das der eigentliche Befund.
- **`unbekannt` in der Liste:** Das Glattstellen selbst ist geworfen, der Lauf konnte
  nicht einmal mehr feststellen, was offen ist. Hier hilft nur das Terminal.
- **Wortlaut des Handelsplatzes:** siehe Abschnitt „Ausstieg misslingt" — dieselben
  Fälle, dieselben Griffe.

**Was ausdrücklich nicht zu tun ist.** Den nächsten Lauf starten, bevor die offenen
Positionen geklärt sind. Er übernimmt sie über `adopt_book()` und rechnet sie in seine
Grenzen ein, als hätte er sie selbst eröffnet.

**Warum dieses Ziel kein Fehlerbudget hat.** Bei den anderen drei ist ein Restanteil
vertretbar. Hier nicht: es gibt keinen Anteil an unbeaufsichtigt am Markt stehendem Geld,
der in Ordnung wäre. Jeder einzelne Fall ist einer zu viel.

---

## Läufe brechen ab

**Was der Alarm sagt.** Weniger als 95 % der Läufe enden mit einem `ende`-Satz. Ein Lauf
ohne Endsatz ist abgestürzt oder abgewürgt worden.

**Was er ausdrücklich NICHT sagt — bitte zuerst lesen.** Dieser Alarm ist **keine
Sicherheitsanzeige**. Gemessen an den 21 Journalen dieses Standes:

- Er zeigt in die **falsche** Richtung. Die beiden Läufe, die wirklich Geld am Markt
  ließen (`173413`: drei Positionen, `182800`: zwei), haben einen `ende`-Satz und zählen
  hier als **gelungen**. Der Lauf mit dem leeren Buch (`182951`) zählt als
  **gescheitert**.
- Er misst etwas, das die Software nicht steuert. Der längste Abbruch geschah, weil die
  Maschine elf Sekunden nach dem letzten Journalsatz in den Standby ging
  (Windows-Ereignisprotokoll, Kernel-Power 42). Bei `taskkill /F` läuft weder ein
  Signalhandler noch `atexit` noch ein `finally`-Block — gemessen.

**Wer wissen will, ob Geld unbeaufsichtigt stand, liest den Alarm „Position offen
geblieben".** Der sieht jeden Lauf, gleich wie er endete.

**Zuerst nachsehen.**

1. Welcher Lauf hat keinen `ende`-Satz? Der letzte Satz vor dem Abbruch sagt, wo er
   stand.
2. **Hat dieser Lauf eine Position hinterlassen?** Das ist die einzige Frage, die
   eilt. Öffnungen ohne zugehörige Schließung (`eroeffnungsversuch` mit
   `eroeffnet: true` gegen `geschlossen`/`vom_broker_geschlossen`) oder ein letzter
   `takt`-Satz mit nicht-leerem `positionen`. Steht dort etwas: weiter unter „Position
   offen geblieben", nicht hier.
   *Gemessen: genau so ist es am 17.08. passiert — `journal-20260817T150513` starb nach
   fünf Minuten mit drei offenen Positionen; ein Mensch bemerkte es 31 Sekunden später.
   Nachts wären daraus Stunden geworden.*

**Was zu tun ist.**

- **Absturz mit Ausnahme:** Der Wiederanlauf übernimmt das Buch über `adopt_book()`. Vor
  dem Neustart die Schwebeakte lesen: liegt dort eine Kennung, ist sie **vor** der
  nächsten Eröffnung aufzulösen — der Orderpfad sperrt sonst ohnehin.
- **Abwürgen von außen (Strg-C, Neustart der Maschine):** Dasselbe, ohne
  Ursachensuche.
- **Wiederholt derselbe Punkt:** `python tools/wiederanlaufprobe.py` fährt den
  Wiederanlauf als Probe und sagt, ob Zustand, Schwebeakte und Buch ihn überstehen.

**Was ausdrücklich nicht zu tun ist.** Neu starten, ohne die Schwebeakte gelesen zu
haben. Genau dafür ist sie da.

---

## Wenn die Zustellung selbst scheitert

Die Alarme werden in eine Datei geschrieben, die der Betrieb beobachtet, **und** auf die
Fehlerausgabe des aufrufenden Werkzeugs; das Werkzeug endet dann mit einem Rückgabewert
ungleich 0.

Es gibt bewusst **keinen Netzdienst** dahinter. Eine Zustellung, die still scheitert,
weil ein Anbieter nicht antwortet, ist schlechter als keine — sie erweckt den Eindruck,
jemand sei benachrichtigt worden. Schlägt das Schreiben der Datei fehl, wirft
`stelle_zu` und der Lauf endet laut.

**Wer das ändern will:** ein Kanal, der nicht bestätigt, dass ein Mensch die Nachricht
gesehen hat, ist keine Zustellung bis zu einem Menschen. Das ist die Latte.
