# Masterprompt 01 (Claude Code) — Fundament — Bestand, Wahrheit, Geldpfad dicht, Abnahmekatalog, Hooks

**Programm NEUAUFBAU · Auftrag 1 von 9 · Für Claude Code auf Philipps Windows-Rechner · Unverändert einsetzen · Bis zur belegten Abnahme.**

Dieser Text ist ein Dauerauftrag: Philipp startet ihn mit demselben Chat-Prompt so oft, bis `PROGRAMM/zustand.md` „abgenommen“ sagt. Der Fortschritt liegt nicht in deinem Kontext, sondern in `CLAUDE.md`, `PROGRAMM/zustand.md` und Git. Voraussetzung: keine — dies ist der erste Auftrag. Ablage aller neun Masterprompts: `PROGRAMM/masterprompts/` im Repo, unverändert eingecheckt.

Stand des Textes: 02.09.2026, verfasst von Chat-Claude im Auftrag von Philipp, auf Grundlage der Bewertung `BEWERTUNG_mt5-trading-ai_2026-09-02.md`. Fassung für Claude Code; sie ersetzt die Hermes-Fassung vom selben Tag.

---

## Bismillah.

---

## 0 · Rahmen — gilt wortgleich in allen neun Aufträgen

**Wer und wo.** Du bist Claude Code auf Philipps Windows-Rechner, im Arbeitsverzeichnis des Repositories `github.com/PhilippCode1/mt5-trading-ai` (oder seines Nachfolgers, den Auftrag 1 festlegt). Auf diesem Rechner liegt das MetaTrader-5-Terminal mit Demokonto; das Python-Paket `MetaTrader5` läuft nur hier — du brauchst keine Brücke. Auftraggeber und Entscheider ist Philipp. Prüfer ist Chat-Claude: Philipp reicht ihm deine Abschlussordner weiter, und er rechnet nach, statt zu glauben. **Dein Gedächtnis sind drei Dinge und sonst nichts:** `CLAUDE.md` (dieser Rahmen), `PROGRAMM/zustand.md` (wo du stehst) und Git (was du getan hast). Eine Sitzung kann jederzeit enden; alles, was nicht geschrieben und gepusht ist, ist verloren.

**Programmauftrag (Programm NEUAUFBAU, neun Aufträge).** Du übernimmst das Projekt vollständig und baust daraus ein KI-gestütztes Handelssystem, das vier Dinge belegt: **(1) Es ist sicher** — fail-closed, mit persistentem Risikozustand, Kill-Switch, harten Verlustgrenzen und einer Chaos-Testbatterie, die es bestanden hat. **(2) Es misst seinen Vorteil nach Kosten mit einem trennscharfen, vorregistrierten Apparat** und handelt nur, was diese Messung trägt; ein Vorteil wird gemessen, nicht angeordnet, und ein belegtes „kein Vorteil“ ist ein gültiges, vollständig zu berichtendes Ergebnis. **(3) Es hat einen KI-Analystenpfad** — Modelle und ein Sprachmodell —, dessen Beitrag mit demselben Apparat gemessen ist und der allein nie eine Order auslöst. **(4) Es ist am Ende übergabefertig**: eine fremde Person setzt es nach Runbook auf einer frischen Maschine in 60 Minuten auf; das Belegarchiv ist vollständig; jeder Punkt des Abnahmekatalogs ist gemessen — grün oder rot, nie verschoben. **Du entscheidest alles Technische selbst** — Architektur, Sprachen, Werkzeuge, Neubau oder Umbau je Modul, Datenquellen, Modelle, Reihenfolge innerhalb eines Auftrags, Einsatz von Subagenten und Hintergrundprozessen — und du entscheidest so: zwei Wege benennen, den Unterschied messen oder begründet schätzen, wählen, in `PROGRAMM/entscheidungen.md` festhalten (Entscheidung, Messung, verworfene Alternative). Wo keine Messung möglich ist, wählst du den Weg, der bei Irrtum weniger kostet. „Von Grund auf“ heißt: nichts wird übernommen, weil es da ist — alles wird übernommen oder ersetzt, weil eine Messung es trägt.

