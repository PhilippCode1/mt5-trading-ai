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

---

## F-004 — Ich habe vor dem Stufe-0-Push das Gate-Set nicht vollständig gefahren

**Stufe:** 0, bemerkt in Stufe 1 · **Datum:** 2026-08-19 · **Folge:** zwei Tore rot
gepusht

**Was passiert ist.** Vor dem Stufe-0-Commit habe ich `tools/check_docs_claims.py`
gefahren — es meldete „ok - 32/32" — und daraus geschlossen, `AUFTRAG/` breche kein Tor.
Der Schluss war falsch, weil die Messung zu früh lag: der Ordner war zu diesem Zeitpunkt
**untracked**, und beide Doku-Tore zählen `git ls-files`. Der Commit hat die neun
Markdown-Dateien getrackt gemacht; erst danach wurden die Tore rot. Ich habe also nicht
den Zustand gemessen, den ich erzeugen wollte, sondern den davor.

`tools/check_doc_numbers.py` und `tools/gen_docs.py --check` habe ich vor dem Push gar
nicht gefahren, obwohl beide zum Pflicht-Gate-Set dieses Standes gehören und in der CI
laufen.

**Ursache.** Zwei Fehler in einem: eine Messung vor der Änderung statt danach, und ein
unvollständiges Gate-Set, weil ich das eine Tor für repräsentativ hielt. Nach §6 des
Auftrags: „Über alle Instanzen messen … nie am Vertreter."

**Behoben.** Beide Tore laufen jetzt grün, ohne dass eine Schwelle gesenkt wurde
(E-004); die Behebung ist mit rotem und grünem Eichfall belegt
(`stufen/01-historie/belege/05-doku-tore.txt`). Das Gate-Set wird künftig **nach** dem
Staging und vollständig gefahren.

**Was daraus für die Bewertung folgt.** Der Stufe-0-Push war nicht CI-grün. Die Abnahme
von Stufe 0 selbst berührt das nicht — sie betraf die Bestandsaufnahme, und deren Zahlen
stimmen —, aber der Satz „AUFTRAG/ bricht kein bestehendes Tor" im Stufe-0-Bericht war
zum Zeitpunkt des Schreibens bereits überholt. Er ist in Stufe 1 berichtigt.

---

## F-005 — Mein eigener Wächter las Prosa und hielt sie für Code

**Stufe:** 2 · **Datum:** 2026-08-19 · **Folge:** keine — der rote Eichfall hat ihn
gefunden, bevor er eingecheckt war

**Was passiert ist.** Der Fall, der prüft, ob ein direkter Kerzenleser die Zeitschranke
kennt, suchte in der ersten Fassung die Zeichenkette `ist_abgeschlossen` im Quelltext.
Beim Fahren der Mutation — Schranke aus `tools/ereignisstudie.py` entfernt — lief er
**grün durch**: das Wort stand noch im Docstring („Begründung bei
``protocol.ist_abgeschlossen``"). Der Wächter prüfte damit die Anwesenheit eines Wortes,
nicht die eines Aufrufs.

**Ursache.** Ich habe eine Textsuche für eine Codeprüfung gehalten. Genau die Fehlerklasse,
die dieses Repository an anderer Stelle als Tautologie führt — und ich hatte sie in
demselben Zug gebaut, in dem ich sie beheben sollte.

**Behoben.** Der Fall parst jetzt den Syntaxbaum (`ast`) und verlangt einen echten
`ast.Call` auf `ist_abgeschlossen`. Danach färbt dieselbe Mutation rot
(Beleg: `stufen/02-zeitschranken/belege/03-eichfaelle.txt`).

**Was daraus folgt.** Der rote Eichfall ist nicht Zierrat, sondern die einzige Prüfung des
Prüfers. Ohne ihn wäre ein Wächter eingecheckt worden, der nichts bewacht — und er hätte
in jedem grünen Lauf so ausgesehen wie einer, der es tut.

---

## F-006 — Ich habe beim Trennen von fremder Arbeit fast Fremdanteile verloren

**Stufe:** 2 · **Datum:** 2026-08-19 · **Folge:** keine, im selben Zug bemerkt und
zurückgeholt

**Was passiert ist.** Um meinen Anteil an `tools/ereignisstudie.py` vom fremden zu
trennen, habe ich `git checkout HEAD -- tools/ereignisstudie.py` gefahren und meine
Änderung auf den HEAD-Stand neu aufgetragen. Damit war der **fremde** Anteil derselben
Datei aus dem Arbeitsbaum verschwunden — er lag nur noch in einer Kopie unter `/tmp`, die
ich zufällig vorher angelegt hatte.

Aufgefallen ist es an einer Zahl: die isolierte Fremdarbeit zählte **12** Dateien, der
Stufe-0-Befund nennt **13**. Zurückgeholt, danach stimmten Dateizahl und Umfang exakt
(+1.162/−52).

**Ursache.** `git checkout HEAD -- <datei>` verwirft *alle* nicht eingecheckten Änderungen
dieser Datei, nicht nur die eigenen. Ich habe den Befehl benutzt, als sei er selektiv.

**Was daraus folgt.** Bei verflochtenen Ständen zuerst eine vollständige Kopie sichern und
danach gegen eine **gemessene Größe** prüfen, ob nichts fehlt — hier die Dateizahl und der
Umfang aus dem Stufe-0-Beleg. Ohne diese Gegenprobe wäre der Verlust unbemerkt geblieben.
