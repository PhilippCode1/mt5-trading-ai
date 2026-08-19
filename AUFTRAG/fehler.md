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

---

## F-007 — Ich habe eine Sperre gebaut, die legitime Prüfreihen bestraft

**Stufe:** 3 · **Datum:** 2026-08-19 · **Folge:** keine — vor dem Einchecken gemessen,
gebaut, zurückgenommen

**Was passiert ist.** Die Vorgabe verlangt, „Kennzahleinheiten" vor dem ersten Lauf zu
korrigieren. Ich habe gemessen, dass `deflated_sharpe_ratio` für eine annualisierte
Sharpe stumm **1,000000** liefert — maximale Bestätigung gegen eine Schwelle von 0,95 —
und daraus geschlossen, es brauche eine Laufzeitsperre gegen unplausible Werte.

Die Sperre brach **18 Fälle**. Die Ursache war nicht der Fehler, gegen den sie gebaut war:
die betroffenen Reihen sind synthetische Prüfdaten mit fast verschwindender Streuung und
erzeugen Sharpes von **23,98** bis **3,06 × 10¹³**. Das ist ein Streuungsartefakt
deterministischer Fixtures, kein Einheitenfehler.

**Ursache.** Ich habe von einer richtigen Messung (die Sättigung ist real) auf eine
falsche Ursache geschlossen (also passiert die Verwechslung) und die Sperre gebaut, bevor
ich die Aufrufer und ihre Daten kannte. Die Aufrufer sagen: im Berichtspfad wird genau ein
Feld gelesen, dessen Name die Einheit trägt; in der Ereignisstudie entsteht der Wert zwei
Zeilen vorher lokal. Eine falsche Einheit ist an beiden Stellen **nicht möglich**.

Zwei Zwischenschritte, die den Fehler verlängert haben: erst habe ich die Sperre aus der
Ereignisstudie genommen (16 Fälle grün), dann festgestellt, dass dieselbe Ursache auch
den Engine-Pfad trifft (7 Fälle). Ich habe also zweimal am Symptom geschoben, bevor ich
die Ursache benannt habe.

**Zurückgenommen.** `pruefe_sharpe_je_beobachtung` und die Konstante sind gelöscht — neuer
Code ohne Aufrufer im Ausführungspfad wird nach V1 vor dem Abschluss entfernt, und ein
Helfer, der nur noch in Tests lebt, ist genau das.

**Geblieben ist, was ohne Preis wirkt:** die Feldwahl an der einen gefährlichen Zeile ist
über den Syntaxbaum festgenagelt und gegen beide Verwechslungskandidaten rot gefahren.
Der Streuungsmangel steht als `SPAETER.md`, S9.

**Was daraus folgt.** Vor einer Sperre die Aufrufer und ihre Daten messen, nicht nur die
Funktion. Eine Sperre, die richtige Eingaben abweist, ist kein strengerer Maßstab — sie
ist ein Fehler mit gutem Ruf.

---

## F-008 — Ich habe einen Testfehler drei Stufen lang als Produktionsdefekt geführt

**Wann:** gefunden in Stufe 0 (2026-08-17), berichtigt am 2026-08-19.

**Was ich behauptet habe.** In `stufen/00-bestand/bericht.md`, `stufen/02-zeitschranken/
bericht.md`, `stufen/03-simulator/bericht.md`, `zustand.md` und
`rueckbau-bestandsaufnahme.md` steht derselbe Satz: `tools/live_betrieb.py:604` schreibe
ein rohes `datetime` ins Journal, `json.dumps` werfe darauf `TypeError`, und das treffe
den risikoreduzierenden Pfad. Ich habe ausdrücklich hinzugefügt: „Das ist kein Testfehler,
sondern Produktionscode."

**Was tatsächlich der Fall war.** Der Produktionscode wandelt Zeitstempel korrekt.
`_jsonfaehig` hat rekursiv über Listen und Verschachtelungen gearbeitet und `datetime`
nach ISO-8601 umgesetzt — im Betrieb ist nie ein roher Zeitstempel ins Journal gelangt.
Rot war der Fall nur unter dem Testaufbau: der Fall friert die Uhr ein, indem er
`tools.live_betrieb.datetime` durch eine Unterklasse ersetzt. Derselbe Modulname trug aber
zwei Aufgaben — er war die Uhr **und** der Typ, gegen den `_jsonfaehig` prüfte. Nach dem
Austausch prüfte `isinstance` gegen die Ersatzklasse; ein echter `datetime` ist keine
Instanz von ihr, fiel unkonvertiert durch, und **erst dort** warf `json.dumps`.

