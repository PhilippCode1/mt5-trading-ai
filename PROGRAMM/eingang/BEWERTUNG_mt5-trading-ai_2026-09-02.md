# Bewertung des Projekts `mt5-trading-ai`

**Gegenstand:** `github.com/PhilippCode1/mt5-trading-ai`, Branch `master`, HEAD `306bbaa` vom 20.08.2026 03:47 (letzter von 114 Commits).
**Prüfung:** 02.09.2026, vollständiger Klon in einer Linux-Umgebung (Python 3.11.15, kein MetaTrader5-Terminal).
**Auftrag:** das gesamte Projekt verstehen und bewerten; insbesondere nachvollziehen, ob das System so, wie es programmiert ist, wirklich funktioniert oder funktionieren kann, ob es so aufgebaut und aufeinander abgestimmt ist, dass es KI-gesteuert handeln kann.

Alle Zahlen in diesem Aufsatz sind mit ihrer Bezugsgröße angegeben. Wo etwas ausgeführt wurde, steht **[ausgeführt]**; die Rohausgaben (72 Dateien) liegen in der beigefügten `pruef_ausgaben_mt5-trading-ai_2026-09-02.zip`; die Trennschärfe-Messung aus Abschnitt 5.3 darin unter `trennschaerfe.txt`. Wo ich nur den Quelltext gelesen habe, steht **[gelesen]**. Eigene Entscheidungen und Empfehlungen sind als solche gekennzeichnet. Bewertende Adjektive habe ich zu vermeiden versucht; wo sie stehen, steht die Zahl daneben.

---

## 0 · Der Maßstab, bevor gemessen wird

Deine Frage lautet, ob das System „so programmiert wirklich funktioniert bzw. funktionieren kann“ und ob es „perfekt KI-gesteuert traden kann“. Das ist eine Frage, aber sie enthält fünf verschiedene, und sie lassen sich nur getrennt beantworten, weil sie getrennt scheitern oder bestehen können. Ich habe die fünf Teilfragen und den Maßstab für jede **vor** der Messung festgelegt und danach nicht mehr verändert:

**F1 — Lauffähigkeit.** Lässt sich das Paket importieren, testen und bedienen? Maßstab: alle Module importierbar; die Testsuite läuft mit der im Repo dokumentierten Zahl grün; die acht CI-Tore aus `.github/workflows/ci.yml` sind auf einem frischen Klon grün; die Werkzeuge scheitern ohne Terminal laut, nicht still.

**F2 — Handelsfähigkeit.** Kann das System an einem MT5-Terminal Orders eröffnen und schließen, und ist der Orderpfad so gebaut, dass er dabei Geld schützt? Maßstab: belegte Orders an einem Demokonto; ein einziger, vollständig geprüfter Weg zum Terminal; keine Fehlerklasse, bei der eine Schließung zu einer Eröffnung wird oder die Positionsgröße das Risikobudget überschreitet; Sicherheitszustände überleben einen Neustart in der Standardkonfiguration.

**F3 — KI-Steuerung.** Wo im Entscheidungspfad sitzt ein Modell oder ein Sprachmodell, welche Daten bekommt es, was darf es entscheiden? Maßstab: ein Aufrufer im Live- oder Backtestpfad, der ein Modell befragt und dessen Ausgabe die Entscheidung verändert.

**F4 — Vorteil und Beweisapparat.** Ist belegt, dass das System nach Kosten Geld verdienen kann — oder belegt, dass es das nicht kann? Maßstab: eine Messung, deren Tor eine realistische Strategie (annualisierte Sharpe 1 bis 2) mit mindestens 80 % Wahrscheinlichkeit passieren ließe, wenn sie existierte; Kosten gemessen statt angenommen; Vorregistrierung vor Kenntnis des Ergebnisses; ein Versuchsregister, das alle Versuche zählt.

**F5 — Steuerbarkeit.** Kann ein Mensch das Projekt aus seinen Dokumenten heraus führen? Maßstab: ein lebendes Standdokument, das dem Code entspricht; Entscheidungstore, die entschieden werden, bevor weitergebaut wird; Zahlen an einer Stelle.

Die Reihenfolge ist absichtlich: F4 ist die tragende Frage. Ein System, das F1 bis F3 besteht und F4 nicht, ist eine Maschine ohne Antrieb.

---

## 1 · Was das Projekt ist — der Bestand

**[ausgeführt]** Das Repository enthält 365 Dateien ohne `.git`, davon 171 Python-Dateien mit zusammen 56.469 Zeilen: 16.835 Zeilen im Paket `mt5_trading_ai/` (42 Module ohne `__init__`, 9 Unterpakete), 10.130 Zeilen in 30 Werkzeugen unter `tools/`, 29.416 Zeilen in 89 Testdateien unter `tests/` mit 1.409 Testfunktionen, die pytest zu 1.624 Fällen entfaltet. Dazu 56 Markdown-Dateien mit 15.260 Zeilen und 113.408 Wörtern Dokumentation, 81 Belegdateien unter `AUFTRAG/stufen/*/belege/` plus 23 unter `ABSCHLUSS*/07-AUSGABEN/`, 26 JSON-Konfigurations- und Manifestdateien sowie eine redigierte Betriebsaufzeichnung von 1,2 MB.

Die Kennzahlen im README (42 Module, 1.409 Testfunktionen, 16.835 Zeilen) stimmen — `tools/check_doc_numbers.py` bestätigt sie **[ausgeführt]**, und ich habe sie unabhängig nachgezählt.

**Herkunft und Zeit.** Das Projekt ist der herausgelöste Kern des Vorgängers `bitget-btc-ai` (gemessen am 19.08.2026 im Stufe-0-Bericht: 101.323 Zeilen Python in 15 Diensten plus rund 100.000 Zeilen TypeScript). Zwölf Module wurden übernommen; sie machen heute 3.141 der 16.835 Paketzeilen aus, also 19 %. Alles andere ist neu, und zwar in **zehn Tagen**: der erste Commit stammt vom 11.08.2026 09:02, der letzte vom 20.08.2026 03:47. 114 Commits, alle unter der unkonfigurierten Git-Identität „Dein GitHub Benutzername <Deine E-Mail-Adresse>“, 65 mit dem Trailer „Co-Authored-By: Claude Opus 5“, 49 mit „Claude Opus 4.8“. Die Belege zeigen einen Windows-Rechner (`C:\Users\Acer\…`, an 51 Stellen in 27 verfolgten Dateien). Seit dem 20.08. gibt es keinen Commit.

**Architektur [gelesen].** Das Paket ist in acht Schichten geschnitten, die sich sauber trennen lassen:

| Schicht | Module | Zeilen | Aufgabe |
|---|---|---:|---|
| `venue/` | 6 | 4.225 | Handelsplatz-Vertrag (`protocol.py`), MT5-Adapter mit Fake- und Real-Terminal (`mt5.py`, 2.723 Zeilen), Katalog, Demo-Registrierung, Smoke-Test |
| `execution/` | 12 | 4.506 | Risikoschicht am Orderpfad, persistenter Risikozustand, Runner, Scheduler, Frische-Latch, Live-Freigabe, Kostentor, Reconcile, Schwebeakte |
| `risk/` | 5 | 1.006 | Hebeldeckel je Anlageklasse, Verlustgrenzen, Positionsgröße, Stop-Budget |
| `gates/` | 7 | 1.755 | Vorregistrierte Kriterien und Deflated Sharpe, Versuchsregister, Drossel, Lernphase, Erkundung, Herausforderer |
| `backtest/` | 10 | 2.436 | Backtest-Maschine, drei Strategien, Splits, Sechs-Bedingungen-Tor, Ereignisstudie, Kalender, Auflösung, Provenienz, LLM-Tor |
| `costs/` | 4 | 1.068 | Broker-Kostentabelle, Kostenmodell, ATR-Messung |
| `data/` | 3 | 677 | Dukascopy-Lader, Prüfsummen, Datenqualitätstor |
| `betrieb/` | 3 | 1.149 | Journal-Leser, Dienstgüte und Alarme |

Der Import hängt an keinem Fremdpaket — das ist gemessen: 51 von 51 Modulen und 30 von 30 Werkzeugen importieren auf einer Maschine ohne `numpy`, `pandas`, `MetaTrader5` oder irgendeine Modellbibliothek **[ausgeführt]**. Was das Paket nach eigener Aussage nicht ist: kein Dienst, kein Server, kein Container, keine Datenbank. Das stimmt.

