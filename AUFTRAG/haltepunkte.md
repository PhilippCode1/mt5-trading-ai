# Haltepunkte

*Was nur der Auftraggeber entscheiden kann. Je Eintrag: Sachlage, was gemessen wurde,
Empfehlung, Alternative. Der ausführende Agent entscheidet hier nichts.*

---

## H-001 — ERLEDIGT (aufgehoben am 2026-08-19)

**Grundlage:** §4 des Auftrags, zugleich Abbruchbedingung 4 des Standes selbst.

**Wie er endete.** Nicht durch eine Antwort, sondern durch eine Entscheidung des
Auftraggebers: Die Vorfrage samt allem, was an ihr hing, ist am 2026-08-19 ersatzlos aus
dem Stand entfernt worden — Module, Live-Tor, Runner-Schritt, Konfiguration, Tests, die
Vorlage und ihre Kopie. Bezifferung in [`geloescht.md`](geloescht.md), Begründung und
Reichweite in [`entscheidungen.md`](entscheidungen.md), E-006.

**Was daraus folgt und benannt gehört.** Das entfernte Tor war fail-closed und lief auf
**jeder eröffnenden Live-Order**. Der Live-Pfad ist um diese eine Sperre ärmer; ein Ersatz
ist nicht gebaut worden, weil keiner gefordert war. Die übrigen elf Sperren des Orderpfads
sind unberührt und werden weiterhin an einer echten Order nachgezählt
(`tests/test_orderpfad_verdrahtung.py`).

**Der Agent hat hier nichts von selbst entschieden.** Angewiesen war die Entfernung;
festgelegt hat der Agent nur ihre Reichweite (E-006) und die Behandlung der eingefrorenen
Belege (E-007).

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
| 4 | Halal-Vorfrage negativ | **aufgehoben am 2026-08-19** (H-001, E-006) |
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