**Wie ich es hätte merken müssen.** Der Beleg, den ich selbst angelegt habe
(`stufen/00-bestand/belege/05-defekt-journal-datetime.txt`), enthält die Rückverfolgung.
Zwei Bildschirmzeilen über der Stelle, die ich zitiert habe, steht der `monkeypatch` auf
`tools.live_betrieb.datetime`. Ich habe die letzte Zeile des Traceback gelesen und die
Diagnose daraus abgeleitet, statt zu fragen, warum ein Pfad, der ohne Uhrmanipulation seit
`6cf80a6` läuft, ausgerechnet in einem Fall bricht. Eine Messung wäre ein Dreizeiler
gewesen — `_jsonfaehig([{"seit": datetime.now(UTC)}])` außerhalb des Falls aufrufen. Die
habe ich nicht gemacht.

**Was der Fehler gekostet hat.** Drei Stufenberichte tragen den falschen Satz, `zustand.md`
hat ihn als offenen Punkt für Stufe 4 vorgemerkt, und `rueckbau-bestandsaufnahme.md` hat
ihn dem Auftraggeber als einen von zwei H-004-unabhängigen Punkten vorgelegt. Ein
Auftraggeber, der auf dieser Grundlage entscheidet, entscheidet über einen Defekt, den es
so nicht gab. Die Berichte bleiben stehen — sie sind datierte Belege —, tragen aber ab
sofort je einen Verweis auf diesen Eintrag.

**Behoben.** `tools/live_betrieb.py` bindet die echte Klasse einmal beim Import als
`_DATETIME` und prüft dagegen; die Uhr bleibt austauschbar, der Typ nicht mehr. Drei Fälle
in `tests/test_live_betrieb_sperren.py` halten das fest: einer mit eingefrorener Uhr (rot
vor der Änderung), einer ohne (der grüne Gegenfall, sonst wäre nur belegt, dass es unter
Eingriff geht), und einer, der am Syntaxbaum nachsieht, dass die Typprüfung nicht wieder
auf dem Namen der Uhr liegt.

**Was daraus folgt.** Die letzte Zeile eines Traceback nennt den Ort, nicht die Ursache.
Bevor ein roter Fall „Produktionsdefekt" heißt, muss der Pfad **einmal außerhalb des
Testaufbaus** gefahren worden sein. Und: ein Name, der zugleich Uhr und Typ ist, ist eine
Fehlerquelle unabhängig von diesem Fall — Tests tauschen Uhren aus, das ist ihr gutes
Recht.

---

## F-009 — Streuung der Beträge statt der vorzeichenbehafteten Bewegung

**Wann:** 2026-08-19, im Nachtrag zur Torerfüllbarkeit. **Gefunden und behoben im selben
Lauf, vor jedem veröffentlichten Ergebnis.**

**Was falsch war.** Die erste Fassung von `bewegung_bp` hat zwei Größen zurückgegeben:
das Mittel von `|Bewegung|` und die Streuung **derselben Beträge**. Die zweite ging in
die Sharpe-Rechnung. Falsch: die Auszahlung eines Trades ist `Richtung × Bewegung − K`
und streut mit der **vorzeichenbehafteten** Größe, nicht mit ihrem Betrag.

**Warum es nicht auffiel.** Beide Zahlen sind plausibel und liegen in derselben
Größenordnung (12,24 gegen 16,28 bp). Keine Prüfung schlug an, kein Wert sah falsch aus.

**In welche Richtung.** Die falsche Zahl ist die kleinere und macht das Tor **leichter**
aussehen — die schmeichelnde Richtung. Genau die, bei der §6 des Auftrags verlangt,
zuerst den Fehler zu suchen.

**Wie ich es gefunden habe.** Durch Nachrechnen der Größenordnung von Hand, nicht durch
einen Test: für eine mittelwertnahe Reihe muss die Streuung der vorzeichenbehafteten
Bewegung ungefähr `sqrt(m² + var(|x|))` sein, also **über** dem Mittel der Beträge
liegen — 12,24 lag darunter. Das war das Signal.