Das ist die erste wesentliche Feststellung, und sie steht absichtlich vor allen Befunden: Dieses Projekt ist kein Chaos. Die Schichten sind benannt, die Verträge existieren, die Testsuite ist groß und läuft in 67 Sekunden, und die Dokumentation beschreibt eigene Fehler in einem Ton, den ich bei KI-generierten Projekten selten sehe. Die Frage ist nicht, ob es handwerklich existiert. Die Frage ist, ob es tut, was sein Name verspricht.

---

## 2 · F1 — Lauffähigkeit: das Paket läuft, die Tore nicht überall

**Testsuite [ausgeführt].** `python -m pytest -q` auf dem frischen Klon: **1.611 bestanden, 1 fehlgeschlagen, 12 übersprungen von 1.624 gesammelten Fällen** in 67,3 s, Exit-Code 1. Der Fehlschlag ist deterministisch: `tests/test_risiko_zustand.py::test_localappdata_wird_nur_unter_windows_gefragt` vergleicht einen Windows-Pfad (`C:\Users\…`) mit `Path.parts` und kann unter Linux nicht grün werden — die CI des Projekts läuft aber auf `ubuntu-latest`. Das Projekt schreibt in `PROGRESS.md:2657`, `AUFTRAG/zustand.md` und dem letzten Nachtrag „pytest 1.624 grün“; diese Aussage gilt nur auf dem Windows-Rechner, auf dem sie gemessen wurde.

Die zwölf Übersprungenen sind wichtiger als der eine Rote. Es sind die „Dauertore“ der Stufe 10 (`tests/test_laufabschluss.py`, `test_buchtreue.py`, `test_ausstiegsdeckung.py`, `test_journal_leser.py`), und sie enthalten `pytest.skip("keine Betriebsjournale im Arbeitsbaum")`. Die Betriebsjournale liegen in `betrieb/`, und `betrieb/` steht in `.gitignore`. Diese Tore laufen also ausschließlich auf dem einen Rechner, auf dem der Demolauf stattfand; auf jedem Klon und in der CI bestehen sie, ohne etwas zu prüfen. Das Projekt hat diese Fehlerklasse selbst benannt — im Stufe-2-Bericht steht wörtlich: „Ein Tor, das im Prüfstand mangels Datei stillschweigend übersprungen wird, ist keins.“ Acht Tage später hat es genau das gebaut.

**Ein zweiter Lauf lieferte 19 Fehlschläge [ausgeführt].** Das war der überraschendste Befund der Ausführung, und ich habe ihn erst verstanden, bevor ich ihn hier aufschreibe: `pytest -m "not slow"` direkt nach dem Volllauf zeigte 19 rote Tests (Beispiel: `cost_floor_bps(0.65) == 3.25` statt `6.5`), obwohl `git status` leer und die Quelldatei byteidentisch mit HEAD war. Ursache: das Mutationstor `tools/mutationstor.py` schreibt Mutanten per `write_bytes` in die Quelle und stellt sie danach byteweise zurück. Fallen Mutation und Rückstellung in dieselbe Sekunde und ändert der Mutant die Dateigröße nicht (`2 *` → `4 *`), hält Python das aus dem **Mutanten** erzeugte `.pyc` für gültig. Nach `rm -rf __pycache__` waren die 18 Zusatzfehler weg; gemessen waren 2 von 42 Cache-Dateien vergiftet. Das Mutationstor, das die Testwirkung beweisen soll, hinterlässt also einen Zustand, in dem die Testsuite Falsches meldet — nichtdeterministisch, je nach Sekunde.

**Nichtdeterminismus Nr. 2 [ausgeführt].** `tests/test_live_betrieb.py::test_der_takt_schreibt_den_kontozustand` war in 5 von 130 Wiederholungen rot. Grund: `tools/live_betrieb.py:413` bildet die Auftragskennung mit `uuid.uuid4()`, daraus würfelt der Erkundungspfad mit p = 0,05, und die Test-Attrappe kennt die Methode nicht, die der Erkundungspfad dann ruft. Der Kommentar in `runner.py` behauptet das Gegenteil: „Die Auftragskennung ist je Gelegenheit fest.“

**Statische Tore [ausgeführt].** `ruff check` (gepinnte 0.9.2): 0 Befunde. `ruff format --check`: 112 von 171 Dateien würden umformatiert — Formatierung ist nicht Teil der CI. `mypy --strict mt5_trading_ai`: „no issues in 51 files“. Der CI-Befehl `mypy --strict mt5_trading_ai tools` hingegen: **2 Fehler in 81 Dateien** (`tools/live_betrieb.py:749`: ein `type: ignore[import-untyped]`, das den Fehler `import-not-found` nicht abdeckt, weil `MetaTrader5` auf Linux nicht existiert). Die Belege im Repo zeigen, dass lokal ohne `--strict` gemessen wurde.

**Ergebnis der acht CI-Tore auf dem frischen Klon [ausgeführt]:** 6 grün, 2 rot (pytest, mypy). Ein grüner CI-Lauf für HEAD ist im Repo nicht belegt; die GitHub-API war aus der Prüfumgebung nicht erreichbar.

**Werkzeuge [ausgeführt].** 26 von 29 Werkzeugen mit Kommandozeile antworten auf `--help` mit Exit 0. `tools/edge_test.py --help` stürzt mit `ValueError: unsupported format character 'v'` ab (ein unmaskiertes `%` im Hilfetext) — das ist das Werkzeug, mit dem der zentrale Befund des Projekts erzeugt wurde. Die Doku-Tore (`gen_docs --check`, `check_docs_claims`, `check_doc_numbers`, `kopien_abgleichen`) sind grün. Das Mutationstor tötet 16 von 16 Sonden; die Zweigdeckung liegt bei 94 % über 5.475 Anweisungen, jede der 12 Geldpfad-Dateien über der Schwelle 80 %.

Werkzeuge, die ein Terminal brauchen, scheitern ohne Terminal so: `mt5_smoke.py` und `atr_messung.py` laut und benannt („MetaTrader5 nicht installiert“). `live_betrieb.py` und `live_konsole.py` dagegen mit einem unbehandelten Traceback aus `venue/mt5.py:2156` — der im Code vorgesehene Pfad „FEHLGESCHLAGEN — MT5-Terminal nicht erreichbar“ (Exit 2) wird nie erreicht, weil `initialize()` wirft statt `False` zu liefern. `oberflaeche.py` startet den Webserver, der Sammler-Thread stirbt still mit demselben Traceback, und die Seite zeigt dauerhaft „Noch kein Schnappschuss“.

**Windows heute [gelesen].** Wer das System auf einem frischen Windows-Rechner starten will, braucht `pip install MetaTrader5` (dokumentiert) und voraussichtlich `pip install tzdata` (nirgends dokumentiert): `backtest/kalender.py:51` und `data/loader.py:107` bauen `ZoneInfo("Europe/Helsinki")` bzw. `ZoneInfo("America/New_York")` beim Import, und Windows hat keine Zeitzonendatenbank. Auf dem Entwicklerrechner lief es, also war `tzdata` dort vorhanden — aus einem Grund, den das Repo nicht kennt. Startbefehle stehen nur in Docstrings; das `RUNBOOK.md` enthält ausschließlich Alarm-Handgriffe, keine Startprozedur. Vier der Handgriffe („Halt freigeben“, „Sendeversuch auflösen“, „Not-Aus“, „book_snapshot“) verweisen auf Methoden, für die kein Werkzeug existiert — sie sind nur aus einer Python-Sitzung erreichbar.

**Urteil F1.** Das Paket ist lauffähig, importierbar und in 67 Sekunden testbar — das ist mehr, als der Vorgänger je konnte. Der eigene Maßstab des Projekts („elf Tore je Exit 0“) ist auf einem frischen Klon nicht erfüllt: 2 von 8 CI-Toren rot, 12 Tore, die sich selbst überspringen, ein Beweiswerkzeug, das die Testsuite vergiften kann, und ein Werkzeug mit Absturz beim Hilfetext. Nichts davon ist schwer zu beheben. Aber es zeigt, dass die Aussage „gemessen, nicht behauptet“ an der Grenze des einen Rechners endet, auf dem gemessen wurde.

---

## 3 · F2 — Handelsfähigkeit: es hat gehandelt, und der Pfad hat zwei Löcher

### 3.1 Was belegt ist

**[ausgeführt]** Die Aufzeichnung `aufzeichnungen/demo-2026-08-17.jsonl` enthält 4.453 Sätze aus 21 Läufen zwischen dem 17.08.2026 14:21 UTC und dem 18.08.2026 13:12 UTC, auf einem MetaQuotes-Demokonto (redigiert zu `KONTO-1`, Start-Equity 50.000, Kontohebel 1:1). Ich habe sie unabhängig nachgezählt: 4.343 Eröffnungsversuche, davon 32 gefahren und 4.311 abgelehnt; 26 eigene Schließungen, 6 Schließungen durch den Broker (alle XAUUSD, Stop-Outs), 7 fehlgeschlagene Schließversuche, 4 erklärte Halts. Es gibt Einstiegspreise (EURUSD 1,15789), Broker-Wortlaute („Unsupported filling mode“, „No money“, „AutoTrading disabled by client“), redigierte Order- und Deal-Kennungen. Der Commit `82c81c3` nennt eine echte Order-ID.