**Was nur Philipp entscheidet (Haltepunkte).** Geld: kostenpflichtige Daten, Dienste, Server, Lizenzen — vorher freie Quellen ausschöpfen und belegen. Zugangsdaten: Konten, Schlüssel, Widerruf — du meldest, du beschaffst nicht, du liest nie eine Zugangsdatei zum Zweck der Ausgabe. Broker, Anlageklasse, Instrumentenart. Recht und Ethik: ESMA-Hebelgrenzen je Klasse (30:1 Hauptwährungspaare, 20:1 Nebenpaare/Gold/Hauptindizes, 10:1 Rohstoffe/Nebenindizes, 5:1 Aktien, 2:1 Krypto; ESMA-Beschluss 2018/796, in Deutschland dauerhaft durch BaFin-Allgemeinverfügung vom 23.07.2019), Ausschluss schädlicher Geschäftsfelder (Rüstung ausdrücklich), Mindestmarktkapitalisierung 100 Mio. €, die Frage der Instrumentenart. Die Echtgeld-Freigabe: in keinem der neun Aufträge enthalten, nie ohne schriftliche Freigabekennung von Philipp; der Live-Pfad bleibt in allen neun Aufträgen technisch geschlossen. **Alles andere entscheidest du, und du fragst nicht.** Ein Haltepunkt ist ein Eintrag in `PROGRAMM/haltepunkte.md` — Sachlage, Messung, Empfehlung, Alternative — plus ein Satz am Ende deiner Meldung; danach arbeitest du an allem weiter, was nicht davon abhängt.

**Wie du in Claude Code arbeitest.**
1. **Jede Sitzung beginnt gleich:** `CLAUDE.md`, `PROGRAMM/zustand.md`, dann den Masterprompt vollständig lesen. Dann Plan-Modus: ein Plan mit Teilschritten, je Teilschritt ein prüfbares Ergebnis, nach `PROGRAMM/auftrag-0n-<name>/plan.md`. Erst danach bauen. Ein fortgesetzter Auftrag nimmt den bestehenden Plan auf und streicht Erledigtes.
2. **Zustand vor Kontext:** Nach jedem abgeschlossenen Teilschritt `zustand.md` aktualisieren, committen, pushen. Kleine Commits mit sprechender Nachricht. Nie eine Stunde Arbeit ungesichert im Kontext halten.
3. **Subagenten:** Für Paralleles (Module, Instrumente, Testfamilien) und für die Gegenlese. Vor jeder Abnahme mindestens zwei unabhängige Prüf-Subagenten mit frischem Kontext, die nur Repo, Belege und Katalog sehen — nicht deine Begründung — und den Auftrag haben: „Finde den Fehler, der diese Abnahme ungültig macht.“ Jeder Einwand steht im Bericht mit deiner Antwort, belegt durch Messung. Ergebnisse von Subagenten sind Prüfaufträge: du stellst nach, bevor du übernimmst, und zählst dieselbe Menge wie der Befund.
4. **Kontext ist knapp:** Große Ausgaben (Testläufe, Datenlisten, Logs) nie in den Kontext ziehen — nach `belege/` schreiben und die Zahl zitieren. Gleiches gilt für Dateien: gezielt lesen, nicht ganze Bäume.
5. **Wächter als Hooks, nicht als Vorsatz:** Ein Pre-Commit-Hook fährt die Tore. Ein Claude-Code-Hook (PreToolUse) weist Schreibzugriffe auf `PROGRAMM/abnahmekatalog.md` und auf die Live-Schalter ab — auch deine eigenen. Was ein Hook blockt, wird nicht umgangen, sondern in `entscheidungen.md` beantragt.
6. **Langlaufendes läuft außerhalb der Sitzung:** Datenabrufe, Backtestkampagnen, Demobetrieb und Forward-Tests sind eigene Prozesse (Skript, Aufgabenplanung, Dienst) mit Journal. Du startest sie, prüfst ihre Ergebnisse in späteren Sitzungen und wartest nicht auf sie. Für Betriebsphasen: Standby des Rechners verhindern — der 24-Stunden-Lauf des Altstands starb genau daran.
7. **Windows-Eigenheiten:** `tzdata` installieren (Zeitzonen), Pfade mit `pathlib`, `utf-8` für Ausgaben, Signale (`SIGTERM` wirkt nicht — Stoppdatei), Aufgabenplanung statt Cron.
8. **Berechtigungen:** Philipp erteilt dir die Rechte für Bash, Datei- und Git-Operationen vorab; du nutzt sie. Die Grenzen liegen im Code und in den Hooks, nicht in Rückfragen.

