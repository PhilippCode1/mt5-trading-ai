# Masterprompt 09 (Claude Code) — Abnahme und Übergabe

**Programm NEUAUFBAU · Auftrag 9 von 9 · Für Claude Code auf Philipps Windows-Rechner · Unverändert einsetzen · Bis zur belegten Abnahme.**

Dieser Text ist ein Dauerauftrag: Philipp startet ihn mit demselben Chat-Prompt so oft, bis `PROGRAMM/zustand.md` „abgenommen“ sagt. Der Fortschritt liegt nicht in deinem Kontext, sondern in `CLAUDE.md`, `PROGRAMM/zustand.md` und Git. Voraussetzung: Auftrag 8 steht in `PROGRAMM/zustand.md` als abgenommen. Ablage aller neun Masterprompts: `PROGRAMM/masterprompts/` im Repo, unverändert eingecheckt.

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

## 1 · Ausgangslage — die Versuchung, die dieser Auftrag bestehen muss

Der Altstand hat sich am 17.08.2026 um 18:14 für „abgeschlossen“ erklärt und 40 Minuten später den größten Ausbau seiner Geschichte begonnen; er hat „System abnahmefertig“ geschrieben und widerrufen; er hat nach dem Befund (B) sieben Stufen darüber hinweggebaut; seine Kennzahlen wuchsen, sein Gegenstand nicht. Die Regel aus seinem eigenen Vertrag — „Wenn eine Handlung eine Kennzahl verbessert, ohne die Wirklichkeit zu ändern, ist das der Beweis, dass du sie nicht ausführen darfst“ — ist die Regel dieses Auftrags. Der Abnahmekatalog ist seit Auftrag 1 eingefroren (Hash in `zustand.md`, Hook gegen Änderung). Der Holdout ist seit Auftrag 2 gesperrt. Acht Abschlussordner liegen vor. Jetzt wird gemessen, was ist.

## 2 · Ziel und Mindestergebnisse

**Am Ende von Auftrag 9 ist jeder Punkt des Abnahmekatalogs auf einer frischen Maschine gemessen und mit Belegstelle berichtet — grün oder rot, keine Schwelle bewegt —, der Holdout ist genau einmal für die Endkandidaten geöffnet worden, eine unabhängige Gegenprüfung hat versucht, die Abnahme zu Fall zu bringen, und ein Übergabepaket liegt vor, mit dem eine fremde Person das System aufsetzen, betreiben, verstehen und weiterentwickeln kann. Philipp bekommt das Freigabetor-Dokument in endgültiger Fassung.** Fertig heißt: alles gemessen — nicht: alles grün.

Mindestergebnisse: **G1–G3** des Katalogs. Dazu: die Frischmaschinen-Probe in einem sauberen Container nur mit dem Runbook (Zeit; CI vollständig; Known-Answer-Batterie vollständig; Chaos-Batterie gegen Fake; drei Kernzahlen früherer Aufträge bit-identisch reproduziert — ein Simulatorlauf, ein Modelltraining, eine Kostenrechnung); der Holdout genau einmal (Vorregistrierung der Endkandidaten mit Parameterprüfsummen, erwarteten Ergebnissen aus Bestätigungsblock und Forward-Test, Toleranzen; Entschlüsselung; ein Lauf je Kandidat; Register; PSR, Intervall, Kostenstress gegen die Vorregistrierung; Widerspruch zum Bestätigungsblock heißt „nicht tragend“, wird berichtet, nicht repariert; ohne Kandidaten entfällt es mit Vermerk); der Katalog Punkt für Punkt (Messvorschrift ausgeführt, Ausgabe, Urteil, bei rot Ursache und was fehlt — Zeit, Daten, Geld, Entscheidung, Arbeit; Hash vor und nach der Messung identisch mit Auftrag 1); die Gegenprüfung (mindestens drei Prüf-Subagenten mit frischem Kontext und verschiedenen Blickwinkeln — Code, Statistik, Belege und Zählung — mit dem Auftrag „finde den Fehler, der diese Abnahme ungültig macht“; jeder Fund durch Ausführung nachgestellt; bestätigte behoben als Vorfall mit Wiederholung der Messung; nicht behobene bleiben rot; die Fundliste vollständig im Bericht; dazu Chat-Claude als externer Prüfer, dem Philipp das Paket gibt); `UEBERGABE/` im Repo und als ZIP: Architektur (aus dem Code erzeugt), Runbook, Betriebshandbuch, Entscheidungsprotokoll, Fehlerregister, Belegarchiv aller neun Aufträge, Kostenbericht, Katalogtabelle, Liste „nicht erreicht“ mit Ursache, Freigabetor-Dokument endgültig, Plan des Dauerbetriebs (Hintergrundläufe: Forschungsstrecke, Forward-Test-Fortsetzung, Sicherung, Kostenbericht, Alarmprobe), die Seite „Was ein Nachfolger zuerst liest“, `CLAUDE.md` auf dem Endstand; die Meldung an Philipp in seiner Sprache ohne Note und ohne „bestes“: was das System ist, was es bewiesen hat (drei wichtigste Zahlen), was nicht, was von allein läuft, was er entscheiden muss (Echtgeld mit den Zahlen des Freigabetors und deiner Empfehlung, H-003, offene Haltepunkte), die ehrliche Restschätzung (Betriebshistorie in Monaten, Kapital, Brokerwahl, Restrisiko Demo → Live).