**Behoben und festgenagelt.** `bewegung_bp` gibt jetzt ausdrücklich das Mittel der
Beträge und die Streuung der vorzeichenbehafteten Bewegung zurück, mit einem Docstring,
der beide gegeneinander abgrenzt. Der Eichfall
`test_streuung_ist_die_der_vorzeichenbehafteten_bewegung_nicht_der_betraege` ist gegen
eine Reihe gebaut, bei der die beiden Zahlen um mehr als Faktor 10 auseinanderfallen —
eine Verwechslung ist dort nicht mehr unauffällig.

**Was daraus folgt.** Zwei Streuungen desselben Datensatzes sind nie austauschbar, auch
wenn beide „Streuung der Bewegung" heißen. Wo eine Kennzahl eine bestimmte Streuung
verlangt, gehört in den Docstring, **welche** — und ein Fall, der die andere ausschließt.
Das ist derselbe Fehlertyp wie F-005 (Wort statt Aufruf gesucht) und die
Sharpe-Feldwahl aus Stufe 3: drei gleich skalierte Zahlen nebeneinander, von denen genau
eine richtig ist.

---

## F-010 — Zum zweiten Mal nicht eingecheckte Arbeit mit `git checkout` zerstört

**Wann:** 2026-08-19, unmittelbar nach der Mutationsprobe zur Obergrenzen-Rechnung.

**Was ich getan habe.** Um die Erfüllbarkeitsrechnung zu prüfen, habe ich `tools/
torerfuellbarkeit.py` absichtlich mutiert (die Nicht-Überlappung entfernt), den Testlauf
gefahren — zwei Fälle gingen korrekt rot — und die Mutation dann mit
`git checkout -- tools/torerfuellbarkeit.py` zurückgenommen.

**Was dabei passiert ist.** Der Befehl stellt den Stand des **letzten Commits** her, nicht
den Stand vor der Mutation. Die Funktion `hellseher_sharpe` und der ganze Abschnitt 8
waren zu diesem Zeitpunkt noch nicht eingecheckt. Der Befehl hat also nicht die Mutation
entfernt, sondern die gesamte Arbeit an dieser Datei seit dem letzten Commit — rund 65
Zeilen.

**Das ist derselbe Fehler wie F-006**, sechs Einträge zuvor, in derselben Sitzung, mit
demselben Befehl. Dort hieß die Lehre: „nach verschränkenden Operationen gegen eine
bekannte Größe messen". Sie war richtig und hat hier nicht geholfen, weil der Fehler
schon eine Stufe früher liegt: **`git checkout` ist kein Rücknahmebefehl für eine
absichtliche Mutation.** Für die Rücknahme gibt es genau einen richtigen Weg, und der
heißt, vorher eine Kopie anzulegen.

**Wie es aufgefallen ist.** Sofort — der nächste Befehl in derselben Zeile war der
Testlauf, und er brach bei der Sammlung ab (`hellseher_sharpe` nicht importierbar). Ein
stiller Verlust war es dadurch nicht.

**Wiederhergestellt und geprüft.** Der Inhalt lag vollständig im Arbeitsprotokoll dieser
Sitzung und ist wortgleich zurückgeschrieben worden. Die Gegenprobe gegen eine bekannte
Größe — die Lehre aus F-006, hier korrekt angewandt: der Lauf liefert nach der
Wiederherstellung dieselben Zahlen wie davor, Ziffer für Ziffer (6.549 Trades, Netto
8,9741 bp, Streuung 12,2494 bp, Sharpe je Trade 0,7326, 12,2 % der Obergrenze).

**Was daraus folgt — konkreter als bei F-006.** Vor einer absichtlichen Mutation an einer
Datei mit nicht eingechecktem Stand wird eine Kopie in den Ablagebereich geschrieben und
**aus dieser Kopie** zurückgestellt. `git checkout -- <datei>` ist für diesen Zweck
gesperrt; er kennt den Zwischenstand nicht, den er wiederherstellen soll. Zweitbeste
Reihenfolge, wenn der Stand ohnehin fertig ist: erst einchecken, dann mutieren, dann
`checkout` — dann stimmen Ziel und Wirkung des Befehls überein.

