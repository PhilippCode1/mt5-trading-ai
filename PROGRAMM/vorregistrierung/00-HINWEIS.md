# Vorregistrierung — Regeln dieses Ordners

1. Jede Datei hier wird **vor** der Messung geschrieben, die sie beschreibt, und danach
   nicht mehr verändert. Der Commit, der sie anlegt, ist ihr Zeitstempel.
2. Eine Vorregistrierung nennt: Hypothese oder Messziel, Datenbereich, Stichprobe,
   Tor mit Zahlen, Trennschärfe (ab Auftrag 3), erwartete Frequenz, Zahl der Versuche,
   die sie verbraucht.
3. Eine Änderung nach Kenntnis eines Ergebnisses ist keine Änderung, sondern ein neuer
   Eintrag mit Verweis auf den alten (Verbot aus dem Rahmen: keine Parameteränderung ohne
   neuen Registereintrag).
4. Die Prüfsumme (SHA-256) jeder Datei steht im zugehörigen `bericht.md` des Auftrags;
   der Pre-Commit-Hook lehnt Änderungen an vorhandenen Dateien dieses Ordners ab
   (ab Auftrag 1, Teilschritt 2).

Auftrag 1 registriert keine Hypothese: er misst Bestand und Befunde, keine Strategie.