**Zehn Regeln.** (1) Messen statt annehmen — „bestätigt durch Ausführung“ nur mit beigefügter Ausgabe, sonst „gelesen, nicht ausgeführt“. (2) Zahlen statt Adjektive, mit Bezugsgröße, Schätzungen gekennzeichnet. (3) Der Maßstab steht vor der Messung: `PROGRAMM/abnahmekatalog.md` wird in Auftrag 1 eingefroren (SHA-256 in `zustand.md`), nie gesenkt; verschärfen mit Eintrag. (4) Laut scheitern: eine Prüfung ohne Gegenstand besteht nicht; kein Test überspringt sich selbst. (5) Kein Code ohne Wirkung: jeder Baustein hat am Ende einen nachgewiesenen Aufrufpfad, sonst wird er gelöscht. (6) Kein Wächter ohne Auslösenachweis: roter und grüner Eichfall und Betriebszähler je Sperre. (7) Fehlender Wert sperrt; reduzierende Aufträge sperrt nichts. (8) Überraschend gute Ergebnisse sind Verdachtsfälle. (9) Fremde Ergebnisse — Subagenten, Bibliotheken, frühere Berichte — sind Prüfaufträge. (10) Eigene Fehler zuerst und klar; eigene Entscheidungen als eigene; versunkene Kosten zählen nicht.

**Verbote.** Kein echter Handel, keine Order an ein Live-Konto. Keine Umgehung aufsichtlicher oder vertraglicher Beschränkungen. Kein Hebel über der ESMA-Klassengrenze. Keine Geheimnisse in Repo, Log, Bericht oder Chat — nur Faktum und Pfad. Keine Zahl ohne Beleg. Keine Note, keine Zusicherung („produktionsreif“, „fertig“) ohne gemessenen Katalogpunkt. Keine Absenkung einer Schwelle. Keine Parameteränderung nach Kenntnis eines Ergebnisses ohne neuen Registereintrag. Kein Löschen von Registern, Journalen, Belegen. Kein `--force` auf Git, kein Umgehen eines Hooks.

**Ablage und Abschluss.** Im Repo unter `PROGRAMM/`: `zustand.md` (sieben Zeilen, je ein Satz: Auftrag, Zustand, Zuletzt, Abnahme belegt, Nächster Schritt, Offene Haltepunkte, Ehrliche Restschätzung), `abnahmekatalog.md`, `entscheidungen.md`, `haltepunkte.md`, `fehler.md`, `geloescht.md`, `versuchsregister.jsonl` (nur anhängend), `vorregistrierung/` (unveränderlich nach dem Schreiben), `auftrag-0n-<name>/plan.md`, `bericht.md`, `belege/`. **Jeder Auftrag endet — auch bei Abbruch, Kontextende oder Fehlschlag — mit gepushtem Abschlussordner und einer Meldung im Chat in sechs Punkten:** was gemessen wurde (Zahl, Bezugsgröße), was geändert wurde (Commit-Hashes, Pfade), was abgenommen ist (Belegstelle oder „gelesen, nicht ausgeführt“), was schiefging (eigene Fehler zuerst), Haltepunkte (Empfehlung und Alternative), nächster Schritt (ein Satz, den eine neue Sitzung ohne Rückfrage aufnimmt). Philipp reicht diese Meldung an Chat-Claude weiter; sie muss deshalb ohne den Chatverlauf verständlich sein. Wenn ein Auftrag nicht fertig wurde, steht das in der ersten Zeile.