**Das System hat also auf einem Demokonto Orders eröffnet und geschlossen.** Das ist belegt, und es ist der Punkt, an dem der Vorgänger `bitget-btc-ai` nach 100.000 Zeilen nie angekommen war (dort blockierte ein Wächter ohne Setzer jede Eröffnung). Es ist ein echter Fortschritt, und ich will ihn nicht kleinreden, bevor ich die Löcher beschreibe.

Gehandelt haben nur drei der sechs gefahrenen Symbole: EURUSD (11 Trades, 0,11 Lot), GBPUSD (10, 0,07 Lot), XAUUSD (11, 0,01 Lot). EURGBP und USDJPY scheiterten in **2.258 von 2.259** Versuchen am Kostentor mit `cost_unverifiable`, weil der Katalog für jedes Instrument USD-Gebühren führt und das Tor Kreuznotierungen dann nicht bewerten kann. US500 scheiterte **753-mal** mit „Trade disabled (retcode=10017)“ — jeder Takt eine Order, die an den Broker gesendet und dort abgelehnt wurde, weil das System das Feld `trade_mode` des Symbols nicht liest. 828 Absagen kamen von der Tageskappe, 376 vom Positionsdeckel. Der Ertrag der 11 Trades mit Ein- und Ausstiegspreis: Median +1,99 bp brutto, 8 von 11 positiv — eine Zahl ohne jede statistische Aussage, was das Werkzeug selbst so sagt. Der 24-Stunden-Lauf endete nach 18,7 Stunden, weil der Rechner in den Standby ging; ein Endstand fehlt. Seit dem 18.08. 13:12 UTC hat das System nicht mehr gehandelt.

### 3.2 Der Orderpfad [gelesen, mit neun ausgeführten Nachproben]

Von `tools/live_betrieb.py` bis `MetaTrader5.order_send` durchläuft eine eröffnende Order **24 Stationen**: Verbindung, Scheduler mit Equity-Beobachtung und Reconcile, Global-Halt, Handelszeit mit Tick-Frische, Signal, Zulassung, Daten-Tor, Hebelklammer, Kostentor, Stop-Budget, Risikoschicht (Tagesverlust, Drawdown, Positionsdeckel), Margendeckel, Volumenprüfung, Schwebeakte, Global-Halt (Venue), Stop-Pflicht, Frische-Latch, Kontoschnappschuss, Live-Freigabe, Hebel und Marge, Kostentor (Venue), Risikoschicht (zweiter Durchlauf), Doppelorder-Riegel, Schreibrecht, Broker-Idempotenz. Es gibt im Produktionscode genau **drei** Stellen, die `mt5.order_send` rufen (Order, Storno, Stop-Änderung), und nur die erste hat einen Aufrufer außerhalb der Tests. Reduce-only-Aufträge umgehen die Tore absichtlich (Vertrag V5: keine Sperre blockiert den Risikoabbau). Das ist ein durchdachter Pfad, und die im Repo behauptete Verdrahtung der fünf Risikosperren an jeder eröffnenden Order ist bestätigt (`tests/test_orderpfad_verdrahtung.py`, 28 Fälle).

Die MT5-API-Nutzung ist überwiegend korrekt: Request-Felder, Retcodes, Füllart aus dem Symbol-Bitfeld, Stop-Level in Tickschritten, `positions_get()` fail-closed bei `None`, Serverzeit nach UTC gedreht. Kleinere Abweichungen: Bitmaske 4 wird als RETURN statt BOC gedeutet; `deviation` fest 20 Points für alle Symbole (bei Gold 0,20 USD); der Stop-Änderungs-Request lässt `symbol` weg und löscht bei fehlendem `tp` den bestehenden Take-Profit (der Docstring behauptet das Gegenteil); ob ein 60-Bit-`magic` durch die Python-Bindung verlustfrei geht, ist ohne Terminal nicht prüfbar.

### 3.3 Die Fehler, die Geld kosten können

Zwei Befunde erfüllen den Maßstab „Schließung wird zu Eröffnung“ bzw. „Größe überschreitet Budget“. Beide sind mit dem Fake-Terminal des Repos bzw. einem Stub-`mt5`-Modul nachgestellt worden **[ausgeführt]**:

**D2 — Reduce-only ohne Ticket (`venue/mt5.py:2512–2536`).** Beim Schließen sucht der Adapter die Gegenposition per `positions_get(symbol=…)` und setzt `req["position"]` auf ihr Ticket. Findet die Schleife keine Position der gesuchten Richtung — etwa weil der Broker-Stop 50 Millisekunden zuvor gefeuert hat, typischerweise in genau dem volatilen Moment, in dem Signalwechsel oder Notbremse schließen wollen —, wird `position` schlicht nicht gesetzt, und die Marktorder geht **trotzdem** raus, mit `sl = 0.0`. Nachgestellt: Request ohne `position`, `accepted = True`. Auf einem Hedging- wie auf einem Netting-Konto entsteht eine neue Gegenposition ohne Stop, an allen Toren vorbei, denn der Reduce-only-Pfad ist von ihnen befreit. Das Buch bucht die Füllung als Schließung, das Reconcile sieht netto keine Drift. Der Kommentar direkt darüber beschreibt exakt diese Falle für den Fall `roh is None` und behandelt ihn — der Fall „leer, aber ohne Treffer“ ist die zweite Hälfte derselben Falle und wurde nicht behandelt. Schwere S1.

**D3 — Keine Währungsumrechnung (`risk/sizing.py:185–187`, `execution/leverage_preflight.py:90–92`, `execution/runner.py:163–167`).** Die Positionsgröße ist `Risikobetrag / (Stopabstand · Kontraktgröße)`. Der Risikobetrag steht in Kontowährung, der Nenner in Notierungswährung, und keine Funktion im Pfad nimmt einen Umrechnungskurs entgegen. Nachgerechnet: USD-Konto, EURGBP, 0,5 % Risiko → Verlust am Stop 63,15 USD statt 50 USD, also 26 % über Budget; USDJPY auf USD-Konto → Marge 30.000 statt 33, Order abgelehnt. Die Richtung hängt am Kurs: ist die Notierungswährung stärker als die Kontowährung, ist das Risiko zu groß. Heute verdeckt das Kostentor den Fehler zufällig, weil es genau die kreuznotierten Symbole mit `cost_unverifiable` abweist. Sobald jemand den Katalog um EUR- oder GBP-Gebühren ergänzt — was die 2.258 Absagen geradezu verlangen —, ist die Deckung weg. Schwere S1.

Dazu drei Befunde der Schwere S2, die den Betrieb brechen:

**D8 — Sicherheitszustand flüchtig per Vorgabe.** `tools/live_betrieb.py:832` baut `RiskManager()` ohne Zustandsdatei. Persistenz von Drawdown-Halt, Tageszähler und Schwebeakte gibt es nur, wenn `MT5_RISIKO_ZUSTAND[_ORDNER]` bzw. `MT5_SCHWEBENDE_AUFTRAEGE` gesetzt sind — drei Umgebungsvariablen, die in keiner Markdown-Datei vorkommen, während `.env.example` erklärt: „der aktuelle Kern liest keine Umgebungsvariablen.“ Ein Neustart nach Drawdown-Halt setzt alles auf null; das `RUNBOOK` empfiehlt bei Halt genau diesen Neustart. `execution/risiko_zustand.py` beschreibt in seinem Kopf einen gemessenen Vorfall (22 Trades statt 10 wegen Neustart) als Grund seiner Existenz — und der Betrieb nutzt es nicht.

**D1 — Der Erkundungswürfel im Trockenlauf.** Ohne `--scharf` ist die Zulassung `passed=False`; der Runner würfelt dann mit p = 0,05 je Versuch, ob er die nicht zugelassene Strategie trotzdem fährt. Im Trockenlauf ist `allow_write=False`, der Versuch läuft bis zum Terminal, `_require_write` wirft, und `submit_order` verbucht das als „Antwort blieb aus“: Eintrag in der Schwebeakte plus Global-Halt. Nachgestellt: `halt_reason=sendeversuch_unklar:…`, danach ist jede Eröffnung mit `schwebender_auftrag` gesperrt, auch nach `clear_halt()`. Bei sechs Symbolen und einem Versuch je Takt ist jeder Trockenlauf nach wenigen Minuten still gelatcht. Ist die Persistenz eingeschaltet, blockiert der Phantom-Eintrag den nächsten scharfen Lauf, und kein Werkzeug kann ihn auflösen.

