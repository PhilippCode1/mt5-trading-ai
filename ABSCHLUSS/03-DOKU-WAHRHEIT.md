# Doku-Wahrheit (A4) — was behauptet wurde und was stimmt

*In sich geschlossen. Rohausgaben:
[`check_doc_numbers.txt`](07-AUSGABEN/check_doc_numbers.txt),
[`check_docs_claims.txt`](07-AUSGABEN/check_docs_claims.txt),
[`geheimnispruefung.txt`](07-AUSGABEN/geheimnispruefung.txt).*

---

## Das Ergebnis in drei Sätzen

1. **M4 = GRÜN: null widersprüchliche Zahlen** zwischen `README.md`, `MASTERBERICHT.md`,
   `FEHLT.md` und `MODULES.md`, geprüft von `tools/check_doc_numbers.py` — von einem
   Werkzeug, nicht von einem Leser. *Bestätigt durch Ausführung.*
2. **Zwei der drei vorgegebenen Widersprüche (B2, B3) existierten nicht mehr**; sie waren
   zwischen Paket 0 und heute geschlossen worden. Das ist gemessen, nicht angenommen.
3. **Dafür lagen drei andere offen**, die der Auftrag nicht kannte: eine ganze Spalte
   driftender Zeilenzahlen, eine unbelegte Reifegrad-Zusicherung und eine nicht
   nachprüfbare Behauptung über einen Git-Tag.

---

## A4.3 — Die drei vorgegebenen Widersprüche, nachgemessen

### B2 — Fallzahl von `test_mt5_venue.py`

*Behauptet:* `FEHLT.md` §1 sage 18 Fälle, `MASTERBERICHT.md` §3.4 sage 30.

*Gemessen:* **beide sagen 52. Der tatsächliche Wert ist 52.**

```
python -m pytest tests/test_mt5_venue.py --collect-only -q  ->  52 tests collected
```