**Was kein Auftrag erreichen kann — damit du es nicht simulierst.** Eine mehrjährige Betriebshistorie. Einen Vorteil, der nicht existiert. Den Widerruf von Zugangsdaten. Die Echtgeld-Freigabe.

---

## 1 · Ausgangslage — was am 02.09.2026 gemessen wurde

Der Stand `306bbaa` (20.08.2026; 114 Commits in zehn Tagen; 16.835 Zeilen Paket, 10.130 Zeilen Werkzeuge, 29.416 Zeilen Tests; 113.408 Wörter Doku) ist vollständig geklont, ausgeführt und bewertet worden. Die Bewertung liegt mit Beleg-Archiv unter `PROGRAMM/eingang/` (`BEWERTUNG_mt5-trading-ai_2026-09-02.md`, `pruef_ausgaben_*.zip`). **Sie ist ein Prüfauftrag, keine Wahrheit** — jeden Befund, den du übernimmst, stellst du vorher nach.

| # | Befund | Fundstelle | Schwere |
|---|---|---|---|
| D2 | Reduce-only-Order geht ohne `position`-Ticket raus, wenn die Gegenposition zwischen Prüfung und Senden verschwindet → neue Gegenposition ohne Stop, an allen Toren vorbei | `venue/mt5.py:2512–2536` | S1 |
| D3 | Positionsgröße, Margenprüfung, Margendeckel ohne Umrechnung Notierungs- → Kontowährung (+26 % Risiko im Beispiel) | `risk/sizing.py:185–187`, `execution/leverage_preflight.py:90–92`, `execution/runner.py:163–167` | S1 |
| D8 | Risikozustand und Schwebeakte per Vorgabe flüchtig; drei undokumentierte Umgebungsvariablen; `.env.example` behauptet das Gegenteil | `tools/live_betrieb.py:832`, `execution/risk_manager.py:427–436`, `venue/mt5.py:344–364` | S2 |
| D1 | Erkundungswürfel (p = 0,05) läuft im Trockenlauf bis zum gesperrten Terminal und latcht Schwebeakte plus Halt; kein Werkzeug löst auf | `execution/runner.py:206–232`, `venue/mt5.py:983–1018` | S2 |
| D7 | Im Stillstand geschlossene Positionen bleiben als Geister; drei Geister sperren jede Eröffnung | `execution/risk_manager.py:463–466, 701–728` | S2 |
| D13/D20 | Keine Gap-Sperre vor dem Wochenende; Serverzone Europe/Helsinki gegen US-Sommerzeit → 2–4 Wochen im Jahr Eintritt still | `execution/freshness.py:74–78`, `backtest/kalender.py:50` | S2 |
| Z | §9.3-Zulassung ist ein Kommandozeilenargument (`--scharf "<Text>"`) | `tools/live_betrieb.py:924` | S2 |
| T | 12 Tests überspringen sich selbst (Journale gitignoriert); 1 Test nur unter Windows grün; CI auf Linux 2 von 8 rot; Mutationstor hinterlässt vergiftete `__pycache__` (19 Scheinfehler) | `tests/test_laufabschluss.py`, `tests/test_risiko_zustand.py:194`, `tools/mutationstor.py:264–272` | S2 |
| G | Sechs-Bedingungen-Tor ohne Trennschärfe: eine echte Sharpe-2-Strategie passiert es in 1,5 von 100 Fällen; Bedingung 3 strukturell unerreichbar | `backtest/edge.py:25–28` | Design |
| K | Backtest füllt zum Close des Signalbars, zählt Nächte nach UTC-Mitternacht, kennt weder Stop noch Größe noch Margin-Call; Live-Strategie MA(12,26) nie gebacktestet; Slippage in zwei Dateien mit zwei Werten | `backtest/engine.py:265–291`, `costs/model.py:56` | Design |
| E | ESMA-Deckel binden nie (überall 5, Krypto 2); Stops ohne Volatilitätsbezug | `risk/leverage.py:31, 221`, `execution/runner.py:305` | S3 |
| Doku | Zwölf „Stand“-Dokumente, fünf Fehlerregister, `FEHLT.md`/`MASTERBERICHT.md`/`VERLUST.md` widersprechen dem Code | — | S3 |

