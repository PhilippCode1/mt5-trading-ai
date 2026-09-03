# Masterprompt 07 (Claude Code) — Schattenbetrieb und Forward-Test auf dem Demokonto

**Programm NEUAUFBAU · Auftrag 7 von 9 · Für Claude Code auf Philipps Windows-Rechner · Unverändert einsetzen · Bis zur belegten Abnahme.**

Dieser Text ist ein Dauerauftrag: Philipp startet ihn mit demselben Chat-Prompt so oft, bis `PROGRAMM/zustand.md` „abgenommen“ sagt. Der Fortschritt liegt nicht in deinem Kontext, sondern in `CLAUDE.md`, `PROGRAMM/zustand.md` und Git. Voraussetzung: Auftrag 6 steht in `PROGRAMM/zustand.md` als abgenommen. Ablage aller neun Masterprompts: `PROGRAMM/masterprompts/` im Repo, unverändert eingecheckt.

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

## 1 · Ausgangslage — ein Betriebstag, gegen den alles gemessen wurde

Der Altstand hat genau einen Betriebstag: 21 Läufe am 17./18.08.2026, der längste 18,7 Stunden, gestorben am Standby dieses Rechners. Alle vier Kennzahlen der alten Stufe 10 verfehlen ihr Ziel (Buchtreue 98,5 % gegen 99 %, Ausstiegsverlässlichkeit 78,8 % gegen 95 %, Laufabschluss 90,5 % gegen 95 %, Ausstiegsdeckung 72,7 % gegen 100 %); Alarme gingen in eine Datei, zu keinem Menschen; die Tests dafür überspringen sich auf jedem Klon. Seitdem hat nichts gehandelt. Jetzt gibt es einen Geldpfad mit Persistenz und Chaos-Batterie (Auftrag 4), einen Simulator mit demselben Kern (Auftrag 3), Kandidaten oder ein belegtes „keiner“ (Auftrag 5/6). In beiden Fällen läuft dieser Auftrag — mit Kandidaten als Forward-Test, ohne als Maschinenprobe über dieselbe Dauer, und das Freigabetor-Dokument sagt dann „kein Echtgeld“.

**Die Maschinenfrage ist hier entscheidend:** Der Forward-Test braucht 30 bis 60 Tage ununterbrochenen Betrieb. Dieser Rechner kann das nur, wenn Standby und Aktualisierungsneustarts verhindert sind und niemand ihn zuklappt; die Alternative ist ein Windows-VPS (Geld → Haltepunkt). Das ist die erste Entscheidung dieses Auftrags, und sie liegt bei Philipp — du misst und empfiehlst.

## 2 · Ziel und Mindestergebnisse

**Am Ende von Auftrag 7 hat das System ≥ 30 Kalendertage (60 empfohlen) ununterbrochen auf dem Demokonto gehandelt, mit parallel laufender Schattensimulation, gegen ein vorher eingefrorenes Protokoll — und es liegt ein Freigabetor-Dokument vor, das Philipp mit Zahlen sagt, was für eine Echtgeld-Freigabe erfüllt ist und was nicht.** Die Freigabe selbst ist nicht Teil dieses Auftrags.

Mindestergebnisse: **F1, F2** des Katalogs. Dazu: die Vorregistrierung des Forward-Tests (Kandidaten mit Parameterprüfsummen, Instrumente, Kontogröße, Dauer, Start und Ende, erwartete Verteilung des Tagesertrags mit Intervall aus dem Simulator, Toleranzen für Füllabweichung, Latenz, Kosten, Paritätsanspruch 100 %, Dienstgüteziele, Abbruchkriterien, Kennzahldefinitionen wörtlich); die Schattensimulation (Kern auf dem aufgezeichneten Tickstrom, Vergleich der Absichten bit-genau, Füllkurse in bp, Kosten, Ertragspfad — jede Abweichung mit Ursache, ohne Ursache = Vorfall); der Betrieb rund um die Uhr in offenen Sitzungen als eigener Prozess mit Watchdog, Wiederanlauf aus persistiertem Zustand, Zeitabgleich, Journal mit Prüfsummen; Alarme an Philipp ≤ 60 s nach vorregistrierten Regeln über einen Kanal, den er wirklich liest (Telegram-Bot, E-Mail — du baust ihn, er bestätigt den Empfang einer Probe); Tagesmeldung zur festen Uhrzeit; Wochenbericht mit Gegenlese durch Prüf-Subagenten; wöchentliche Probe des Kill-Switch aus jedem Kanal ohne Gefährdung von Positionen; Vorfallregister (Zeit, Symptom, Ursache, Wirkung, Behebung, Commit, Uhr läuft weiter ja/nein); Messung über das Fenster (Verfügbarkeit, Alarmlatenz, Wiederanlaufzeit nach geprobtem Prozessabbruch, Buchtreue, Ausstiegsverlässlichkeit, Parität, Füllabweichung, Kosten realisiert gegen simuliert, Ertrag gegen Intervall, Analystenkosten); Halbzeit- und Abschlussbericht; `PROGRAMM/freigabetor-echtgeld.md` — für Philipp geschrieben, mit Zahlen: erfüllt/nicht erfüllt je Bedingung, die Risiken, die kein Demo messen kann (Demo → Live-Füllung bei einem Broker, der Gegenpartei ist; Kapazität; Regimewechsel), deine Empfehlung, und nur bei erfüllten Bedingungen ein Stufenplan mit Mindestgröße, Haltepunkten und Abbruchkriterien je Stufe; das Dokument beschreibt den Freigabemechanismus und setzt ihn nicht.