**D7 — Geisterpositionen.** Positionen werden nur ausgetragen, wenn sie *innerhalb desselben Laufs* verschwinden. Wird eine Position im Stillstand beim Broker geschlossen (Freitagabend, Stop übers Wochenende), bleibt sie im persistierten Zustand; drei Geister genügen für `risk_concurrent_position_cap` auf jedem Symbol — ohne Ablauf, ohne Werkzeug.

Und die Liste der S3-Befunde, die ich nicht unterschlage, aber nicht ausbreite: Kostentor am Venue wird auf Demo übersprungen (der Demo-Betrieb soll der Beweisplatz sein, für das Kostentor ist er es nicht); `copy_rates_range → None` wird still zu „keine Kerzen“; `ValueError`/`RiskSizingError` im Orderpfad sind keine `VenueError` und stürzen den Takt ab; ein Halt-Grund wird von `reconcile()` überschrieben, so dass der Betrieb einen Drawdown-Halt lösen kann, wenn gleichzeitig ein Stop feuert; Serverzone `Europe/Helsinki` mit EU-Sommerzeitregeln gegen Broker-Server mit US-Regeln — 2 bis 4 Wochen im Jahr steht der Eintrittspfad still (im Code benannt, nicht behoben); nach Freitag 21:00 UTC schlägt jede Schließung fehl, und es ist kein Gap-Ereignis konfiguriert, also bleiben Positionen ohne Aufsicht übers Wochenende.

### 3.4 Was der Hebel wirklich ist

`config/asset_class_leverage.json` trägt die ESMA-Deckel korrekt (30/20/20/20/10/10/5/2) — aber sie binden nie **[ausgeführt]**: kein Aufrufer setzt einen gewünschten Hebel, deshalb greift `DEFAULT_LEVERAGE = 5` und `clamp_leverage` liefert für jede Klasse 5, für Krypto 2. Das ist konservativ, aber es heißt: die ESMA-Grenzen sind hier Dokumentation, keine Mechanik. Und „Hebel“ ist keine Exposure-Grenze je Konto, sondern eine Margenprüfung je Order plus eine Obergrenze des Stop-Budgets; drei Positionen können zusammen mehr als das Fünffache der Equity binden — faktisch begrenzt das Sizing mit 0,25 % Risiko je Trade. Die Datei enthält außerdem `system_min_leverage: 5` und die Notiz, Krypto sei damit `no_trade`; beides setzt der Code seit Entscheidung E2 nicht mehr um. BTCUSD ist handelbar, mit Hebel 2 und einem Stop-Budget bis 833 bp.

### 3.5 Die Zulassung ist ein Kommandozeilenargument

`tools/live_betrieb.py:924`: `zulassung = CriteriaVerdict(passed=bool(args.scharf), results=())`. Das README beschreibt als dritte Sperrebene: „Der Orderpfad prüft als Erstes die §9.3-Zulassung. Sie ist nicht erteilt, weil kein Kandidat das Bewertungstor bestanden hat.“ Tatsächlich prüft `Mt5Venue.submit_order` keine Zulassung; nur der Runner tut es, und der bekommt sie vom Betriebswerkzeug als Freitext: `--scharf "Maschinenprobe"` ersetzt das Bewertungstor. 15 der 21 Demoläufe liefen so, mit dem Journalfeld `zulassung_uebergangen`. Auf einem Live-Konto hielte davon nur `require_demo=True` und `allow_write=False` — beides Vorgaben derselben Klasse, die dasselbe Werkzeug mit einem Argument umstellt. Die Aussage „Der Live-Pfad ist nicht erreichbar auf drei Ebenen unabhängig voneinander“ ist damit auf einer Ebene falsch und auf den anderen beiden dünner als beschrieben.

**Urteil F2.** Das System kann an einem Demokonto handeln; das ist belegt. Es ist nicht so gebaut, dass es dabei zuverlässig Geld schützt: eine Schließung kann zur Eröffnung ohne Stop werden (D2), die Größenrechnung kennt keine Währungen (D3), der Sicherheitszustand ist per Vorgabe flüchtig (D8), der Trockenlauf latcht sich selbst (D1), Stops stehen ohne Volatilitätsbezug (alle sechs Broker-Schließungen betrafen Gold; die fünf, die sich einer Eröffnung im selben Lauf zuordnen lassen, kamen 0 bis 42 Minuten danach), und die Zulassung ist ein Flag. Von den 24 Stationen des Orderpfads sind es nicht die Tore, die fehlen — es ist die Stelle *nach* den Toren, an der das Repo am wenigsten Tests hat: `execution/runner.py` hat mit 80 % die niedrigste Deckung, `venue/mt5.py` mit 80,7 % die niedrigste Zweigdeckung.

---

## 4 · F3 — KI-Steuerung: es gibt keine, und das ist eine Entscheidung

Die Antwort auf die Frage „ist es KI-gesteuert?“ ist kurz und muss trotzdem genau sein.

**[ausgeführt]** Eine Suche über `mt5_trading_ai/` und `tools/` nach `sklearn`, `torch`, `tensorflow`, `xgboost`, `openai`, `anthropic`, `openrouter`, `gemini`, `numpy`, `pandas` liefert **0 Treffer**. Die einzigen Fundstellen für „LLM“ im Produktionscode sind `backtest/llm_compare.py` (71 Zeilen) und `tools/modelllauf.py`. Es gibt keinen Netzaufruf an ein Sprachmodell, keinen Modellaufruf, keine Merkmalsberechnung, keine Gewichte, kein Training.

**Was entscheidet [gelesen].** Im Betrieb entscheidet `moving_average_crossover(12, 26)` auf abgeschlossenen H1-Kerzen: LONG, wenn der 12er-Durchschnitt über dem 26er liegt, SHORT darunter, FLAT nur bei exakter Gleichheit — praktisch immer ein Signal, praktisch immer im Markt. Der Docstring in `tools/live_betrieb.py:124–125` nennt sie ausdrücklich Platzhalter ohne bestandenes Tor. Ausgestiegen wird bei Signalwechsel oder nach vier Stunden; danach eröffnet der nächste Takt bei unverändertem Signal dieselbe Richtung wieder. Das ist ein Kostenkreislauf, keine Strategie, und das Projekt sagt das selbst.

**Die drei Hüllen, die nach KI aussehen [gelesen]:**

`backtest/llm_compare.py` ist ein Tor *für* ein künftiges LLM: vier boolesche Prüfungen auf ein Datenobjekt (`llm_passed`, Score über Basislinie, Backtest-Start nach Trainingsende, Modellversion nicht leer). Es ruft nichts. Sein einziger Aufrufer, `tools/modelllauf.py:173–183`, füttert es mit Attrappen (alles False, 0, leer, Datum 1970), damit es „nein“ druckt und damit als „verdrahtet“ gilt — das war Stufe 9, „tote Tore verdrahten oder löschen“.

`gates/herausforderer.py` ist ein JSON-Artefakt mit Parametern, Schemahash, Prüfsumme und dem festen Zustand `wartend`. Es gibt keine Funktion, die einen Herausforderer befördert oder in den Entscheidungspfad speist; `max_haltedauer` im Betrieb kommt aus der Kommandozeile, nicht aus dem Artefakt.

`tools/modelllauf.py` ist der „Trainingslauf“: er liest Haltespannen aus dem Journal, setzt für **jeden** Trade `net_pnl_r = 0.0` (Zeile 222), ranglistet damit lauter Nullen, findet keine Schwächen, bildet einen einzigen Parameter (mittlere Haltedauer) und schreibt ihn bei mindestens 50 effektiven Beobachtungen als wartendes Artefakt. Auf den echten Daten: 16 Trades, kein Artefakt. Der Bericht der Stufe 6 sagt das ehrlich.

`gates/erkundung.py` ist ein ε-greedy-Mechanismus (p = 0,05), der abgelehnte Signale auf dem Demokonto gelegentlich trotzdem fährt, um die eigenen Absagen überprüfbar zu machen — eine gute Idee mit Horvitz-Thompson-Gewichtung, verdrahtet nur für den Grund `strategy_not_admitted`, mit 0 erkundeten Zeilen im Betrieb und dem in Abschnitt 3.3 beschriebenen Nebeneffekt D1.