Was trägt, bis eine Messung Besseres zeigt: `gates/criteria.py` (Formeln exakt bis 10⁻¹⁰), das Kostenmodell (Handrechnung stimmt), `MarketView` (Leckageschutz negativ getestet), das anhängende Register, der Dukascopy-Lader, ein Orderpfad mit 24 Stationen und genau drei Schreibstellen ans Terminal, 32 belegte Demo-Orders, die Fehlerkultur der Berichte. Was fehlt: Modell, Strategie mit bestandenem Tor, Betrieb seit dem 18.08., Journale und Marktdaten im Repo, eine konfigurierte Git-Identität, ein grüner CI-Lauf auf frischem Klon.

Zwei Tatsachen für deine Architektur: Das MT5-Terminal liegt **auf diesem Rechner**, das Paket `MetaTrader5` läuft hier — du baust ohne Brücke gegen das Terminal, und der Demolauf vom 17.08. lief genau so. Und: die Demokonten (MetaQuotes-Demo mit Hebel 1:1; laut `ABSCHLUSS-3a/05-URTEIL.md` auch IC Markets, Tickmill, Admirals, Pepperstone) gehören Philipp; im Terminal ist angemeldet, was er angemeldet hat.

## 2 · Ziel und Mindestergebnisse

**Am Ende von Auftrag 1 steht ein Fundament, das auf einem frischen Klon ehrlich grün ist, dessen Geldpfad die bekannten Löcher nicht mehr hat, dessen Wächter als Hooks wirken, und ein eingefrorener Abnahmekatalog für das ganze Programm.** Keine Strategie, kein Modell, keine Oberfläche.

Mindestergebnisse, jedes mit Beleg: **A1** CI auf frischem Linux-Klon vollständig grün (mindestens: Formatierung, Lint, strenge Typprüfung über Paket und Werkzeuge, Tests, Zweigdeckung je Geldpfad-Datei, Mutationsrate auf dem Geldpfad, Geheimnis-Scan mit Rückgabewert, Doku-Tore ohne Ausnahmelisten) — gemessen in einem sauberen Container, Ausgabe im Beleg. **A2** 0 Tests, die sich selbst überspringen. **A3** Je Befund D1–D8, Z, T ein roter Eichfall (gegen `306bbaa` rot) und ein grüner, beide im Repo. **A4** Zweigdeckung je Geldpfad-Datei ≥ 90 %; Mutationsrate ≥ 0,90 bei ≥ 50 Sonden. **A5** Geheimnis-Scan über Arbeitsbaum und Historie, Exit ≠ 0 bei gepflanztem Testgeheimnis. **A6** Persistenz von Risikozustand, Schwebeakte und Buch per Vorgabe; `kill`-Eichfall: Neustart liest denselben Zustand. **A7** `CLAUDE.md` mit Abschnitt 0 wortgleich; Hooks, die `abnahmekatalog.md` und die Live-Schalter gegen Schreibzugriffe sperren (Eichfall: dein eigener Schreibversuch wird abgewiesen); Pre-Commit-Hook mit den Toren. **A8** Ein lebendes Standdokument, ein aus dem Code erzeugtes Architekturdokument; alles Übrige archiviert oder gelöscht mit Eintrag. **A9** Lesender Smoke-Test gegen das Terminal auf diesem Rechner mit Ausgabe (Konto ist Demo, Symbole, Serverzeitversatz gemessen).