---

## F-011 — Einen „Vorher"-Beleg gegen den Nachher-Stand gefahren

**Wann:** 2026-08-19, Stufe 5. Bemerkt und berichtigt, bevor der Bericht geschrieben war.

**Was falsch war.** Der Beleg `stufen/05-ausfuehrung/belege/01-messung-vorher.txt` sollte
zeigen, wie sich der Stand **vor** dieser Stufe verhielt. Ich habe dafür dasselbe
Prüfskript noch einmal laufen lassen — gegen den Arbeitsbaum, in dem die Änderung bereits
stand. Das Ergebnis war die neue Antwort unter der Überschrift „vorher", mit einem Kopf,
der ausdrücklich Commit `64b4423` behauptete.

**Warum das schwerer wiegt als ein Tippfehler.** Der ganze Bericht dieser Stufe steht auf
dem Vergleich zweier Zustände. Ein „Vorher", das in Wahrheit ein „Nachher" ist, macht die
gefundene Lücke unsichtbar und den Beleg zu einer Bestätigung dessen, was ich ohnehin
schreiben wollte. Genau davor warnt §6 des Auftrags: „Abgelesenes von Erwartetem
trennen."

**Wie es aufgefallen ist.** Beim Durchsehen der geschriebenen Datei stand in Zeile 4
`ABGELEHNT reason=schwebender_auftrag` — ein Grund, den es vor dieser Stufe nicht gab.
Eine Ausgabe, die einen Namen kennt, den der gemessene Stand nicht kennt, ist kein
Messwert dieses Standes.

**Berichtigt.** Der Beleg ist gegen einen eigenen Arbeitsbaum auf `64b4423` neu gefahren
(`git worktree add --detach`), danach wurde der Arbeitsbaum entfernt. Das Arbeitsverzeichnis
ist dabei unberührt geblieben — anders als bei einem `git checkout`, der in dieser Sitzung
schon einmal Arbeit zerstört hat (F-010). Der Unterschied steht jetzt in der Datei: vorher
`DURCHGELASSEN` nach `clear_halt()`, nachher `ABGELEHNT reason=schwebender_auftrag`.

**Was daraus folgt.** Ein Vorher-Beleg wird gegen einen **benannten Commit** gefahren, nicht
gegen „den Stand von eben". Der Arbeitsbaum ist dafür das richtige Werkzeug: er kostet
nichts, berührt die Arbeitskopie nicht, und der Kopf des Belegs kann den Commit nennen,
weil er ihn wirklich gemessen hat.

---

## F-012 — Eine Aufzeichnung nach Umfang verkleinert statt nach Aussagekraft

**Wann:** Entstanden in Stufe 5 (2026-08-19), aufgefallen und berichtigt in Stufe 7
desselben Tages.

**Was ich getan habe.** Beim Redigieren der Betriebsjournale habe ich vier Satzarten
weggelassen, die zusammen 98 % des Umfangs ausmachten: `kurs`, `signal`, `takt` — und
`eroeffnungsversuch`. Die Begründung im Werkzeug lautete: „tragen keine Antwort des
Handelsplatzes".

**Was daran falsch war.** Für drei der vier stimmt das. Für `eroeffnungsversuch` nicht:
diese 4.343 Sätze tragen die **4.311 abgelehnten Signale samt Grund** — also genau die
Auskunft darüber, was das System *nicht* getan hat und warum. Eine Stufe später verlangt
die Abnahme wörtlich, dass „die Auswertungstabelle gekennzeichnete Zeilen aus abgelehnten
Signalen" enthält. Die Daten dafür lagen vor; ich hatte sie weggeworfen.

**Der Fehler hat einen Namen.** Ich habe nach **Umfang** beurteilt statt nach
**Aussagekraft**. Vier Satzarten machten 98 % aus, also sahen alle vier nach Rauschen
aus. Eine Verkleinerung, die das Häufige für Rauschen hält, wirft das Seltene weg und
behält das Laute — und hier war das Häufige das Aussagekräftigste, das dieser Stand
besitzt.