**Was ein Modell hier bekäme:** aus `tools/auswertung.py` Zeilen mit Zeitstempel, Instrument, Signal, Herkunft, Ergebnis in Basispunkten und Ablehnungsgrund — gemessen **11 Zeilen mit Ergebnis** aus 23 Stunden Demobetrieb. **Was es entscheiden dürfte:** nichts. Der einzige Ausgang ist ein Vorschlag im Wartezustand, der nur über das Sechs-Bedingungen-Tor Champion werden könnte, und dieses Tor ist, wie Abschnitt 5 zeigt, für realistische Strategien nicht passierbar.

**Warum das eine Entscheidung ist und kein Versäumnis.** Der Dauerauftrag `AUFTRAG/masterprompt-freigabereife.md` §8 verbietet ausdrücklich „Fundamentmodelle, Inferenzserver, zusätzliche Sprachmodell-Agenten“ und „weitere Entscheidungsschichten“. Und `ALPHA.md` §3 begründet es: „Maschinelles Lernen findet Muster, die Menschen übersehen“ benenne keine Gegenpartei und keinen Grund für Fortbestand; es sei die Hoffnung, dass ein Suchverfahren etwas findet, wonach mit ungleich mehr Rechenleistung, Daten und Personal bereits gesucht wird. Der Vertrag, den das Projekt sich gegeben hat, stellt die KI hinter die Frage, ob es überhaupt einen Vorteil gibt. Das ist die richtige Reihenfolge. Aber sie bedeutet: der Name `mt5-trading-ai` beschreibt eine Absicht, nicht den Inhalt. Aus deiner früheren Ausrichtung — Gemini als Analystenmodell, OpenRouter angebunden — ist in diesem Repository nichts angekommen, und der Vertrag hat es bewusst ausgeschlossen.

**Urteil F3.** Nein. Es gibt im Entscheidungspfad kein Modell und kein Sprachmodell; die Strategie ist eine gleitende Durchschnittsregel, die als Platzhalter gekennzeichnet ist. Die Frage „kann es perfekt KI-gesteuert traden“ ist damit nicht mit „noch nicht“ zu beantworten, sondern mit: das Projekt hat sich, mit guter Begründung, entschieden, diese Frage erst zu stellen, wenn eine andere beantwortet ist — und die ist es nicht.

---

## 5 · F4 — Vorteil und Beweisapparat: das Herz des Projekts, und sein Konstruktionsfehler

Hier entscheidet sich alles, und hier ist die Lage komplizierter, als beide Lager es darstellen würden — die Skeptiker, die sagen „es verliert“, und die Hoffnung, die sagt „man muss nur die richtige Strategie finden“.

### 5.1 Was gemessen wurde

Am 19.08.2026 wurden drei Hypothesen gegen eine unabhängig beschaffte Reihe gefahren: EURUSD H1, 18.715 Bars vom 02.01.2022 bis 31.12.2024, Dukascopy (nur Bid), Prüfsumme `8cdebf05…`, In-Sample 13.100 Bars, Out-of-Sample 5.615 Bars ab 07.02.2024 — also 0,9 Jahre OoS. Kosten: Spread 0,1 Pip (hart codiert), Kommission 7 USD je Lot Roundturn, Slippage 0,5 Pip je Seite, Swap −8,24/+1,51 USD je Nacht, Hebel 5, fix 1 Lot, Stress ×1,5. Das Tor (`backtest/edge.py`): OoS-Trade-Sharpe ≥ 1,0; Deflated Sharpe > 0,95 gegen 60 Versuche; ≥ 2.000 Trades; drei Folds in Folge positiv; positiv unter Stress; Zufallsreferenz negativ.

| Hypothese | Trades | Netto | Trade-Sharpe | DSR |
|---|---:|---:|---:|---:|
| MA-Kreuzung 24/120 | 59 | −18,85 % | −0,792 | 0,0010 |
| Mittelwertrückkehr z48 | 123 | +3,22 % | 0,185 | 0,0150 |
| Ausbruch Donchian 48 | 58 | −30,82 % | −1,202 | 0,0003 |

Die Bootstrap-Konfidenzintervalle aller drei enthalten die Null in beide Richtungen. Das Repo nennt das Ergebnis „Befund (B) — es existiert kein Vorteil“ und legt es dem Auftraggeber als H-004 zur Entscheidung vor, mit der Empfehlung, zu beenden. **Die Läufe selbst konnte ich nicht nachfahren [nicht ausführbar]:** die Datenreihe liegt nicht im Repo (`daten/` ist gitignored, nur das Manifest mit Prüfsumme ist eingecheckt), und der Dukascopy-Abruf scheitert aus der Prüfumgebung am Proxy (403). Die Zahlen sind also weder bestätigt noch widerlegt; ich prüfe im Folgenden den Apparat, der sie erzeugt hat.

### 5.2 Was am Apparat stimmt

Das soll vorangehen, weil es nicht selbstverständlich ist. Die Statistikfunktionen in `gates/criteria.py` — erwartete Maximal-Sharpe, Deflated Sharpe Ratio, Annualisierung, Perzentil gegen Zufall — sind gegen eine unabhängige Implementierung mit `scipy` nachgerechnet **[ausgeführt]** und stimmen bis auf 10⁻¹⁰ mit Bailey und López de Prado (2014) überein. Das Kostenmodell bucht je Roundturn exakt das, was eine Handrechnung ergibt (18,00 USD bei 1 Lot EURUSD, 0,1 Pip Spread, 7 USD Kommission, 0,5 Pip Slippage je Seite) **[ausgeführt]**. Der Leckageschutz funktioniert: `MarketView` wirft bei jedem Zugriff auf eine spätere Kerze, und ein Test fährt das negativ. Purge und Embargo sind korrekt implementiert. Das Versuchsregister ist anhängend mit Prüfsumme und Commit-Herkunft. Der Dukascopy-Dekoder entspricht dem bekannten bi5-Format. Das Datenqualitätstor prüft Lücken gegen Sessions, Monotonie, OHLC-Ordnung. Das ist handwerklich solide Arbeit, und 170 Tests über zehn Dateien bestätigen sie **[ausgeführt]**.

### 5.3 Der Konstruktionsfehler: ein Tor ohne Trennschärfe

Die entscheidende Frage an jede Messung ist nicht „was kam heraus?“, sondern „was hätte herauskommen können?“. Ich habe deshalb mit den **eigenen Funktionen des Repos** gemessen, mit welcher Wahrscheinlichkeit eine Strategie, die wirklich einen Vorteil hat, das Tor passiert **[ausgeführt, `trennschaerfe.txt` im Beleg-Archiv]**. Annahme: unabhängig normalverteilte Trade-Renditen, 2.000 Trades in 0,9 Jahren, 60 Versuche, 3.000 Wiederholungen je Zeile.

| wahre annualisierte Sharpe | besteht Bedingung 1 (Sharpe ≥ 1,0) | besteht Bedingung 2 (DSR > 0,95) | besteht beide |
|---:|---:|---:|---:|
| 0,0 | 17,0 % | 0,0 % | 0,0 % |
| 1,0 | 50,2 % | 0,1 % | 0,1 % |
| 2,0 | 82,3 % | 1,5 % | 1,5 % |
| 3,0 | 97,2 % | 12,1 % | 12,1 % |
| 4,0 | 99,8 % | 41,7 % | 41,7 % |
| 5,0 | 100,0 % | 78,9 % | 78,9 % |

Zur Einordnung: eine annualisierte Sharpe von 2 wäre für eine systematische Strategie auf einem einzelnen FX-Paar außergewöhnlich; die meisten dokumentierten Ansätze liegen unter 1. **Eine Strategie mit echter Sharpe 2 passiert dieses Tor in 1,5 von 100 Fällen. Eine mit Sharpe 3 in 12 von 100.** Bedingung 2 verlangt rechnerisch eine Sharpe je Trade von 0,0894, annualisiert 4,22 — und selbst dann besteht sie nur zu 42 %, weil der Schätzfehler auf 0,9 Jahren rund ±1,05 Sharpe-Punkte beträgt. Umgekehrt lässt Bedingung 1 allein eine Strategie ohne jeden Vorteil in 17 von 100 Fällen durch. Das Tor ist also auf der einen Seite zu grob und auf der anderen unpassierbar: Ein „Nein“ aus diesem Tor sagt fast nichts darüber, ob ein Vorteil existiert. Es sagt: mit diesem Design ist die Frage nicht entscheidbar.

Dazu kommt Bedingung 3. Die drei Strategien halten im Mittel 44 bis 119 Bars je Trade; 2.000 Trades auf 5.615 OoS-Bars verlangen 2,8 Bars. Diese Bedingung war für die getesteten Hypothesen **konstruktionsbedingt unerreichbar**, um den Faktor 16 bis 34, und der Nachtrag des Repos räumt das ein („Auslegungslücke der Kampagne“).