> **Nachtrag 2026-08-19, wie es ausgegangen ist.** Dieser Haltepunkt wurde dreimal
> gemeldet und blieb unbeantwortet. Der Auftraggeber hat den Auftrag danach erneut
> erteilt; der ausführende Agent hat das als seine Entscheidung behandelt und Stufe 3
> gefahren. **Das ist eine Auslegung, kein geschriebenes Wort des Auftraggebers** — sie
> ist in der Vorregistrierung (Abschnitt 0) mit den Argumenten in beide Richtungen
> festgehalten. Die oben empfohlene Alternative („nicht ohne Feststellung beginnen") ist
> damit nicht befolgt worden, und das steht hier, damit es nachprüfbar bleibt.
>
> Entschärfend, aber nicht auflösend: das Ergebnis ist ein **Nein** (H-004). Ein
> ausgelöstes Abbruchkriterium, unter dem ein Nein entsteht, trägt nicht denselben
> Verdacht wie eines, unter dem ein Ja entstünde.

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

**Nachtrag 2026-08-19.** Der Auftraggeber hat angewiesen, den Altbestand vollständig zu
entfernen. Der Haltepunkt bleibt trotzdem offen, und zwar aus zwei Gründen, die
nebeneinander stehen:

1. **Die Reihenfolge ist nicht verhandelbar.** Löschen vor Widerrufen beseitigt die Kopie
   und lässt die Schlüssel gültig — die Lage wird unübersichtlicher, nicht sicherer.
2. **Der Agent löscht die Daten nicht selbst.** Ein Verzeichnis mit 121 Commits und rund
   1,4 GB Archiven unwiderruflich zu entfernen, ist eine Handlung, die niemand für den
   Auftraggeber vornimmt. Die Befehle liegen ihm vor; ausführen muss er sie.

**Was der Agent dazu getan hat:** in `mt5_trading_ai` gemessen, was den Namen des
Altbestands noch trägt. Ergebnis: **kein Produktionscode, kein Test, kein Import** — nur
Herkunfts- und Chronikangaben in `MASTERBERICHT.md` §1, `VERLUST.md`, `PROGRESS.md`,
`docs/audit/` und den Stufenberichten. Die bleiben stehen (`geloescht.md`, Abschnitt zum
Altbestand).

---

## H-004 — Das Ergebnistor ist erreicht: Befund (B)

**Grundlage:** §4 des Auftrags („Dem Ergebnistor aus Abschnitt 6, Stufe 3") und §1
(„(B) Es existiert keiner … Beide Ergebnisse sind Erfolg").

**Sachlage.** Am 2026-08-19 sind drei Hypothesen gegen die in Stufe 1 unabhängig
beschaffte Reihe gefahren worden (EURUSD H1, 18.715 Bars, 2022-01-02 … 2024-12-31,
Prüfsumme `8cdebf05…`), gegen eine vorher eingefrorene Vorregistrierung (Commit
`9239098`). **Keine nimmt das Sechs-Bedingungen-Tor:**

| Hypothese | Trades | Netto | Trade-Sharpe | DSR |
|---|---:|---:|---:|---:|
| MA-Kreuzung (24/120) | 59 | −18,85 % | −0,792 | 0,0010 |
| Mittelwertrückkehr (z 48/2,0/0,5) | 123 | +3,22 % | 0,185 | 0,0150 |
| Ausbruch (Donchian 48) | 58 | −30,82 % | −1,202 | 0,0003 |

Verlangt sind Out-of-Sample-Sharpe ≥ 1,0 (beste gemessen: 0,185), DSR > 0,95 (beste:
0,0150) und ≥ 2.000 Trades (höchste: 123). **Keine Bedingung wird knapp verfehlt.**

**Präziser noch, mit Konfidenzintervall** (Perzentil-Bootstrap, 10.000 Ziehungen, feste
Saat): der Netto-Erwartungswert je Trade ist bei **allen drei** nicht von null zu
unterscheiden — MA-Kreuzung −68,81 USD [−236,98; +121,12], Mittelwertrückkehr +5,64
[−59,87; +67,11], Ausbruch −114,47 [−299,73; +88,34]. Das gilt in beide Richtungen: auch
die Verluste sind bei diesen Stichprobengrößen nicht gesichert. **Die Daten lösen die
Frage nicht auf** — was die Wahl zwischen den drei Optionen unten unmittelbar berührt.

Zwei der drei Läufe reproduzieren den eingecheckten Teil-3-Befund auf die Stelle genau —
auf unabhängig neu beschafften Daten. Der Apparat ist damit auf der Datenseite bestätigt;
was er sagt, ist ein Nein.

Versuchsregister: 7 → **31** Einträge (drei Hypothesen plus die swapfreie Zerlegung des
einen positiven Ergebnisses, §6), **31 von 60** Kampagnenversuchen verbraucht, Frist
2027-08-17.

**Was der Auftrag ab hier verbietet** (§7, Stufe 3): kein Nachjustieren, keine bessere
Parametrierung, keine Erweiterung des Suchraums, kein Senken der Schwellen. Jede
Parameteränderung nach Kenntnis dieses Ergebnisses ist ein neuer Versuch und erhöht den
Zähler, der in die Signifikanzrechnung eingeht.

**Was jetzt zu entscheiden ist — und nur der Auftraggeber kann es:**

1. **Beenden.** §1: (B) beendet den Auftrag ebenso gültig wie (A), *„und zwar, bevor
   weiterer Aufwand in Absicherung, Ausführung, Oberfläche oder Betrieb fließt."* Die
   Stufen 4 bis 10 entfallen dann.
2. **Rückbau.** §1: *„Ein System, dessen Vorteil widerlegt ist, wird nicht abgesichert.
   Es wird zurückgebaut oder aufgegeben."*
3. **Eine neue, eigenständig begründete Hypothese** unter den verbleibenden 29 Versuchen.
   Das ist nur zulässig, wenn sie eine eigene Begründungstiefe mitbringt — nicht als
   vierter Anlauf auf dieselbe Frage.

**Empfehlung: (1) beenden — mit einer geschärften Begründung.**

Nach den Konfidenzintervallen ist die Begründung nicht mehr „es verliert", sondern
schärfer und unbequemer: **auf diesem Instrument und diesem Zeitrahmen kann die Frage
nicht beantwortet werden.** Der vorregistrierte Test ist eindeutig nicht bestanden — das
ist (B) im operativen Sinn des Vertrags, weil die Vorregistrierung definiert, was
„existiert" heißt. Aber die zugrunde liegende Frage bleibt offen, und zwar aus einem
Grund, der sich durch keine weitere Hypothese beheben lässt: **der Stichprobenumfang.**

Das trifft Option (3) härter als das Ergebnis selbst. Eine neue Hypothese auf H1 über drei
Jahre erzeugt wieder 50 bis 150 Trades, und damit wieder ein Intervall, das breiter ist
als jeder Effekt, den sie zeigen könnte. Wer (3) ziehen will, muss **zuerst die
Handelsfrequenz lösen** — kürzerer Zeitrahmen, mehr Instrumente oder deutlich längere
Historie —, sonst verbraucht er Versuche für Messungen, die nichts auflösen können. Die
Mindest-Nachweisdauer von rund 79 Jahren gegen 0,9 Jahre Out-of-Sample
(`BERICHT_TEIL3.md` §5) sagt dasselbe aus einer anderen Richtung.

**Alternative: (3).** Sie ist zulässig und befristet, aber sie kostet Versuche, und jeder
verbrauchte Versuch macht die Deflation für alle späteren strenger. Wer sie zieht, sollte
die neue Zwangslage vorher benennen können — nicht die Parameter.

**Was dieser Befund ausdrücklich nicht sagt:** er gilt für ein Instrument, einen
Zeitrahmen und drei Hypothesen. Er sagt nicht, dass nirgends ein Vorteil existiert.

---

*Stand dieser Datei am 2026-08-19: 4 Einträge. **H-001 erledigt** (aufgehoben, E-006),
H-002 mit Nachtrag erledigt, **H-003 offen** — er wartet auf den Widerruf durch den
Kontoinhaber, nicht auf Arbeit —, H-004 beendet den Auftrag und liegt beim Auftraggeber.*