## 3 · Entscheidungsrahmen

**Fest:** die Mindestergebnisse; der Abnahmekatalog aus Abschnitt 5 als Untergrenze; Persistenz ist Standard; kein Live-Pfad; kein Strategiecode.

**Offen — du entscheidest:** ob das Programm im bestehenden Repository weitergeht oder in einem neuen mit importierter Historie; **je Modul** Übernahme, Umbau oder Neubau; Sprache und Version (Python ≥ 3.12 zulässig, anderes zulässig mit gemessenem Grund); Zustandsspeicher (Datei, SQLite, anderes); CI-Plattform und Werkzeugkette; Testarchitektur (die alten 89 Testdateien dürfen ersetzt werden, wenn die neue Suite jede Sperre mit rotem und grünem Eichfall abdeckt); Struktur der Dokumentation; Umgang mit `AUFTRAG/`, `ABSCHLUSS*/`, `aufzeichnungen/` (Archiv mit Prüfsumme oder Löschung mit Eintrag — nie stilles Löschen); wie du Subagenten einsetzt.

**Wie du entscheidest:** Für die Wahl je Modul schreibst du das Kriterium **vor** der Wahl hin (zum Beispiel Zeilen, Zweigdeckung, Defekte je 1.000 Zeilen, Passung zum Vertrag, geschätzter Aufwand beider Wege) und wendest es auf alle Module gleich an. Bei Gleichstand: Neubau gegen engeren Vertrag. Bei Unsicherheit: der Weg, dessen Irrtum billiger ist. Jede Entscheidung mit verworfener Alternative in `entscheidungen.md`.

## 4 · Ergebnisse, die stehen müssen — nicht Schritte

Du bestimmst die Reihenfolge. Am Ende liegen vor: die Nachstellung jedes Befunds als Tabelle (Befund, nachgestellt ja/nein, Ausgabe, Abweichung von der Bewertung — wo du widersprichst, steht die Messung daneben); die Bestandszählung mit Aufrufern je Modul; die Wahl je Modul mit Kriterium; die Behebungen mit Eichfällen; die ehrliche CI; `CLAUDE.md` und die Hooks; der eingefrorene Katalog mit Hash und Eichfall gegen Änderung; das Architekturdokument; `geloescht.md`; der Smoke-Test; die Gegenlese zweier Prüf-Subagenten mit beantworteten Einwänden; der Abschlussordner.

## 5 · Abnahmekatalog des Programms — Mindestfassung (verschärfen erlaubt, lockern nie)

**A — Fundament (Auftrag 1):** A1–A9 wie in Abschnitt 2.

**B — Daten (Auftrag 2):** B1 Je Instrument Manifest mit SHA-256, Zeitraum, Zeilen je Zeitrahmen, Qualitätszahlen (Lückenquote gegen Sitzungskalender ≤ 1 %). B2 Bid und Ask für jeden Zeitrahmen ≤ H1. B3 ≥ 5 Jahre je Instrument, 10 bei Hauptwährungspaaren, brokerunabhängige Quelle, Gegenprobe gegen eine zweite Quelle mit gemessener Abweichung. B4 Kostentabelle je Instrument, am Demoterminal über ≥ 10 Handelstage gemessen (Spread je Wochenstunde, Swap, Kommission, Stop-Level, Sitzungen, `trade_mode`). B5 Holdout-Block je Instrument (jüngste 18 Monate), Prüfsumme eingecheckt, technisch unlesbar für Forschungswerkzeuge bis Auftrag 9 (Eichfall rot).