**Das Repo hat den Fehler selbst gemessen und falsch geschlossen.** Der Nachtrag „Torerfüllbarkeit“ (`AUFTRAG/stufen/03-simulator/nachtrag-torerfuellbarkeit.md`, Zusammenfassung in `haltepunkte.md`) rechnet vor, dass Bedingung 2 annualisiert 4,22 verlangt, dass das eine Trefferquote von 64,6 % bei 2,8 Stunden Haltedauer bedeutet, dass der Nulldurchgang allein 57,8 % kostet — und schließt: „Das Tor ist erfüllbar (f = 29,1 % der mittleren Bewegung, also deutlich unter 100 %). Befund (B) steht unverändert.“ Das ist ein Fehlschluss. Dass ein Hellseher das Tor nehmen könnte, macht es nicht zu einem Test für die Existenz eines Vorteils. Ein Tor, das nur Sharpe-4-Strategien passieren lässt, misst nicht „gibt es einen Vorteil“, sondern „gibt es einen Vorteil der Größenordnung, die es in liquiden FX-Stundenbars nach allem, was bekannt ist, nicht gibt“. Das Ergebnis dieser Messung stand fest, bevor sie lief — und zwar in beide Richtungen: ein „Ja“ hätte ebenso wenig bedeutet.

Die Zufallsreferenz ist aus demselben Grund ohne Aussage: `random_signal_strategy` wählt je Bar aus {Long, Flat, Short} und erzeugt rund 2.500 Trades auf 5.615 Bars, deren Kosten 209 % der Margin fressen (Beleg: −218 %). Jede Strategie mit 58 bis 123 Trades schlägt das trivial; die Bedingung „Zufall negativ“ prüft nur, dass das Kostenmodell Kosten bucht. Gefahren wurden 5 Zufallsläufe statt der in `criteria.py` vorregistrierten 1.000.

### 5.4 Die weiteren Schwächen der Messung

Sie sind kleiner als 5.3, aber sie zeigen dieselbe Richtung: eine Maschine, die ihre eigene Frage nicht beantworten kann.

**Die Vorregistrierung war keine.** Die drei Hypothesen und ihre Zahlen standen seit dem 13.08. in `BERICHT_TEIL3.md`; die Vorregistrierung vom 19.08. registriert ausdrücklich „eine Reproduktion, keine neue Suche“, und die Stufe-1-Reihe hat exakt die Prüfsumme der Teil-3-Reihe. Das Repo nennt es „auf neu und unabhängig beschafften Daten“ — unabhängig vom Broker, ja; vom früheren Lauf sind es dieselben Bytes. Als Reproduzierbarkeitsnachweis des Apparats ist das wertvoll. Als Vorregistrierung im wissenschaftlichen Sinn ist es keine, und sie hat 24 der 60 Kampagnenversuche für die Wiederholung bekannter Läufe und deren Zerlegung verbraucht. Sie sagt außerdem „OoS ist das letzte Drittel“; der Code nimmt 30 %.

**Das Register zählt nicht alles.** „Jeder Lauf zählt“ gilt seit dem 17.08.; die 18 Versuche aus Teil 3, die 12 Multi-Instrument-Versuche und der Breakout-Lauf auf 2025/26 stehen nicht darin. Derselbe OoS-Block wurde im Register viermal und davor mindestens dreimal angefasst. Die Deflation kennt die wahre Versuchszahl nicht — und die sieben Ereignisstudien, die sie mitzählt, wurden auf Terminaldaten gefahren, die Stufe 1 später für unbrauchbar erklärt hat (0 von 15 Reihen unabhängig, 12 von 15 enden auf einer offenen Kerze).

**Backtest und Betrieb handeln verschiedene Systeme.** Der Backtest füllt zum Close des Signalbars, nicht zum Open des nächsten (nachgerechnet: 500 USD Brutto bei einem 50-Pip-Gap, wo ein Fill am Open 0 ergäbe) — auf lückenlosen H1-Bars klein, an Wochenend- und Bewegungsgrenzen systematisch schmeichelnd; der Einwand wurde einmal ad hoc geprüft und nie im Werkzeug abgestellt. Finanzierungsnächte zählen UTC-Tageswechsel ab dem Entscheidungsbar, der Rollover liegt aber bei 21/22 UTC und der Fill eine Stunde später (nachgerechnet: von vier Randfällen zwei falsch). Der Backtest kennt weder Stop-Loss noch Positionsgröße noch Margin-Call — die Equity kann unter null laufen und der Lauf läuft weiter; der Betrieb verlangt einen Stop und rechnet die Größe aus dem Stopabstand. Und die Strategie, die im Betrieb läuft, MA(12,26), ist nie gebacktestet worden; gebacktestet wurde MA(24,120).

**Zwei Wahrheiten je Kostenposten.** Die Engine rechnet 0,5 Pip Slippage je Seite (0,93 bp Roundturn), die Kostendatei 0,5 bp Roundturn; der Spread ist mit 0,1 Pip hart codiert, der Katalog sagt 0,6 Pip, die Dukascopy-Reihe ist nur Bid, also ist der Spread eine Annahme. Slippage ist 55,6 % der Kostenrechnung und der einzige ungemessene Posten — das Repo sagt das selbst. Es gibt zwei Vorregistrierungen im Code mit verschiedenen Zahlen (`criteria.py`: 500 Trades, 1.000 Zufallsläufe; `edge.py`: 2.000 Trades, 5 Zufallsläufe), obwohl Vertrag V6 genau das verbietet. `ABBRUCH.md` begründet die Kampagnengröße 60 in einer Einheit (Tageskonvention, ×√252), die das Tor nicht benutzt.

### 5.5 Was das Projekt richtig gesehen hat

`ALPHA.md` ist die ehrlichste Seite des Repositories. Sie stellt die vier Fragen, die jedes Handelssystem beantworten muss — welche Quelle des Vorteils, wer verliert, warum bleibt er bestehen, wie widerlegt man ihn —, und beantwortet drei davon mit „keine haltbare Antwort“: kein Informationsvorsprung (dieselben OHLC-Kerzen wie jeder Retail-Kunde), keine Geschwindigkeit (drei bis fünf Größenordnungen daneben), keine benannte Zwangslage. Die Ereignisstudie aus Paket 3a hat dann fünf Zwangslagen benannt und gemessen: größter Bruttoeffekt 1,36 bp gegen eine Kostenschwelle von 5,51 bp, alle sieben Nettoeffekte negativ, und der kleine Effekt ist nicht an das Ereignis gebunden, sondern die allgemeine Neigung der Stundenrendite zur Rückkehr. Das ist — trotz der später verworfenen Datenbasis — der substanziellste Befund des Projekts, weil er nicht an einem Tor hängt, sondern an einem Größenverhältnis: Faktor 4 bis 39 zwischen Effekt und Kosten.

Und `BERICHT_TEIL3.md` §5 hat die Mindest-Nachweisdauer nach López de Prado ausgerechnet: bei einer Sharpe von 0,185 wären 79 bis 97 Jahre Out-of-Sample nötig. Das ist dieselbe Aussage wie meine Trennschärfe-Tabelle, nur aus der anderen Richtung — und sie stand im Repo, bevor die Stufe-3-Läufe gefahren wurden.

**Urteil F4.** Ein Vorteil ist nicht belegt. Er ist aber auch nicht widerlegt, und die Überschrift „Befund (B) — es existiert kein Vorteil“ ist in dieser Form nicht gedeckt: Das Tor, gegen das gemessen wurde, hätte einen realistischen Vorteil mit 98 % Wahrscheinlichkeit übersehen. Die korrekte Formulierung, die das Repo in `bericht.md` §5.1 und in der H-004-Empfehlung zur Hälfte selbst gibt, lautet: *Auf EURUSD H1 ist die Frage mit diesem Apparat und dieser Datenmenge nicht entscheidbar.* Das ist ein anderer Befund als „kein Vorteil“, und er führt zu einer anderen Entscheidung. Was das Projekt substanziell gezeigt hat, ist etwas anderes und Wichtigeres: dass es auf der Stundenskala eines Retail-CFD-Kontos keine benannte Quelle für einen Vorteil gibt, dass die gemessenen Zwangslagen ihre Kosten nicht tragen, und dass jede Strategiearbeit ohne benannte Quelle Kurvenanpassung an Rauschen ist.

---

## 6 · F5 — Steuerbarkeit: Tore und Prosa wachsen schneller als Erkenntnis

### 6.1 Der Verlauf in zehn Tagen

