# Masterprompt 03 (Claude Code) — Simulator und Beweisapparat

**Programm NEUAUFBAU · Auftrag 3 von 9 · Für Claude Code auf Philipps Windows-Rechner · Unverändert einsetzen · Bis zur belegten Abnahme.**

Dieser Text ist ein Dauerauftrag: Philipp startet ihn mit demselben Chat-Prompt so oft, bis `PROGRAMM/zustand.md` „abgenommen“ sagt. Der Fortschritt liegt nicht in deinem Kontext, sondern in `CLAUDE.md`, `PROGRAMM/zustand.md` und Git. Voraussetzung: Auftrag 2 steht in `PROGRAMM/zustand.md` als abgenommen. Ablage aller neun Masterprompts: `PROGRAMM/masterprompts/` im Repo, unverändert eingecheckt.

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

## 1 · Ausgangslage — was der alte Apparat kann und was ihn wertlos machte

Die Statistik in `gates/criteria.py` ist richtig (bis 10⁻¹⁰ gegen Bailey/López de Prado nachgerechnet); der Leckageschutz in `backtest/engine.py` wirkt; die Kostenbuchung stimmt mit der Handrechnung. **Und trotzdem konnte der Apparat seine Frage nicht beantworten:** Das Tor (`backtest/edge.py`: OoS-Trade-Sharpe ≥ 1,0; DSR > 0,95 gegen 60 Versuche; ≥ 2.000 Trades; drei Folds in Folge; Stress ×1,5; Zufall negativ) verlangt implizit eine annualisierte Sharpe von 4,22. Mit den Repo-Funktionen gemessen: eine echte Sharpe 1,0 passiert es mit 0,1 %, Sharpe 2,0 mit 1,5 %, Sharpe 3,0 mit 12,1 %; eine Strategie ohne Vorteil passiert Bedingung 1 allein mit 17 %. Bedingung 3 war für Strategien mit 44–119 Bars Haltedauer strukturell unerreichbar. Die Zufallsreferenz erzeugt 2.500 Trades und verliert 218 % der Margin — jede Strategie schlägt sie trivial; gefahren wurden 5 statt 1.000 Läufe. Der Backtest füllt zum Close des Signalbars, zählt Nächte nach UTC-Mitternacht statt Broker-Rollover, kennt weder Stop noch Take-Profit noch Positionsgröße noch Margin-Call, handelt fix 1 Lot und damit ein anderes System als der Betrieb. Purge ist 1 Bar bei Haltedauern von Tagen. Zwei Vorregistrierungen im Code mit verschiedenen Zahlen. Das Register kennt ≥ 30 frühere Versuche nicht. **Ein Tor ist erst dann ein Test, wenn vorher ausgerechnet ist, was es erkennen kann.**

## 2 · Ziel und Mindestergebnisse

**Am Ende von Auftrag 3 existiert ein ereignisgetriebener Simulator, der denselben Entscheidungskern fährt wie später der Betrieb, und ein statistischer Apparat, dessen Trennschärfe vorregistriert und an einer Known-Answer-Batterie gemessen ist — bevor er eine echte Hypothese sieht.** Der Apparat sagt zu jedem Tor: „erkennt Sharpe X bei Stichprobe Y mit 80 %“.

Mindestergebnisse: **C1–C5** des Katalogs. Dazu: der Entscheidungskern als Vertrag (reine Funktion: Marktzustand bis t — technisch ohne Zukunft —, Kontozustand, Kalender, Parameter → Absichten mit Grund und Größe; keine Uhr, kein Netz, kein Zufall ohne Saat); Simulator mit Latenz (Vorgabe 250 ms + 150 ms, in Auftrag 4 gemessen), Spread aus Daten, Slippage als kalibrierbares Modell, Kommission, Swap zur Brokerzeit mit Dreifachtag, SL/TP intrabar aus Tickfolge (ohne Ticks: die für die Strategie ungünstigste Reihenfolge), Teilfüllungen, Marge und Stop-Out, Währungsumrechnung mit echten Kreuzkursen, ESMA-Hebel, Sitzungen und Wochenendlücken, Portfolio mit Grenzen, Sizing wie im Betrieb, Kostenstress ×1,5 und ×2,0; Statistik mit PSR, DSR gegen gezählte Versuche und Varianz über die Versuche, MinTRL, Blockbootstrap-Intervalle, Schiefe und Kurtosis aus den Trade-Renditen, kombinatorische purged Kreuzvalidierung mit Embargo ≥ maximale Haltedauer, Walk-Forward, **frequenzgleiche** Zufallsreferenz (≥ 1.000 Permutationen der Einstiegszeiten bei gleicher Trade-Zahl), Regime-Aufteilung, Familienkorrektur, Kostensensitivität als Kurve; ein Trennschärfe-Rechner; Known-Answer-Batterie (Zufallspfad; geplante Sharpe 0,5 / 1,0 / 1,5 / 2,0; Regimewechsel; Fallen: Vorausschau wird technisch verhindert, kostenlose Hochfrequenz zeigt negatives Netto, perfekte Vorausschau zeigt die Obergrenze); Register mit Integritätskette und Typ je Lauf; Vorregistrierungsformat mit Pflichtfeldern; Bit-Gleichheit zweier Läufe und zweier Maschinen; gemessene Laufzeit.

## 3 · Entscheidungsrahmen

