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

## Läufe brechen ab

**Was der Alarm sagt.** Weniger als 95 % der Läufe enden mit einem `ende`-Satz. Ein Lauf
ohne Endsatz ist abgestürzt oder abgewürgt worden.

**Zuerst nachsehen.**

1. Welcher Lauf hat keinen `ende`-Satz? Der letzte Satz vor dem Abbruch sagt, wo er
   stand.
2. Steht eine Stoppdatei (`stoppdatei`-Satz)? Dann war es ein gewollter Abbruch und
   zählt hier fälschlich mit — das ist eine bekannte Ungenauigkeit der Metrik.

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