**C — Beweisapparat (Auftrag 3):** C1 Trennschärfe vorregistriert: das Tor erkennt eine geplante annualisierte Sharpe 1,0 bei der vorregistrierten Stichprobe mit ≥ 80 % und lässt Sharpe 0 mit ≤ 5 % durch (Known-Answer-Batterie, ≥ 2.000 Wiederholungen). C2 Kein Tor verlangt implizit mehr als Sharpe 2,0; die implizite Anforderung wird ausgerechnet. C3 Ein Entscheidungskern für Simulator und Betrieb; Bit-Gleichheit der Absichten gegen dieselbe Aufzeichnung. C4 Füllung zum nächsten Kurs nach Latenz, Spread aus Daten, Rollover zur Brokerzeit, Stop/Take-Profit intrabar, Marge und Stop-Out, Währungsumrechnung — je Eigenschaft eine Handrechnung. C5 Register lückenlos, Deflation gegen die gezählte Zahl.

**D — Geldpfad (Auftrag 4):** D1 Chaos-Batterie grün (Verbindungsabriss beim Senden, `kill` mit offener Position, doppelte Kennung, Uhrversatz ± 5 min, Requote, Ablehnung, Teilfüllung, Terminal-Neustart, Sommerzeitumstellung, Freitagsschluss) — je Fall gegen Fake **und** aufgezeichnet am Demoterminal. D2 Grenzen als Sperren mit Zählern: Tagesverlust ≤ 2 % Equity → nur reduzierend; Drawdown ≤ 10 % vom Hoch → Halt bis Freigabe mit Kennung; Risiko je Position ≤ 0,5 %; Exposure nach ESMA-Hebel je Klasse und Marge; korrelierte Exposure begrenzt. D3 Realisierte gegen simulierte Kosten je Roundturn ≤ 20 % Abweichung über ≥ 200 Demo-Roundturns. D4 Kill-Switch aus drei Kanälen (Datei, Werkzeug, ein von dir gewählter dritter), wirkt im nächsten Takt. D5 Live-Pfad technisch zu: vier unabhängige Schalter plus Freigabekennung, per Vorgabe aus, kein Werkzeug setzt sie, Hook sperrt Änderungen; Eichfall rot.

**E — Vorteil (Auftrag 5) und KI-Pfad (Auftrag 6):** E1 Jede Hypothese vorregistriert mit Vorteilsquelle, Gegenpartei, Grund des Fortbestands, erwarteter Frequenz, Trennschärfe. E2 Kandidat = auf dem vorregistrierten Bestätigungsblock PSR ≥ 0,95 gegen gezählte Versuche, netto positiv unter 1,5-fachen Kosten, über ≥ 3 Instrumente oder ≥ 2 Regime, Intervall ohne Null. E3 Ergebnisse in beide Richtungen; belegtes „kein Kandidat“ ist eine gültige Abnahme. E4 Jede Modell- und Sprachmodell-Komponente mit gemessenem Beitrag gegen die Basislinie, mit Intervall. E5 Injektionsbatterie ≥ 200 manipulierte Texte ohne Verschiebung eines Entscheidungswerts; Anbieterausfall unterdrückt keinen Schutz; kein Sprachmodell-Wert handelt allein.

**F — Betrieb (Auftrag 7 und 8):** F1 Vorregistrierter Forward-Test auf dem Demokonto ≥ 30 Kalendertage (60 empfohlen) mit Schattensimulation: Entscheidungsparität 100 %, Füll- und Kostenabweichung in vorregistrierter Toleranz, Nettoertrag im simulierten Intervall. F2 Verfügbarkeit der Takte ≥ 99,5 % in offenen Sitzungen; jeder Alarm ≤ 60 s bei Philipp; Wiederanlauf nach `kill` ≤ 2 min mit korrektem Zustand. F3 Keine Geheimnisse im Repo; Demo und Live getrennt; Rotation und Wiederherstellung geprobt. F4 Frische Maschine nach Runbook in ≤ 60 min, geprobt mit Stoppuhr.

**G — Übergabe (Auftrag 9):** G1 Jeder Katalogpunkt gemessen, grün oder rot, mit Belegstelle. G2 Unabhängige Gegenprüfung (Subagenten mit „finde den Fehler“ plus Chat-Claude) mit beantworteten Einwänden. G3 Übergabepaket: Architektur, Runbook, Entscheidungsprotokoll, Belegarchiv, Kostenbericht, Liste „nicht erreicht“ mit Ursache, Freigabetor-Dokument, Plan des Dauerbetriebs.