Die Git-Historie erzählt eine Geschichte, die kein Dokument im Repo vollständig erzählt **[ausgeführt, `git log`]**:

Am **11.08.** wird der Kern in 48 Minuten aus `bitget-btc-ai` herausgelöst, am selben Tag von Bitget auf MT5 umgestellt. Am **12.08.** Selbst-Audit und CI. Vom **12. auf den 13.08.** Teil 3: Backtest-Engine, drei Edge-Tests, dreimal Entscheidungstor E5 — „weiter“, „weiter“, „beenden“ — und 29 Minuten nach „beenden“ der Commit „Doch Paket 5“, der die eigenen Abbruchregeln übersteuert. Vom **13. bis 15.08.** sieben „Abnahme-Pakete“, die mit „System abnahmefertig“ enden (später widerrufen). Am **17.08.** um 00:50 „Paket 2“ (Kostentor an vier EU-Brokern), um 14:22 Paket 3a (Ereignisstudie, Urteil gelb), um 16:14 der Demo-Betrieb, und um **18:14 der Commit „Weg (a) — Vorhaben in dieser Auslegung abgeschlossen“** mit ausgelöster Abbruchbedingung 3: „Halt. Keine weitere Eröffnung.“ **40 Minuten später**, um 18:54, beginnt der größte Ausbau des Projekts: Web-Oberfläche, drei „Wellen“ mit Agentenschwärmen — bis zum 18.08. 04:12 zusammen 24.758 eingefügte Zeilen in 89 Dateien, die Testzahl steigt laut Commit von 1.099 auf 1.354 —, um 20:28 der Start des 24-Stunden-Demolaufs — nichts davon steht in `PROGRESS.md`, dem „Kernprotokoll“. Am **19.08.** von 17:23 bis 20:16 der neue Dauerauftrag, Stufen 0 bis 3, Vorregistrierung, Befund (B), Haltepunkt H-004 mit der Empfehlung „beenden“. Um 20:55 der Halal-Rückbau auf Anweisung. Und von **22:14 bis 03:47 am 20.08.**, in einer Nachtsitzung von 10 Stunden 24 Minuten, die Stufen 4 bis 10 samt drei Nachträgen — vom Halal-Rückbau bis HEAD 19.549 eingefügte Zeilen in 123 Dateien — auf die Anweisungen „weiter mit schritt 4“, „weiter mit stufe 5/6“, „Stufe 7“, „stufe 8/9/10“. Der Vertrag §1 sagt für Befund (B): „bevor weiterer Aufwand in Absicherung, Ausführung, Oberfläche oder Betrieb fließt. Ein System, dessen Vorteil widerlegt ist, wird nicht abgesichert.“ Der Agent hat das als Entscheidung E-009 protokolliert und ausgeführt.

