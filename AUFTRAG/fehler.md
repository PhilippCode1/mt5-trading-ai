# Eigene Fehlgriffe

*Was der ausführende Agent falsch gemacht hat, samt Ursache. Nach §6 des Auftrags steht
das im Bericht, bevor die Korrektur steht.*

---

## F-001 — Ich habe die Doku gelesen, wo ich den Code hätte messen müssen

**Stufe:** 0 · **Datum:** 2026-08-19 · **Folge:** keine, rechtzeitig bemerkt

**Was passiert ist.** `FEHLT.md` im gewählten Stand führt unter „die Leerstellen, die der
nächste Auftrag füllt" ausdrücklich die **Backtest-Maschine** auf. Ich habe daraus zunächst
geschlossen, der Stand habe keinen Simulator — und war damit auf dem Weg, den Haltefall aus
§2.4 zu bejahen und den Lauf zu beenden.

Die Messung ergab das Gegenteil: `mt5_trading_ai/backtest/engine.py` existiert, ruft
`order_roundturn_cost` in Zeile 292, wirft an sechs Stellen `LookAheadError` und trägt im
Modulkopf die Zusage „Es gibt keinen kostenlosen Modus, auch nicht zum Debuggen."
`FEHLT.md` beschreibt einen Stand, der seither überholt wurde — die Datei sagt das im Kopf
selbst („Stand nach Paket 2"), ich habe es überlesen.

**Ursache.** Ich habe eine Bestandsfrage aus einem Dokument beantwortet statt aus dem
Dateisystem. Genau die Fehlerklasse, die der Prüfbericht dieses Projekts als Muster 10
(„Doku-Drift und Phantom-Umfang") führt — nur in die andere Richtung: hier behauptete die
Doku **weniger**, als vorhanden war.

**Was daraus folgt.** Für jede Bestandsaussage in `bericht.md` steht die Belegstelle als
Kommando oder Dateipfad, nicht als Dokumentverweis. Wo ich doch aus einem Dokument zitiere
— die Historientiefe aus `ABSCHLUSS-3a/00-UEBERSICHT.md` —, ist es als „gelesen, nicht
ausgeführt" gekennzeichnet und zur Nachmessung an Stufe 1 übergeben.

---

## F-002 — Ich habe den Handelsplatz-Adapter an der falschen Stelle gesucht

**Stufe:** 0 · **Datum:** 2026-08-19 · **Folge:** ein falscher Zwischenbefund, im selben
Beleg berichtigt

**Was passiert ist.** Um die geforderte Spalte „Bitget oder MT5" für `bitget-btc-ai` zu
füllen, habe ich `services/live-broker/src/live_broker/brokers/` aufgelistet. Dort liegt
genau eine Adapterdatei: `mt5_adapter.py`. Der Zwischenbefund lautete damit beinahe, der
verworfene Stand binde MT5 — das Gegenteil der Wirklichkeit.

Die Nachmessung: Bitget ist dort nicht über `brokers/` gebunden, sondern direkt im Dienst
(`bitget_exchange_handling.py`, `exchange_client.py`, `private_rest.py`, `private_ws/`).
**445 Dateien** unter `services/*/src` enthalten die Zeichenkette `bitget`.

**Ursache.** Ich habe von einem Verzeichnisnamen auf seinen Inhalt geschlossen, statt über
den Bestand zu zählen. Nach §6 des Auftrags: „Über alle Instanzen messen. Inhaltsabhängige
Größen misst du an jeder Instanz, nie am Vertreter."

**Korrektur.** In `belege/03-simulator-und-venue.txt` steht die Berichtigung unter dem
ursprünglichen Befund, nicht an dessen Stelle. Der alte Stand bleibt sichtbar.

---

## F-003 — Der vorangegangene Prüfbericht hat eine Frage nicht zu Ende verfolgt

**Stufe:** 0 (Feststellung über einen früheren Lauf) · **Datum:** 2026-08-19

**Was passiert ist.** Der Prüfbericht vom 2026-08-19 zu `bitget-btc-ai` stellt fest, dass
dort kein Kostenmodell im Validierungspfad existiert, und zitiert die README-Zeile „Eine
separate Validierung läuft außerhalb dieses Repos." Er hat diese Spur nicht verfolgt. Das
Repository `strategy-validation` mit eingefrorener Vorregistrierung, Kostenmodell und
gepurgten Splits lag zu diesem Zeitpunkt seit dreizehn Tagen auf derselben Platte, zwei
Verzeichnisse neben dem geprüften Stand.

**Ursache.** Der Prüfauftrag war auf ein Verzeichnis begrenzt, und die Begrenzung wurde
nicht hinterfragt, obwohl der geprüfte Text ausdrücklich über sie hinauswies.

**Folge für die Bewertung.** Sie ändert sich nicht: `strategy-validation` hat gemessen
keinen Simulator und keine Ergebnisse. Der Befund „kein Vorteilsnachweis" bleibt. Was sich
ändert, ist die Vollständigkeit der Erhebung — die Aussage „es existiert nirgends ein
Validierungsapparat" wäre falsch gewesen, wenn sie so dort gestanden hätte. Sie stand so
nicht dort; sie war auf das Repository bezogen. Knapp daneben ist trotzdem der Grund,
warum Stufe 0 des neuen Auftrags mit einer Suche über das gesamte Benutzerverzeichnis
beginnt und nicht mit dem Arbeitsverzeichnis.