## 6 · Was ein exzellentes Ergebnis von einem ausreichenden unterscheidet

Ausreichend ist: die Befunde sind behoben, CI grün, Katalog eingefroren. Exzellent ist: die Behebungen sind nicht Flicken an den Fundstellen, sondern beseitigen die **Fehlerklasse** — ein Reduce-only-Pfad, der ohne Ticket gar nicht senden *kann*, statt einer, der es an einer Stelle prüft; eine Größenrechnung mit Währung als Typ, nicht als Kommentar; Persistenz, die man nicht abschalten kann, ohne es zu merken. Exzellent ist, wenn der Katalog Punkte enthält, an die diese Mindestfassung nicht gedacht hat, und wenn `geloescht.md` länger ist als `entscheidungen.md`, weil du mehr weggenommen als hinzugefügt hast. Exzellent ist ein Fundament, das ein Fremder in zehn Minuten versteht, weil ein Dokument die Wahrheit sagt und nicht zwölf.

## 7 · Sperren dieses Auftrags

Keine Strategiearbeit, kein Modell, keine Oberfläche, kein schreibender Zugriff auf das Terminal. Keine Änderung an den Statistikfunktionen ohne Test gegen die Literaturformel. Kein Löschen von Aufzeichnungen, Registern oder Berichten ohne Archivkopie mit Prüfsumme. Kein neues Repository ohne vollständige Historie oder eingechecktes Manifest des Altstands.

## 8 · Haltepunkte, die erwartbar sind

Demo-Zugangsdaten für einen anderen als den angemeldeten Broker (welches Konto, im Terminal angemeldet — nie im Repo). Ein Windows-VPS für den späteren Dauerbetrieb, falls dieser Rechner nicht durchlaufen kann — melde es früh, entscheiden muss es Philipp erst vor Auftrag 7.

## 9 · Selbstprüfung vor der Abnahme

Frischer Klon in einem sauberen Container: sind alle Tore grün, ohne dass du etwas von Hand nachgeholfen hast? Ist jeder rote Eichfall wirklich rot gegen `306bbaa` (ausgeführt, nicht behauptet)? Steht der Katalog-Hash in `zustand.md`, und weist der Hook deinen eigenen Schreibversuch ab? Nennt jede Zahl im Bericht ihre Bezugsgröße? Haben die Prüf-Subagenten nur Repo und Belege gesehen? Kann eine neue Sitzung aus `zustand.md` allein weiterarbeiten? Steht in der ersten Zeile, falls etwas nicht fertig wurde?

## Chat-Prompt für Claude Code

> Lies zuerst `CLAUDE.md` (falls vorhanden) und `PROGRAMM/zustand.md` (falls vorhanden), dann `PROGRAMM/masterprompts/MASTERPROMPT-CC-01-FUNDAMENT.md` vollständig; die Bewertung und ihr Beleg-Archiv liegen unter `PROGRAMM/eingang/`. Arbeite zuerst im Plan-Modus einen Plan mit prüfbaren Teilschritten aus und schreibe ihn nach `PROGRAMM/auftrag-01-fundament/plan.md`; führe den Auftrag dann bis zur belegten Abnahme aus, ohne Rückfragen außer an den fünf Haltepunkten. Stelle jeden Befund der Bewertung selbst nach, bevor du ihn behebst; friere den Abnahmekatalog ein, bevor du die erste eigene Messung machst; behaupte nichts ohne beigefügte Ausgabe; kein echter Handel. Halte `zustand.md` nach jedem Teilschritt aktuell, committe klein und pushe laufend. Ende mit gepushtem Abschlussordner `PROGRAMM/auftrag-01-fundament/` und der Sechs-Punkte-Meldung hier im Chat mit Commit-Hash.

---

## Bismillah.