Ich schreibe das nicht, um über Anweisungen zu urteilen, die du gegeben hast. Ich schreibe es, weil es die Frage F5 beantwortet: Die Entscheidungstore, die das Projekt sich gebaut hat, wurden zweimal von seinem Ergebnis überfahren — „Doch Paket 5“ und E-009 —, und beide Male in dieselbe Richtung: weiterbauen. H-002 („darf Stufe 3 unter ‚keine Strategiearbeit' laufen?“) wurde dreimal gemeldet und nie beantwortet; der Agent legte die erneute Auftragserteilung als Ja aus. H-004 ist formal offen und faktisch erledigt. H-003 — Zugangsdaten im Klartext in drei `.env`-Dateien und zwei Archiven des Altbestands in einem OneDrive-Ordner — ist der einzige Haltepunkt, der wirklich nur dich braucht, und er ist seit dem 19.08. offen.

### 6.2 Die Dokumentation

113.408 Wörter Prosa in 56 Dateien für 16.835 Zeilen Code, entstanden in zehn Tagen. Zwölf Dateien beschreiben einen „Stand“ (README zweimal, MASTERBERICHT, ABBRUCH mit sechs Standabsätzen, ALPHA zweifach, zwei Abschlussübersichten, geloescht.md, haltepunkte.md, zustand.md, Audit); es gibt fünf Fehlerregister, drei Rückstellungslisten, sieben Nomenklaturen (U-Pakete, Teil-3-Pakete, Abnahme-Pakete, Masterprompt-Pakete, Paket 3a, Wellen, Stufen) ohne Übersicht; „Paket 2“ bezeichnet drei verschiedene Dinge. Das Prinzip „nie überschreiben“ kollidiert mit „eine Zahl an einer Stelle“: überholte Absätze bleiben stehen und werden mit 57 Nachträgen, 16 Widerrufen und 16 Berichtigungen überlagert. `AUFTRAG/zustand.md` soll laut Vertrag sieben Zeilen mit je einem Satz sein; die Zeile „Zuletzt“ hat 1.205 Wörter, die Zeile „Nächster Schritt: ein Satz“ 653.

Die Doku-Tore prüfen weniger, als ihr Ruf verspricht **[gelesen, mit ausgeführter Schlupfloch-Probe]**: `check_doc_numbers.py` nimmt `PROGRESS.md`, `AUFTRAG/`, `ABSCHLUSS/`, `ABSCHLUSS-3a/` und `docs/audit/` aus — 43 der 56 Dateien — und kennt fünf Regeln. `check_docs_claims.py` sperrt zehn Phrasen und akzeptiert als Beleg jede Zeile mit dem Wort „Beleg“ und einem Backtick, ohne zu prüfen, ob der genannte Test existiert; eine Testdatei mit „production ready — Beleg: `irgendwas`“ passiert. Der Commit-Titel `651c752` lautet „der Order-Pfad wird produktionsreif“ — die Phrase, die das Tor in Markdown blockt; Commit-Texte prüft es nicht.

Was die Tore nicht fangen, ist inhaltliche Drift, und davon gibt es viel: `FEHLT.md` führt Backtest-Maschine und Strategie als „neu zu schreiben“, obwohl beide seit dem 12.08. existieren, und das README verweist darauf als Liste dessen, „was noch fehlt“. `MASTERBERICHT.md` trägt „Stand der Messung: 2026-08-11“ und beschreibt einen Kern ohne Backtest-Engine, während er an anderer Stelle die Sperren von Paket 2 aufzählt. `VERLUST.md` nennt Kill-Switch und Halt-Latch „neu zu schreiben“, `FEHLT.md` erklärt sie für erledigt. Das README zitiert `venue/mt5.py:447` als Ort der Live-Freigabe — dort steht die Klassendefinition; der Aufruf steht in Zeile 968. `.env.example` sagt, der Kern lese keine Umgebungsvariablen; er liest fünf. `ABSCHLUSS/06-ABBRUCHKRITERIUM.md` heißt „Kopie von ABBRUCH.md“ und weicht ab; das Kopien-Tor prüft nur die andere Kopie. Die Zahl der in Stufe 9 behandelten Funktionen steht in vier Dokumenten als 12, 7+5, 7+7 und 15.

### 6.3 Die Fehlerklassen, die sich wiederholen

Das Projekt führt seine eigenen Fehler mit einer Offenheit, die ich anerkenne — F-001 bis F-020 in `AUFTRAG/fehler.md`, dazu die 09-EIGENE-FEHLER-Dateien beider Abschlussordner. Liest man sie zusammen, wiederholen sich vier Klassen: **Module ohne Aufrufer** (Hebelklammer, vier Risikomodule, Compliance-Tore, Prüfsummenmaschine, `learning_phase`, zwölf Funktionen in Stufe 9 — darunter der in Stufe 7 selbst gebaute Erkundungspfad); **Wächter, die nichts wachen** (ein Kostentor, das nie rot werden konnte; eine Bedingung 6, die fest auf `True` stand, zweimal; ein Melder, der Anwesenheit statt Wert prüfte); **Kennzahlen neben der Sache** (eine Laufabschluss-Metrik, die antikorreliert zur Gefahr ist; eine Buchtreue, die ihrem Docstring widerspricht); **Doku-Drift**. Der Vertrag §0 nennt genau diese Muster als das, „woran das Projekt krankt“, und der Auftrag, der sie beheben sollte, hat sie reproduziert — die zwölf sich selbst überspringenden Tore der Stufe 10 sind die jüngste Instanz.

Die Erklärung dafür steht in den Zahlen: 11 Kommandozeilen-Tore, 37 Erwähnungen von „Dauertor“, 85 von „Eichfall/Eichfälle“, 136 von „fail-closed“, 89 von „ehrlich“ in den 56 Markdown-Dateien — und **ein** Betriebstag. Die Absicherungsmaschinerie ist umfangreicher als das, was sie absichert, und sie wächst mit jedem Fehler, der gefunden wird, während der Gegenstand — ein Handelssystem mit einem Vorteil — nicht wächst. Der Vertrag §0 hat auch das vorhergesehen: „eine Absicherungsmaschinerie, die umfangreicher ist als das, was sie absichern soll.“

Zwei kleinere Punkte, der Vollständigkeit halber: Die Git-Identität ist nicht konfiguriert (alle 114 Commits von „Dein GitHub Benutzername“). Geheimnisse liegen keine im Repo — Login-, Passwort-, Server- und IP-Muster über Arbeitsbaum und alle Commits: 0 Treffer, die Kontonummer ist redigiert; aber der Windows-Kontoname `Acer` steht 51-mal in verfolgten Dateien, und `geheimnis_scan.py` gibt immer Exit 0 zurück, ist also kein Tor. Die Halal-Vorfrage (H-001) wurde auf deine Anweisung samt Code entfernt; die Sachfrage — ob gehebelte CFDs als Instrument für dich tragfähig sind — ist damit nicht beantwortet, sondern gestrichen. Ich merke das nur an, weil ethische Legitimität nach deinen eigenen Regeln eine harte Anforderung ist und weil das Projekt selbst in `ALPHA.md` §2 die Gegenpartei eines B-Book-Brokers als „schlechteste denkbare Antwort“ beschreibt.

**Urteil F5.** Aus den Dokumenten heraus ist das Projekt heute nicht führbar; der rote Faden ist nur über `git log` rekonstruierbar, und das Standdokument widerspricht sich in einer Zeile. Die Steuerung durch Einwort-Anweisungen hat die Tore außer Kraft gesetzt, die das Projekt gegen genau diese Dynamik gebaut hatte. Der Agent hat das jedes Mal protokolliert — das ist die gute Nachricht — und jedes Mal ausgeführt.

---

## 7 · Gesamturteil

**Funktioniert das System, so wie es programmiert ist?** Als Softwarepaket: ja, mit den in Abschnitt 2 gemessenen Einschränkungen — importierbar, testbar, auf einem Demokonto handelnd, mit einem Orderpfad von 24 Stationen und einer Kultur des Fail-closed, die im Vorgänger fehlte. Als Handelssystem: nein. Es fehlt ihm der Antrieb, nicht das Getriebe.

**Ist es so aufgebaut und aufeinander abgestimmt, dass es KI-gesteuert handeln kann?** Nein. Es gibt keine KI im Entscheidungspfad, die Strategie ist ein gekennzeichneter Platzhalter, und Backtest und Betrieb handeln verschiedene Systeme. Der Vertrag, den das Projekt sich gegeben hat, schließt Modelle bewusst aus, bis ein Vorteil belegt ist — mit einer Begründung, die trägt.

**Kann es profitabel handeln?** Das ist nicht belegt, und die Messung, die es widerlegen sollte, konnte es nicht: ein Tor, das eine Sharpe-2-Strategie mit 98,5 % Wahrscheinlichkeit übersieht, beantwortet die Frage nicht. Was belegt ist: auf der Stundenskala eines Retail-CFD-Kontos gibt es keine benannte Quelle für einen Vorteil, die gemessenen Zwangslagen tragen ihre Kosten um den Faktor 4 bis 39 nicht, und die Mindest-Nachweisdauer für die beste getestete Strategie liegt bei 79 Jahren.

**Nach Schwere geordnet sind die Befunde:**

Erstens das Studiendesign (5.3): Das Sechs-Bedingungen-Tor hat keine Trennschärfe; der zentrale Befund des Projekts ist ein Artefakt des Maßstabs und wird im Repo mit einem Fehlschluss verteidigt. Das ist kein Codefehler, sondern der Grund, warum das Projekt seine eigene Frage nicht beantworten kann.

Zweitens die zwei S1-Fehler im Geldpfad (3.3): eine Schließung, die zur Eröffnung ohne Stop werden kann, und eine Größenrechnung ohne Währungsumrechnung. Beide sind nachgestellt, beide liegen hinter den Toren.

Drittens die flüchtige Sicherheit (3.3, D8): Der Betrieb nutzt den persistenten Risikozustand nicht, den das Projekt wegen eines gemessenen Vorfalls gebaut hat; drei undokumentierte Umgebungsvariablen entscheiden darüber, und die Beispieldatei behauptet, es gäbe keine.

Viertens die Tore, die nicht messen (2, 6.2): zwölf Tests, die sich auf jedem Klon überspringen; zwei rote CI-Tore auf Linux; ein Mutationstor, das die Testsuite vergiften kann; Doku-Tore, die 43 von 56 Dateien ausnehmen.

Fünftens die Steuerung (6.1): zwei überfahrene Ergebnistore, ein dreimal unbeantworteter Haltepunkt, ein Standdokument, das sich widerspricht.

Und was ich ausdrücklich als Stärke festhalte, mit Zahl: Statistikfunktionen exakt bis 10⁻¹⁰; Kostenbuchung stimmt mit Handrechnung; Leckageschutz negativ getestet; 32 echte Demo-Orders mit Broker-Antworten; Zweigdeckung 94 %; ein Vertrag (`masterprompt-freigabereife.md`), der die richtigen Fragen in der richtigen Reihenfolge stellt; Fehlerregister mit 20 eigenen Fehlern, die kein Mensch geschönt hat; und eine `ALPHA.md`, die den Kern der Sache in vier Fragen fasst und drei davon ehrlich mit „keine Antwort“ beantwortet.

---

## 8 · Was daraus für „komplett von Grund auf verbessern“ folgt

Das sind meine Schlüsse, als eigene gekennzeichnet. Sie sind keine Handelsempfehlung; sie betreffen die Reihenfolge der Arbeit.

**Erstens: Fundament vor Skalierung, und das Fundament ist F4.** Jede Zeile, die in Oberfläche, Dienstgüte, Herausforderer-Hülle, Erkundung oder weitere Tore fließt, bevor die Frage nach dem Vorteil entscheidbar gemacht ist, wiederholt den Fehler vom 17. und 19. August. „Von Grund auf“ heißt hier nicht, den Code wegzuwerfen — der Orderpfad und der Statistikkern sind die belegten Stärken —, sondern die Messung neu aufzusetzen: eine Trennschärfe-Rechnung **vor** dem Lauf (welche Sharpe soll mit 80 % erkannt werden, wie viele Trades und Jahre braucht das), Tore, die zur Frequenz der Hypothese passen, eine Deflation gegen die ehrlich gezählte Versuchszahl, eine frequenzgleiche Zufallsreferenz, Fill zum nächsten Open, Rollover-korrekte Nächte, dieselbe Strategie im Backtest wie im Betrieb, und mehr Daten — mehrere Instrumente und mehr Jahre, weil 0,9 Jahre OoS auf einem Paar nach der eigenen Rechnung des Repos nichts auflösen können.

**Zweitens: die Frage nach der Quelle des Vorteils geht der Frage nach der KI voraus.** Wenn das Ziel „KI-gesteuert“ bleibt, muss vorher benannt werden, welche Information ein Modell hätte, die der Markt nicht hat — sonst gilt, was `ALPHA.md` sagt. Ein Sprachmodell, das Nachrichten liest, ist eine mögliche Antwort auf Frage 1 (Information), aber nur, wenn die Messung aus dem ersten Punkt sie prüfen kann. Ein Modell, das auf 11 Ergebniszeilen trainiert, ist keine.

**Drittens: den Geldpfad vor jedem weiteren Demobetrieb dicht machen.** D2, D3 und D8 sind eng umrissen und mit je einem roten Eichfall belegbar; D1 verschwindet, wenn die Erkundung im Trockenlauf nicht bis zum Terminal läuft; die zwölf Selbstüberspringer werden zu echten Toren, sobald die redigierte Aufzeichnung ihr Prüfgegenstand ist statt der gitignorierten Journale. Das ist ein Paket von Tagen, nicht Wochen.

**Viertens: die Steuerung.** Ein einziges lebendes Standdokument statt zwölf; Haltepunkte, die beantwortet werden, bevor die nächste Stufe beginnt; und H-003 — der Widerruf der Zugangsdaten im Altbestand — als erste Handlung, weil sie nur du vornehmen kannst und weil sie mit dem Wert dieses Projekts nichts zu tun hat, aber mit deinem Risiko.

Was ich in diesem Aufsatz nicht getan habe: den Masterprompt für den Neuaufbau geschrieben. Das ist der nächste Abschnitt, und er hängt an einer Entscheidung, die nur du treffen kannst — ob der Neuaufbau bei der Messung beginnt (mein Vorschlag), beim Geldpfad und Demobetrieb, oder beim KI-Analystenpfad, der bisher nur ein Name ist.

Bismillah.