**Was den Fehler verdeckt hat.** Der Kopf der Datei wies die weggelassenen Sätze je Art
ordentlich aus — 4.343 `eroeffnungsversuch`, sichtbar für jeden. Die Zahl stand da, und
ich habe sie selbst hingeschrieben. Sichtbarkeit ersetzt kein Urteil: eine deklarierte
Auslassung ist nicht dadurch richtig, dass sie deklariert ist.

**Berichtigt.** `eroeffnungsversuch` ist wieder in `BEHALTEN`. Statt der Sätze fällt
jetzt ein **Feld** weg (`schritte`), und die Begründung ist diesmal inhaltlich: die erste
rote Naht steht bereits als `grund` im selben Satz, die übrigen Einträge sind die grünen
davor. Dass das 72 % des Umfangs spart (4,15 → 1,18 MB), steht im Kommentar
ausdrücklich als Nebeneffekt und nicht als Grund. Der Feldwegfall wird im Kopf der Datei
ausgewiesen wie die Satzwegfälle auch, und ein Dauertor hält beides fest.

**Was daraus folgt.** Vor jeder Auslassung die Frage stellen, die ich mir nicht gestellt
habe: *wofür könnte jemand diese Zeilen brauchen, der später kommt?* Umfang ist ein
Argument für eine andere Ablageform, nie eines für das Weglassen. Und wenn eine
Auslassung doch sein muss, entscheidet die seltenste Verwendung mit, nicht die häufigste.

---

## F-013 — Den Erkundungswürfel auf die Wanduhr gesetzt

**Wann:** 2026-08-20, Stufe 9, beim Verdrahten des in Stufe 7 gebauten Erkundungspfads.
Aufgefallen an einem einzelnen Testfehlschlag, der sich zunächst nicht reproduzieren ließ.

**Was falsch war.** `execution/runner.py` rief die Erkundungsentscheidung mit dem
Schlüssel `f"{symbol}|{side}|{now.isoformat()}"`. `now` ist im Betrieb
`datetime.now(UTC)` — eine Wanduhrzeit mit Mikrosekunden. Damit ist der Schlüssel **je
Aufruf verschieden**, auch für dieselbe Gelegenheit.

**Warum das schlimmer ist, als es aussieht.** Es widerspricht genau der Eigenschaft, für
die ich den Hash in Stufe 7 gewählt hatte. Der Docstring dort sagt wörtlich: *„derselbe
Schlüssel ergibt in jedem Lauf dieselbe Entscheidung … Beides macht eine Auswertung
unreproduzierbar, und eine unreproduzierbare Auswertung belegt nichts."* Ich habe eine
Stufe später den Schlüssel so gewählt, dass sich dieselbe Lage nie wiederholt — und damit
die Begründung des eigenen Entwurfs ausgehebelt.

Im Prüfstand war die Folge sichtbar: die Suite wurde zu rund 5 % wackelig, weil ein nicht
zugelassenes Signal mit der Erkundungsrate gelegentlich gefahren wurde statt abgelehnt.
Im Betrieb wäre die Folge unsichtbar und schlimmer gewesen — eine Auswertung, deren
Auswahl sich nicht nachrechnen lässt.

**Wie es aufgefallen ist.** Ein einzelner Fehlschlag in einem Lauf unter `coverage`, der
sich in zwölf Wiederholungen nicht reproduzieren ließ. Die Versuchung war, ihn als
Ausrutscher abzulegen. Stattdessen habe ich gefragt, was ich in dieser Stufe eingebaut
habe, das überhaupt nicht deterministisch sein kann — und die Antwort stand in meinem
eigenen Code.

**Behoben.** Der Schlüssel ist jetzt `f"{symbol}|{side}|{client_order_id}"`. Die
Auftragskennung identifiziert die Gelegenheit und ist für dieselbe Gelegenheit fest.
Sechs Läufe hintereinander: 43 Fälle grün, keine Schwankung.

**Was daraus folgt.** Ein Zufallsschlüssel muss die **Sache** benennen, über die
entschieden wird, nie den Zeitpunkt der Entscheidung. Und: ein einzelner, nicht
reproduzierbarer Fehlschlag ist kein Rauschen, solange man in derselben Sitzung etwas
eingebaut hat, das würfelt. Die erste Frage lautet dann nicht „war das ein Ausrutscher",
sondern „was von dem, was ich gerade gebaut habe, ist nicht deterministisch".