Der Widerspruch war real, ist aber in Commit `b585fed` („Fallzahl test_mt5_venue.py auf 35
aktualisiert (Zahlen-Tor)") geschlossen worden und danach mitgewachsen. Er kann nicht
zurückkehren: Regel 3 in `tools/check_doc_numbers.py` prüft jede „N Fälle"-Angabe zu einer
realen Testdatei gegen die Ist-Zahl, in **jedem** Live-Dokument.

**Urteil: kein Widerspruch. Nichts zu korrigieren, nur zu belegen.**

### B3 — „privat" und die Commit-Zahl

*Behauptet:* `MASTERBERICHT.md` §0 und §6 nennen das Repo privat; es ist öffentlich.
Zusätzlich stehe dort eine handgepflegte Commit-Zahl.

*Gemessen:*

| Suche | Ergebnis |
|---|---|
| „privat" in `MASTERBERICHT.md` | **nicht gefunden**; `MASTERBERICHT.md:20` sagt ausdrücklich „(öffentlich)" |
| Sichtbarkeitsangabe in §6 | **keine vorhanden** |
| handgepflegte Commit-Zahl | **nicht gefunden** (einziger Treffer für „commit" ist eine Funktionssignatur in `MODULES.md`) |

Auch dieser Fall kann nicht zurückkehren: Regel 4 verbietet eine harte Commit-Zahl in jedem
Live-Dokument.

**Urteil: existiert nicht mehr. Nichts zu korrigieren.**

### B4 — Abhängigkeiten

*Behauptet:* `README.md` sage, das Paket hänge an nichts außer der Standardbibliothek;
`MASTERBERICHT.md` §9 verlange `pip install MetaTrader5`.

*Gemessen:* **beides stimmt, und genau darin liegt der Fehler.**

- Der Import ist nachweislich **lazy**: `venue/mt5.py` lädt `MetaTrader5` erst in
  `RealMt5Terminal.initialize()`. Eine Gegenprobe über alle Paketmodule findet **keinen
  einzigen** Fremdimport auf Modulebene, und die gesamte Testsuite läuft ohne das Paket.
- Der Satz war trotzdem irreführend, weil er den **Laufzeitpfad** verschwieg: wer das
  Terminal anspricht — lesend wie schreibend — braucht `MetaTrader5` und ein laufendes,
  angemeldetes Terminal.

**Urteil: echter Befund, korrigiert.** Der Satz in `README.md` ist neu formuliert und
unterscheidet jetzt ausdrücklich zwischen Import (stdlib-rein) und Laufzeit (braucht
`MetaTrader5`), mit Nennung der betroffenen Werkzeuge `tools/mt5_smoke.py` und
`tools/atr_messung.py`.

---

## Die drei Widersprüche, die der Auftrag nicht kannte

### N1 — 18 von 18 Zeilenzahlen in `MASTERBERICHT.md` §3 waren falsch

**Der Befund.** §3 führte je Modul eine Spalte „Zeilen". Keine der vier bestehenden Regeln
des Zahlen-Tors erfasste sie: die Regexe suchten nach „N Module", „N Testfunktionen",
„N Zeilen Kerncode", „N Commits" und „N Fälle" — nicht nach einer Zahl in einer
Tabellenzelle. Gemessen waren **13 von 18** Werten falsch, der größte Abstand bei
`venue/mt5.py` (Bericht 818, tatsächlich über 1100). Der Bericht behauptete zugleich in §5,
jede seiner Zahlen sei gemessen.

**Behoben an der Ursache, nicht am Symptom.** Nicht die 18 Zahlen wurden korrigiert — sie
wären beim nächsten Commit wieder falsch. Stattdessen:

1. `tools/gen_docs.py` schreibt die Zeilenzahl je Modul jetzt in `MODULES.md`. Diese Datei
   wird **erzeugt**, nicht gepflegt.
2. Die Spalte „Zeilen" ist aus `MASTERBERICHT.md` §3 entfernt; alle **18 von 18**
   Tabellenzeilen sind umgebaut, mit einem Verweis auf `MODULES.md` an ihrer Stelle.
3. **Regel 5** in `tools/check_doc_numbers.py` blockt die Rückkehr: eine Tabellenzeile in
   einem Live-Dokument außer `MODULES.md`, die einen realen Modulpfad mit einer nackten Zahl
   führt, ist ein Verstoß.
4. Ein **roter Eichfall** belegt Regel 5:
   `test_das_zahlen_tor_faengt_eine_erfundene_zeilenzahl`.

### N2 — „System abnahmefertig." (WIDERRUFEN) ohne jeden Beleg

**Der Befund.** `PROGRESS.md` endete mit dem Satz **„System abnahmefertig."** — inzwischen **WIDERRUFEN**, siehe unten.
`tools/check_docs_claims.py` existiert genau dafür, Reifegrad-Zusicherungen ohne
ausführbaren Beleg zu blocken — aber das Wort „abnahmefertig" fehlte in seiner Wortliste
(beide Zitate hier: **WIDERRUFEN**). In `ABNAHME_PLAN.md` stand derselbe Satz ein zweites
Mal („System komplett abnahmefertig.") — ebenfalls **WIDERRUFEN**.

Der Satz war nicht nur unbelegt, sondern **unwahr**: zu diesem Zeitpunkt lief die
Risikoschicht nur am Live-Konto und damit an keinem erreichbaren Konto.

**Behoben, ohne Geschichte zu fälschen.** `PROGRESS.md` ist ein anhängendes Logbuch
(Kernregel 22: nie überschreiben). Löschen wäre verboten, Stehenlassen unwahr. Deshalb:

1. Das Wort steht jetzt in der Sperrliste von `check_docs_claims.py`.
2. Das Werkzeug kennt neu einen **Widerruf**: eine Zeile, die `WIDERRUFEN` trägt oder auf
   die ein Widerruf folgt, stellt keine Zusicherung mehr auf. Ohne diese Ausnahme gäbe es
   für ein Logbuch keinen Weg, eine falsche Aussage zu korrigieren.
3. Beide Fundstellen sind durchgestrichen und mit Datum und Grund widerrufen. Der alte
   Wortlaut bleibt lesbar; er behauptet nichts mehr.
4. `PROGRESS.md` hat einen neuen, angehängten Eintrag für Paket 2.

### N3 — Ein Git-Tag, der nicht nachprüfbar ist

**Der Befund** (bei der Geheimnisprüfung aufgefallen). `README.md` sagte: „der Altbestand
liegt unverändert unter dem Git-Tag `archive/pre-extraction`". Gemessen:

```
git tag -l                    ->  (leer)
git ls-remote --tags origin   ->  (leer)
```

Der Tag existiert **weder lokal noch am Remote**. `PROGRESS.md:17` führt sogar eine Abnahme
„`git ls-remote --tags` zeigt `archive/pre-extraction`" — die heute nicht mehr reproduzierbar
ist. Die plausibelste Erklärung: der Tag liegt im **Vorgänger-Repository**, aus dem der Kern
herausgelöst wurde, und dieses Repo ist nirgends benannt.

**Behoben:** `README.md` und `MASTERBERICHT.md` sagen jetzt, dass der Tag im
Vorgänger-Repository liegt und **aus diesem Repo nicht nachprüfbar** ist, mit Messdatum. Wer
die Isolation gegenprüfen will, braucht den Namen des Vorgänger-Repositorys — er steht
bisher nirgends und ist als offener Punkt in [`08-SPAETER.md`](08-SPAETER.md) vermerkt.

---

## A4.1 — Der Zahlenwächter, ausgeweitet

`tests/test_readme_numbers.py` deckte nur `README.md` ab. Er deckt jetzt **drei** Dokumente
ab: `README.md`, `MASTERBERICHT.md`, `FEHLT.md`.

Die Ausweitung ruft die Regeln von `tools/check_doc_numbers.py` **direkt auf**, statt sie
nachzubauen — eine zweite Kopie derselben Regeln wäre genau der Fehler, den beide verhindern
sollen. Je Dokument drei Prüfungen:

| Prüfung | Was sie sicherstellt |
|---|---|
| `test_bewachtes_dokument_existiert` | Laut scheitern, wenn der Wächter seinen Gegenstand nicht findet |
| `test_bewachtes_dokument_hat_keine_zahlen_drift` | Keine wiederholte Kennzahl, keine handgeführte Zeilenzahl, keine Commit-Zahl, keine falsche Fallzahl |
| `test_..._ist_nicht_von_der_pruefung_ausgenommen` | Die historische Ausnahme erfasst keines dieser drei Dokumente |

Dazu: `test_zeilenzahl_je_modul_lebt_nur_in_modules_md` und der rote Eichfall zu Regel 5.
**11 neue Fälle**, alle grün.

---

## A4.2 — Die Ausnahme des Doku-Tors: geprüft, verschärft, behalten

**Die Frage.** `tools/check_doc_numbers.py` nimmt `PROGRESS.md` und `docs/audit/` von der
Zahlenprüfung aus — ausgerechnet die Datei, in der eine Falschaussage stand.

**Die Prüfung.** Die Begründung im Docstring lautet: `PROGRESS.md` ist ein anhängendes
Logbuch, jeder Eintrag ist der Stand **zu diesem Paket** und war damals wahr; sie gegen den
heutigen Code zu „korrigieren", wäre Geschichtsfälschung.

Diese Begründung ist **tragend**, und zwar belegbar: `PROGRESS.md` endet mit
einem datierten Zeilenstand vom 2026-08-15, dessen Zahl der Testfunktionen kleiner ist als
die, die der README-Block heute führt. Das ist **kein Widerspruch, sondern ein Zeitstempel** — zwischen
beiden Ständen sind Testfunktionen hinzugekommen. Genau das schützt die Ausnahme.

**Was an der Ausnahme falsch war.** Sie wurde als Schutz für die *Datei* gelesen, obwohl sie
nur für *zeitgestempelte Messwerte* trägt. Eine **Reifegrad-Zusicherung** ist kein
Messwert: „System abnahmefertig" (**WIDERRUFEN**) trägt kein Datum und behauptet einen
Zustand.

**Eigene Entscheidung 7: die Ausnahme bleibt, mit drei Klarstellungen.**
*(Entscheidung des ausführenden Agenten.)*

1. Sie gilt nur in `check_doc_numbers.py` — also nur für Zahlen. `check_docs_claims.py` hatte
   und hat **keine** Datei-Ausnahme; die Asymmetrie ist beabsichtigt und jetzt belegt.
2. Der Wortschatz von `check_docs_claims.py` ist um die Wortfamilie „abnahmefertig /
   abnahmereif / abnahmebereit" erweitert (**WIDERRUFEN**-Zitat) — die Lücke, durch die
   N2 lief.
3. Der Widerruf-Mechanismus gibt einem Logbuch erstmals einen sauberen Weg, eine falsche
   Aussage zurückzunehmen, ohne sie zu löschen.

Die Ausnahme **entfernen** wäre falsch gewesen: dann müssten die historischen Zahlen
laufend nachgezogen werden, und das Logbuch verlöre genau die Eigenschaft, für die es
existiert.

**Eigene Entscheidung 8: die Doku-Obergrenze steigt von 12 auf 24.**
*(Entscheidung des ausführenden Agenten.)*

`check_docs_claims.py` begrenzt die Zahl der Markdown-Dateien auf 12 und war mit 12/12
ausgereizt. Der vom Auftrag vorgeschriebene Abschlussordner bringt genau 12 dazu (neun in
`ABSCHLUSS/`, drei im Wurzelverzeichnis). Die Fehlermeldung des Werkzeugs bietet selbst
beide Wege an — „eine löschen oder die Grenze bewusst anheben". Angehoben auf **24**, mit
der Begründung im Code: die Bremse soll Doku-Wildwuchs verhindern, nicht einen
vorgeschriebenen Abschlussordner. Jede **weitere** neue Datei lässt das Tor wieder rot
werden; die Bremse bleibt scharf, sie steht nur ein Stück weiter.

---

## A4.4 — Geheimnisprüfung

Werkzeug, nicht Sichtprüfung: `tools/geheimnis_scan.py` (im Repo, reproduzierbar). Zwei
Runden — `detect-secrets` mit allen 27 eingebauten Detektoren, plus eine gezielte
Regex-Runde auf genau die vier im Auftrag genannten Gattungen (Zugangsdaten,
Server-Adressen, Kontonummern, Schlüssel).

| Prüfung | Geprüfte Objekte | Funde |
|---|---:|---:|
| Arbeitsbaum, `detect-secrets`, 27 Detektoren | **130** von Git verfolgte Dateien | **5** |
| **Gesamter Verlauf**, jedes Blob-Objekt einzeln | **342** Blobs aus **50** Commits | **0** |
| Arbeitsbaum, gezielte Regex-Runde, 9 Muster | **130** Dateien | **0** |

**Alle 5 Funde sind Fehlalarme** — und zwar nachgesehen, nicht angenommen. Es sind
SHA-256-Prüfsummen von Testdaten:

| Fundstelle | Inhalt |
|---|---|
| `tests/fixtures/smoke_eurusd_d1.manifest.json:3` | `"bars_checksum": "944fd240…"` |
| `tests/fixtures/smoke_eurusd_h1.manifest.json:3` | dieselbe Prüfsumme |
| `tests/test_e2e_smoke.py:40` | `PINNED_CHECKSUM = "035616dd…"` |
| `tests/test_edge_test_cli.py:26` | `PINNED_CHECKSUM = "944fd240…"` |
| `tests/test_multi_instrument_edge.py:22` | `PINNED_CHECKSUM = "944fd240…"` |

Das sind Herkunftsmarken der Testdaten, keine Geheimnisse. **Echte Funde: 0.**

**Warum der Verlauf mitgeprüft wurde.** Ein Geheimnis, das einmal committet und später
gelöscht wurde, steht weiter im Verlauf und ist bei einem öffentlichen Repository abrufbar.
Deshalb wurde jedes Blob-Objekt aus `git rev-list --objects --all` einzeln ausgelesen und
gescannt — nicht nur der aktuelle Stand.

**Alt-Repos.** Der Auftrag verlangt, sie mitzuprüfen. Es gibt in diesem Repository **keine**:
`git tag -l` und `git ls-remote --tags origin` sind beide leer (siehe N3). Der Vorgängerbaum
liegt in einem anderen, nicht benannten Repository und war damit nicht erreichbar. Das ist
eine **Lücke der Prüfung**, keine Bestätigung — und sie steht als solche in
[`08-SPAETER.md`](08-SPAETER.md).

**Bei einem Fund wäre die Regel gewesen:** nicht stillschweigend löschen, sondern den Fund
benennen und die Rotation des betroffenen Geheimnisses als Handlungsbedarf hierher
schreiben. Es gab keinen.

**Ein Hinweis zur Sorgfalt in eigener Sache:** dieser Lauf hat gegen ein reales MT5-Demokonto
gemessen. Dessen Kontonummer, Servername und Zugangsdaten stehen an **keiner** Stelle im
Repository — weder in `config/atr_measurements.json` noch in einer Ausgabe unter
`07-AUSGABEN/`. Die Messdatei nennt nur den Handelsplatz-Namen `MetaQuotes-Demo` und das
Kennzeichen `is_demo: true`.