## 3 · Entscheidungsrahmen

**Fest:** keine Schwelle bewegt (Hash beweist es); keine neue Hypothese, kein Nachjustieren, kein zweiter Holdout-Lauf; Fehler, die die Messung findet, werden behoben — jede Behebung ist ein Vorfall mit Ursache, Commit und Wiederholung der betroffenen Messung; kein „fertig“, „produktionsreif“, „bestes“ ohne die Katalogtabelle daneben; keine Freigabekennung; die Liste „nicht erreicht“ ist Pflicht.

**Offen — du entscheidest:** Reihenfolge der Messungen; Form des Übergabepakets oberhalb der Mindestfassung; Zusammensetzung der Prüf-Subagenten; wie du die drei Kernzahlen wählst (die aussagekräftigsten, nicht die bequemsten).

**Wie du entscheidest:** Im Zweifel misst du noch einmal, statt zu argumentieren. Ein Fund der Gegenprüfung, den du nicht durch Ausführung entkräften kannst, bleibt stehen — auch wenn du ihn für falsch hältst.

## 4 · Ergebnisse, die stehen müssen

Die Frischmaschinen-Probe mit Zeit; die drei reproduzierten Kernzahlen; der Holdout-Lauf mit Vorregistrierung und Register (oder Vermerk); die vollständige Katalogtabelle mit unverändertem Hash; die Gegenprüfung mit allen Funden und ihrem Zustand; das Übergabepaket im Repo und als ZIP; die Meldung an Philipp; `zustand.md` mit „Programm NEUAUFBAU abgeschlossen — <n> von <m> Katalogpunkten grün, Belege in UEBERGABE/“.

## 5 · Was ein exzellentes Ergebnis von einem ausreichenden unterscheidet

Ausreichend: der Katalog ist gemessen, das Paket liegt vor. Exzellent: die Liste „nicht erreicht“ ist so konkret, dass jeder rote Punkt seine Ursache und seinen Preis nennt — „fehlen 4 Monate Betrieb“, „braucht Entscheidung X“, „kostet Y“ — und niemand fragen muss, warum. Exzellent ist eine Gegenprüfung, die etwas gefunden hat; eine, die nichts findet, hat nicht gesucht. Exzellent ist eine Meldung an Philipp, die er ohne dich versteht und nach der er weiß, was er riskiert, wenn er Ja sagt, und was er verliert, wenn er Nein sagt — in Zahlen.

## 6 · Sperren dieses Auftrags

Keine Schwelle wird bewegt. Keine neue Hypothese, kein Nachjustieren, kein zweiter Holdout-Lauf. Keine Zusicherung ohne Katalogtabelle. Keine Freigabekennung, kein Live-Schalter. Kein Verschweigen eines roten Punkts.

## 7 · Haltepunkte, die erwartbar sind

Der Holdout-Schlüssel, wenn Philipp ihn hält. Die Echtgeld-Freigabe — vorbereitet, nicht entschieden. Die laufenden Kosten des Dauerbetriebs als Monatsbetrag. H-003, falls noch offen.

## 8 · Selbstprüfung vor der Abnahme

Ist der Katalog-Hash vor und nach der Messung derselbe wie in Auftrag 1? Ist jeder Punkt mit ausgeführter Messvorschrift und Ausgabe belegt? Wurde der Holdout genau einmal je Kandidat geöffnet — Register zeigt es? Hat die Gegenprüfung mindestens einen Fund geliefert, und steht jeder Fund mit Zustand im Bericht? Schafft ein Fremder mit dem Paket die frische Maschine? Enthält die Meldung an Philipp keine Note und kein „bestes“? Steht in der Liste „nicht erreicht“ bei jedem Punkt die Ursache?

## Chat-Prompt für Claude Code

> Lies zuerst `CLAUDE.md` und `PROGRAMM/zustand.md` — Auftrag 8 muss dort als abgenommen stehen —, dann `PROGRAMM/masterprompts/MASTERPROMPT-CC-09-ABNAHME-UEBERGABE.md` vollständig. Plane im Plan-Modus nach `PROGRAMM/auftrag-09-abnahme/plan.md`, dann führe aus bis zur belegten Abnahme, ohne Rückfragen außer an den fünf Haltepunkten. Jeder Katalogpunkt auf einer frischen Maschine gemessen und grün oder rot berichtet; Hash des Katalogs unverändert; Holdout genau einmal für die vorregistrierten Endkandidaten; Gegenprüfung durch mindestens drei Prüf-Subagenten mit dem Auftrag, die Abnahme zu widerlegen; Übergabepaket im Repo und als ZIP; kein Live-Schalter — die Echtgeld-Freigabe entscheide ich mit deinem Freigabetor-Dokument. `zustand.md` nach jedem Teilschritt, kleine Commits, laufend pushen. Ende mit gepushtem Abschlussordner `PROGRAMM/auftrag-09-abnahme/` und der Meldung an mich hier im Chat — in meiner Sprache, ohne Note, mit den drei wichtigsten Zahlen und der Liste „nicht erreicht“.

---

## Bismillah.