**Fest:** die Mindestergebnisse; C2 (kein Tor über implizit Sharpe 2,0); PSR und MinTRL immer ausgewiesen; jede Formel gegen eine unabhängige Zweitimplementierung getestet; keine Hypothese auf echten Daten in diesem Auftrag; Holdout unberührt.

**Offen — du entscheidest:** Umbau oder Neubau von `backtest/`; Ereignisschicht (Tick oder M1 mit Tickfolge); Bibliotheken (`numpy`, `pandas`/`polars`, `scipy`, `statsmodels` zulässig); Parallelisierung; Laufzeitziel (Vorgabe: Universum, M1, zehn Jahre ≤ 30 min auf diesem Rechner — setze ein strengeres, wenn du es misst); Primärmaß der Statistik; Aufbau der Batterie; Speicherformat der Läufe; wie du den Paritätstest gegen synthetische Aufzeichnungen aufbaust, bevor Auftrag 4 echte liefert.

**Wie du entscheidest:** Genauigkeit vor Geschwindigkeit, wenn beides kollidiert — aber miss beides. Ein Modell mit weniger Parametern schlägt eines mit mehr, wenn die Handrechnung beide bestätigt. Wo die Literatur zwei Wege kennt (Bootstrap-Varianten, Deflationsvarianten), nimm den konservativeren und weise den anderen als Sensitivität aus.

## 4 · Ergebnisse, die stehen müssen

Der Kern als Modul mit Vertragstest; der Simulator mit Handrechnungstest je Eigenschaft (50-Pip-Gap wird am Open danach gefüllt; genau eine Nacht über den Rollover; Stop innerhalb der Kerze bei ungünstiger Reihenfolge; Stop-Out bei zu wenig Marge; GBP-Trade auf EUR-Konto mit Kreuzkurs des Zeitpunkts); der Trennschärfe-Rechner mit Beispiel für drei Frequenzen; die Batterie als Tabelle (geplante Sharpe × Erkennungsrate, ≥ 2.000 Wiederholungen; C1 erfüllt); das Register mit Integritätsprüfung; zwei bit-identische Läufe, davon einer in einem Container; die Laufzeit; die Gegenlese; der Abschlussordner.

## 5 · Was ein exzellentes Ergebnis von einem ausreichenden unterscheidet

Ausreichend: der Simulator ist korrekt, das Tor hat Trennschärfe. Exzellent: der Apparat sagt **vor** jedem Lauf, was er nicht sehen kann — und weigert sich, ein Tor zu fahren, dessen Frage die Daten nicht beantworten können (die Antwort „unentscheidbar“ ist ein Ergebnis mit Zahl, kein Fehler). Exzellent ist ein Simulator, dessen Kostenmodell seine eigene Unsicherheit trägt (Slippage als Verteilung mit Kalibrierungsdatum) und der jedes Ergebnis mit dem Satz ausgibt, unter welchen Annahmen es gilt. Exzellent ist eine Batterie, die auch die Fehler des alten Apparats als Testfälle enthält — damit sie nie wiederkommen.

## 6 · Sperren dieses Auftrags

Läufe auf echten Daten nur als Maschinenprobe mit Registertyp und ohne Renditebericht. Kein Zugriff auf den Holdout. Keine Statistikformel ohne Zweitimplementierung. Kein Tor ohne Trennschärfe-Ausweis. Keine Konstante als Versuchszahl.

## 7 · Haltepunkte, die erwartbar sind

Rechenleistung, wenn dieser Rechner das Laufzeitziel nicht erreicht (Preis, Nutzen in Minuten, Alternative mit ihren Kosten in Genauigkeit).

## 8 · Selbstprüfung vor der Abnahme

Erkennt die Batterie Sharpe 1,0 mit ≥ 80 % und Sharpe 0 mit ≤ 5 % — mit Ausgabe? Fängt der Kern eine Strategie, die den nächsten Bar liest? Stimmt jede Handrechnung auf den Cent? Sind zwei Läufe byteidentisch? Steht die implizite Anforderung jedes Tors in Sharpe-Einheiten im Bericht? Hat das Register jeden Lauf dieses Auftrags, auch die abgebrochenen?

## Chat-Prompt für Claude Code

> Lies zuerst `CLAUDE.md` und `PROGRAMM/zustand.md` — Auftrag 2 muss dort als abgenommen stehen —, dann `PROGRAMM/masterprompts/MASTERPROMPT-CC-03-SIMULATOR-BEWEISAPPARAT.md` vollständig. Plane im Plan-Modus nach `PROGRAMM/auftrag-03-simulator/plan.md`, dann führe aus bis zur belegten Abnahme, ohne Rückfragen außer an den fünf Haltepunkten. Ein Entscheidungskern für Simulator und Betrieb; Füllung zum nächsten Kurs nach Latenz; Trennschärfe vor jedem Tor ausgerechnet; Known-Answer-Batterie mit ≥ 80 % Erkennung bei Sharpe 1,0 und ≤ 5 % bei Sharpe 0; kein Tor mit impliziter Anforderung über Sharpe 2,0; keine Hypothese auf echten Daten; Holdout unberührt. `zustand.md` nach jedem Teilschritt, kleine Commits, laufend pushen. Ende mit gepushtem Abschlussordner `PROGRAMM/auftrag-03-simulator/` und der Sechs-Punkte-Meldung hier im Chat mit Commit-Hash.

---

## Bismillah.
