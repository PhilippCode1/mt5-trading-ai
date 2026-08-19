# Haltepunkte

*Was nur der Auftraggeber entscheiden kann. Je Eintrag: Sachlage, was gemessen wurde,
Empfehlung, Alternative. Der ausführende Agent entscheidet hier nichts.*

---

## H-001 — Die Halal-Vorfrage ist unbeantwortet

**Grundlage:** §4 des Auftrags („Der offenen Halal-Vorfrage"), zugleich Abbruchbedingung 4
des Standes selbst.

**Sachlage.** `HALAL-VORFRAGE.md` liegt fertig im Wurzelverzeichnis: eine Vorlage für eine
Fatwa-Anfrage an einen qualifizierten Gelehrten, mit drei getrennten Fragen — (1) kein
Eigentum am Basiswert, (2) Margin und Hebel, (3) Finanzierungskosten über Nacht. Das
Dokument ist ausdrücklich so verfasst, dass es **unverändert** weitergegeben werden kann,
und es hält fest, dass das Produktetikett „swap-frei" allein Frage 3 berührt und zu den
Fragen 1 und 2 nichts sagt.

**Gemessen:** Der Stand des Vorhabens führt diese Bedingung als **„offen — keine der drei
Fragen beantwortet"** (`ABSCHLUSS-3a/05-URTEIL.md`, Tabelle in §3, Zeile 4). Gelesen, nicht
ausgeführt — es gibt nichts auszuführen; die Antwort kann nur von außen kommen.

**Warum das jetzt zählt.** Die gewählte Anlageklasse ist der Differenzkontrakt. Alle
folgenden Stufen bauen darauf. Fällt die Antwort negativ aus, ist nicht eine Stufe
betroffen, sondern die Instrumentenwahl — und damit der größte Teil dessen, was in Stufe 1
bis 5 entstünde.

**Empfehlung:** Die Anfrage jetzt versenden, vor Stufe 1. Sie kostet nichts und läuft
parallel; die Antwortzeit ist die einzige Größe, die sich durch frühen Versand verkleinern
lässt.

**Alternative:** Weiterarbeiten und die Frage offenhalten. Zulässig, solange kein echtes
Kapital eingesetzt wird — aber jede Stunde Arbeit an CFD-spezifischer Logik ist dann
Arbeit unter Vorbehalt.

**Der Agent tut hier nichts von selbst.** Nach §4 wird gemeldet, nicht unterstellt.

---

## H-002 — Zwei Verträge widersprechen sich darüber, ob Stufe 3 zulässig ist

**Grundlage:** §4 des Auftrags („Dem Ergebnistor aus Abschnitt 6, Stufe 3"), zugleich §5
und §6 des projekteigenen `ABBRUCH.md`.

**Sachlage.** Der Stand trägt eine eigene, vorab bezifferte Abbruchregel. Ihr Zustand am
2026-08-17, gemessen und in `ABSCHLUSS-3a/05-URTEIL.md` §3 dokumentiert:

| # | Bedingung | Stand |
|---|---|---|
| 1 | Kostentor rot | nicht ausgelöst (M1 grün, **ohne Reserve**; M2 gerissen: 13 von 18 Kostenzeilen über 50 % bei 4 Round-Turns/Tag und Hebel 5) |
| 2 | Kein Kandidat übersteht die Deflation | **nicht** ausgelöst — höchster Deflated Sharpe 0,686 gegen Schwelle 0,95, aber der Messzeitpunkt ist 60 Versuche und das Register hält 7 |
| 3 | Realisierte Kosten weichen ab | **ausgelöst mangels Messung** (kein Handelsbetrieb) |
| 4 | Halal-Vorfrage negativ | offen → H-001 |
| 5 | Aufwandsgrenze | Frist **2027-08-17**, Uhr läuft |
| 6 | Keine benennbare Vorteilsquelle | **ausgelöst** — fünf Zwangslagen benannt und gemessen, keine trägt die Kosten |

Die Empfehlung dieses Urteils lautet wörtlich: **„Bedingtes Halten (M5 gelb). Keine
Strategiearbeit."**

**Der Widerspruch.** Der neue Auftrag verlangt in Stufe 3, die Entscheidungskette gegen die
Historie zu fahren. Ob das „Strategiearbeit" im Sinne des alten Vertrags ist, entscheidet
darüber, ob Stufe 3 überhaupt begonnen werden darf. Der Agent legt diese Auslegung nicht
selbst fest — nach §6 des neuen Auftrags („Der Maßstab steht vor der Messung… Eine Schwelle
wird nie gesenkt, damit etwas durchgeht") wäre das genau die verbotene Richtung.

**Was gemessen ist und den Widerspruch entschärft.** Das Urteil unterscheidet zwei Budgets,
und die Unterscheidung ist erst durch eine Berichtigung sichtbar geworden: das Paketbudget
(5 von 12 übrig, ausdrücklich **nicht** als Vorrat für weitere Anläufe auf dieselben fünf
Zwangslagen) und das Kampagnenbudget aus `ABBRUCH.md` §2 (**53 von 60 Versuchen offen**,
befristet bis 2027-08-17). Bedingung 6 wurde an der Familie der **Ereignisstudien**
ausgelöst, nicht an der Entscheidungskette.

**Empfehlung:** Stufe 1 und Stufe 2 **jetzt freigeben** — beide sind Datengrundlage und
Zeitachsenhygiene, keine Strategiearbeit, und `ABSCHLUSS-3a/05-URTEIL.md` §5 führt genau
diese Bausteine als „Wert unabhängig vom Urteil". Vor Beginn von **Stufe 3** eine
schriftliche Feststellung des Auftraggebers, ob der Simulatorlauf auf der
Entscheidungskette gegen das Kampagnenbudget läuft (dann: zulässig, Versuchszähler steigt
von 7) oder ob „keine Strategiearbeit" auch ihn einschließt (dann: der Auftrag endet mit
Befund (B) aus §1, und das ist nach §1 ein gültiges Ergebnis).

**Alternative:** Stufe 3 ohne diese Feststellung beginnen. Nicht empfohlen — ein Ergebnis,
das unter einem ausgelösten Abbruchkriterium entsteht, ist hinterher nicht mehr
freizusprechen von dem Verdacht, dass die Regel gebeugt wurde, um weitermachen zu dürfen.

---

## H-003 — Zugangsdaten im verworfenen Stand, Widerruf steht aus

**Grundlage:** §4 des Auftrags („Zugangsdaten"), §9.3 („Nur der Kontoinhaber"), Sperre V7.

**Sachlage.** Der Prüfbericht vom 2026-08-19 zum verworfenen Stand `bitget-btc-ai` hat
festgestellt, dass im dortigen Arbeitsverzeichnis Zugangsdaten im Klartext liegen — ein
Börsenschlüsselsatz, ein langlebiges Zugangstoken für die Bedienoberfläche, ein
Anbieterschlüssel für ein Sprachmodell und ein Nachrichten-Token, in drei Kopien
(Hauptdatei und zwei Sicherungskopien).

**Nach Sperre V7 wird hier ausschließlich das Faktum und der Pfad genannt, kein Wert:**

- `C:\Users\Acer\OneDrive\Documents\Cursor1\bitget-btc-ai\.env.production`
- `C:\Users\Acer\OneDrive\Documents\Cursor1\bitget-btc-ai\.env.local.backup`
- `C:\Users\Acer\OneDrive\Documents\Cursor1\bitget-btc-ai\.env.production.backup`

Die Dateien sind **nicht** in der Versionsverwaltung — das ist geprüft und war das erste,
was geprüft wurde. Sie liegen jedoch in einem Verzeichnis, das über einen Cloud-Ordner
synchronisiert wird, und es existieren daneben zwei vollständige Archive desselben Standes
(`bitget-btc-ai.zip`, `bitget-btc-ai.7z`, zusammen rund 1,4 GB), deren Inhalt in dieser
Stufe **nicht** geöffnet wurde.

**Warum das jetzt zählt.** Mit der Entscheidung E-001 wird dieser Stand nicht weiter
gepflegt. Ein aufgegebenes Verzeichnis wird nicht mehr angesehen — die Schlüssel darin
bleiben aber gültig, bis sie widerrufen werden.

**Empfehlung:** Die betroffenen Schlüssel beim jeweiligen Anbieter widerrufen und neu
ausstellen, unabhängig davon, ob eine Kompromittierung bekannt ist. Danach die drei
Dateien und die beiden Archive entfernen. Der Agent kann das nicht — Widerruf und
Neuausstellung kann nur der Kontoinhaber (§9.3).

**Alternative:** Die Dateien nur löschen, ohne zu widerrufen. Nicht empfohlen: das
beseitigt die Kopie, nicht die Gültigkeit.

---

*Stand dieser Datei: 3 offene Haltepunkte, keiner davon blockiert Stufe 1.*