## 3 · Entscheidungsrahmen

**Fest:** Vorregistrierung vor dem Start, unveränderlich; ≥ 30 Tage; Demokonto nur; keine Änderung an Parametern, Grenzen, Kandidaten, Kennzahldefinitionen im Fenster — wer ändert, startet die Uhr neu und schreibt es ins Register; jeder Vorfall im Bericht; keine Kennzahl, die ihren Nenner verkleinert; keine Freigabekennung, kein Live-Schalter.

**Offen — du entscheidest:** Dauer oberhalb des Minimums; Kandidaten (alle tragenden; ohne Kandidaten die beste Basislinie als gekennzeichnete Maschinenprobe); parallele Demokonten (Zugangsdaten → Haltepunkt); Alarmkanal und Berichtsform; Überwachung; ob eine Fehlerbehebung im Geldpfad die Uhr weiterlaufen lässt (nur, wenn sie keinen Entscheidungswert berührt — deine Begründung im Vorfall).

**Wie du entscheidest:** Alles, was im Fenster passiert, wird protokolliert, bevor es bewertet wird. Bei Zweifel, ob eine Änderung einen Entscheidungswert berührt: die Uhr neu starten — ein längerer Test ist billiger als ein ungültiger.

## 4 · Ergebnisse, die stehen müssen

Die unveränderte Vorregistrierung mit Prüfsumme; die Paritätstabelle; Füll- und Kostenabweichungen; Ertrag gegen Intervall; das Vorfallregister mit Ursachen; die Dienstgütetabelle; die geprobten Kill-Switch-Kanäle; Philipps bestätigter Alarmempfang; Halbzeit- und Abschlussbericht; das Freigabetor-Dokument; die wöchentlichen Gegenlesen; der Abschlussordner.

## 5 · Was ein exzellentes Ergebnis von einem ausreichenden unterscheidet

Ausreichend: 30 Tage gelaufen, Zahlen berichtet. Exzellent: die Schattensimulation und der Betrieb haben denselben Ertragspfad, und wo nicht, steht die Ursache mit Zahl — der Simulator ist damit **kalibriert**, nicht nur benutzt. Exzellent ist ein Freigabetor-Dokument, das ein Fremder liest und danach weiß, was er riskiert, in Euro und Wahrscheinlichkeit, ohne ein einziges Adjektiv. Exzellent ist ein Betrieb, der in 30 Tagen keinen Vorfall ohne Ursache hatte — nicht keinen Vorfall.

## 6 · Sperren dieses Auftrags

Keine Änderung im Fenster ohne Neustart der Uhr. Keine Order an ein Nicht-Demokonto. Kein Vorfall außerhalb des Berichts. Keine Nennerverkleinerung. Keine Freigabekennung, auch nicht „zum Testen“.

## 7 · Haltepunkte, die erwartbar sind

Die Maschine (dieser Rechner ohne Standby oder Windows-VPS). Ein zweites Demokonto. Ablauf des Demokontos im Fenster. Verlängerung nach Uhr-Neustarts. Die Echtgeld-Freigabe — ausdrücklich nicht in diesem Auftrag entschieden.

## 8 · Selbstprüfung vor der Abnahme

Ist die Vorregistrierung byteidentisch mit dem Stand vor dem Start (Prüfsumme)? Liegt für jede Paritätsabweichung eine Ursache vor? Hat Philipp eine Alarmprobe wirklich empfangen (seine Bestätigung im Beleg)? Lief der Betrieb ohne offene Sitzung (Journal-Zeitstempel über Nächte und Wochenenden)? Sagt das Freigabetor-Dokument bei jeder Bedingung erfüllt/nicht erfüllt mit Zahl? Enthält es die Risiken, die kein Demo messen kann?

## Chat-Prompt für Claude Code

> Lies zuerst `CLAUDE.md` und `PROGRAMM/zustand.md` — Auftrag 6 muss dort als abgenommen stehen —, dann `PROGRAMM/masterprompts/MASTERPROMPT-CC-07-SCHATTENBETRIEB-FORWARDTEST.md` vollständig. Plane im Plan-Modus nach `PROGRAMM/auftrag-07-forwardtest/plan.md`; kläre als Erstes die Maschinenfrage als Haltepunkt (dieser Rechner ohne Standby oder Windows-VPS) und führe dann aus bis zur belegten Abnahme, ohne weitere Rückfragen außer an den fünf Haltepunkten. Forward-Test vorregistriert und eingefroren; mindestens 30 Kalendertage auf dem Demokonto als eigener Prozess mit Schattensimulation und Paritätsprüfung; Alarme an mich innerhalb 60 s über einen Kanal, dessen Probe ich bestätige; Tagesmeldung; keine Parameteränderung im Fenster; Live-Pfad bleibt zu; am Ende das Freigabetor-Dokument mit Zahlen — die Freigabe selbst entscheide ich. In jeder Sitzung Journale prüfen, `zustand.md` fortschreiben, committen, pushen. Ende mit gepushtem Abschlussordner `PROGRAMM/auftrag-07-forwardtest/` und der Sechs-Punkte-Meldung hier im Chat mit Commit-Hash.

---

## Bismillah.
