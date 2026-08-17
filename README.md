# MT5 Trading AI

Ein einzelnes, lokal lauffaehiges Python-Paket. Es enthaelt den herausgeloesten Kern
eines Handelssystems: die **Risiko- und Sperrschicht** (Hebelklammer, Verlustgrenzen,
Positionsgroesse, Stop-Budget), die **Freigabe- und Bewertungstore**, die
**Validierungs-Splits** fuer Zeitreihen, die vorregistrierten **Kriterien** samt
**Versuchsregister**, und die **Werkzeuge gegen Dokumentationsdrift**. Alles ist additiv
aus einem groesseren Altbestand uebernommen worden. Der Altbestand ist unter dem Git-Tag
`archive/pre-extraction` gesichert — **im Vorgaenger-Repository, nicht in diesem**.
Aus diesem Repo ist der Tag nicht nachpruefbar: `git tag -l` und
`git ls-remote --tags origin` liefern hier beide nichts (gemessen 2026-08-17,
Paket 2, A4.4). Wer die Isolation gegenpruefen will, braucht den Namen des
Vorgaenger-Repositorys; er steht bisher nirgends.

Was das Paket **nicht** ist: kein Dienst, kein Server, kein Container, kein Dashboard,
keine Datenbank.

**Abhaengigkeiten, genau gesagt:** der *Import* haengt an nichts ausser der
Python-Standardbibliothek — jedes Modul laesst sich ohne Fremdpaket laden, und die
gesamte Testsuite laeuft ohne eines. Wer das MT5-Terminal wirklich anspricht, **lesend
wie schreibend**, braucht zusaetzlich `MetaTrader5` (`pip install MetaTrader5`) und ein
laufendes, angemeldetes Terminal. Das Paket wird ausschliesslich **lazy** in
`RealMt5Terminal.initialize()` geladen; fehlt es, scheitert der Verbindungsaufbau laut,
nicht der Import. Betroffen sind `tools/mt5_smoke.py` und `tools/atr_messung.py`.

Die Sperren sind standardmaessig zu; ein Schalter kann nur lockern, nie verschaerfen, und
nur zusammen mit einer Freigabekennung. Eine nicht bewertbare Bedingung gilt als nicht
erfuellt.

Der Aufbau geschieht Paket fuer Paket und wird in `PROGRESS.md` protokolliert — jede Zahl
gemessen, jede Sperre nach dem Umzug einmal absichtlich beschaedigt, damit belegt ist, dass
sie rot wird. Was noch fehlt (Anbindung, Marktdaten, Kosten, Universum, Strategie,
Backtest-Maschine), steht in `FEHLT.md`. Was aus dem Altbestand bewusst zurueckblieb, steht
in `VERLUST.md`.

## Kennzahlen

Gemessen, nicht behauptet — gegen den Code geprueft von `tests/test_readme_numbers.py`.
Aendert sich der Code, ohne dass diese Zahlen nachgezogen werden, wird der Test rot.

<!-- KENNZAHLEN-ANFANG (geprueft von tests/test_readme_numbers.py) -->
- module_count: 39
- test_function_count: 624
- source_lines: 9984
<!-- KENNZAHLEN-ENDE -->

## Oberflaeche

Alles auf einer Seite im Browser, **nur lesend**:

```
python tools/oberflaeche.py
```

Zeigt Konto und Frische-Latch, offene Positionen mit Stop und Alter, den laufenden
Betrieb aus dem Journal (Takte, Eroeffnungen, Ablehnungen mit Grund), die Orderkette
Naht fuer Naht und die gemessenen Spreads gegen das Kostenmodell. Laedt alle 10 s neu,
laeuft nur auf 127.0.0.1, gebaut aus der Standardbibliothek.

Das Terminal wird dort mit `allow_write=False` geoeffnet — das ist kein Schalter des
Werkzeugs. Die Seite kann **nicht handeln**.

Sie hat genau **eine** Handlung: einen Knopf, der `betrieb/STOP` anlegt. Das ist ein
`Path.touch()` — kein Schreibrecht auf Orders, keine Terminalverbindung. Der Lauf sieht
die Datei im naechsten Takt, stellt glatt und beendet sich. Der Knopf verlangt POST und
ein beim Start erzeugtes Token, damit ihn keine fremde Seite im selben Browser ausloest.

Ueber die Laufliste laesst sich jeder fruehere Lauf ansehen (`?lauf=<datei>`); Konto,
Positionen und Kurse bleiben dabei live, und ein Hinweis sagt, dass man in die
Vergangenheit sieht.

Auswertung eines Laufs und aller Laeufe:

```
python tools/betrieb_auswerten.py          # ein Journal
python tools/betrieb_reihe.py              # alle Journale hintereinander
python tools/journal_sichern.py --ziel D:/sicherung/mt5
```

Beide Leser benutzen `mt5_trading_ai/betrieb/journal.py` — die eine getestete Stelle,
an der aus Journalzeilen Aussagen werden.

---

## Stand des Vorhabens (2026-08-17)

**Es gibt keine zugelassene Strategie, und es wird kein Echtgeld gehandelt.**

Sieben Ereignisstudien aus Paket 3a haben keine tragfaehige Zwangslage gefunden: groesster
Bruttoeffekt 1,36 bp gegen eine Kostenschwelle von 5,51 bp, alle sieben Nettoeffekte
negativ, hoechster Deflated Sharpe 0,686 gegen die Schwelle 0,95. Das Urteil steht in
[ABSCHLUSS-3a/05-URTEIL.md](ABSCHLUSS-3a/05-URTEIL.md), die Abbruchbedingungen in
[ABBRUCH.md](ABBRUCH.md).

**Der Live-Pfad ist nicht erreichbar**, und zwar auf drei Ebenen unabhaengig voneinander:

1. `RealMt5Terminal` faehrt mit `allow_write=False` als Vorgabe und `require_demo=True`.
   Ein Schreibzugriff auf ein Live-Konto wird abgelehnt, bevor er den Handelsplatz
   erreicht.
2. Die mehrstufige Live-Freigabe in `execution/release.py` ist an **keinen** Aufrufer
   angeschlossen. Es gibt keinen Weg, sie zu erteilen.
3. Der Orderpfad prueft als Erstes die §9.3-Zulassung. Sie ist nicht erteilt, weil kein
   Kandidat das Bewertungstor bestanden hat.

Was **laeuft**, ist ein Demo-Betrieb zur Pruefung der Maschine
([tools/live_betrieb.py](tools/live_betrieb.py)) mit einer Platzhalterstrategie. Er
beantwortet, ob die Kette sauber arbeitet — nicht, ob sie Geld verdient.

---

## Abschluss Paket 3a

Ergebnisse des Auftrags „Die Vorfrage, auf das Aufloesbare zugeschnitten". Dieses Paket
liest nur — kein Broker-Konto, kein Handelsbetrieb. Es kann das Vorhaben beenden.

- [ABSCHLUSS-3a/00-UEBERSICHT.md](ABSCHLUSS-3a/00-UEBERSICHT.md) — je Aufgabe eine Zeile: Ampel, Zahl, Bezugsgroesse
- [ABSCHLUSS-3a/01-AUFLOESUNG.md](ABSCHLUSS-3a/01-AUFLOESUNG.md) — gemessene Fensterstreuung, Aufloesungstabelle genaehert gegen gemessen
- [ABSCHLUSS-3a/02-DATENLAGE.md](ABSCHLUSS-3a/02-DATENLAGE.md) — Historientiefe, Pruefsummen, Gegenprobe, Zeitversatz
- [ABSCHLUSS-3a/03-KALENDER.md](ABSCHLUSS-3a/03-KALENDER.md) — Kandidaten, Ereigniszeitpunkte, Quellen, ausgesonderte mit Grund
- [ABSCHLUSS-3a/04-EREIGNISSTUDIE.md](ABSCHLUSS-3a/04-EREIGNISSTUDIE.md) — je Kandidat: Effekt, Netto, Bestaetigungstests, Urteil gegen M6
- [ABSCHLUSS-3a/05-URTEIL.md](ABSCHLUSS-3a/05-URTEIL.md) — Go/No-Go, Zustand aller sechs Abbruchbedingungen, Unterschrift
- [ABSCHLUSS-3a/08-SPAETER.md](ABSCHLUSS-3a/08-SPAETER.md) — bewusst zurueckgestellte Funde, je einer mit Begruendung
- [ABSCHLUSS-3a/09-EIGENE-FEHLER.md](ABSCHLUSS-3a/09-EIGENE-FEHLER.md) — was schiefging, ohne Beschoenigung

Rohe Terminalausgaben, eine Datei je Befehl:

- [ABSCHLUSS-3a/07-AUSGABEN/pytest.txt](ABSCHLUSS-3a/07-AUSGABEN/pytest.txt)
- [ABSCHLUSS-3a/07-AUSGABEN/ruff.txt](ABSCHLUSS-3a/07-AUSGABEN/ruff.txt)
- [ABSCHLUSS-3a/07-AUSGABEN/mypy.txt](ABSCHLUSS-3a/07-AUSGABEN/mypy.txt)
- [ABSCHLUSS-3a/07-AUSGABEN/gen_docs.txt](ABSCHLUSS-3a/07-AUSGABEN/gen_docs.txt)
- [ABSCHLUSS-3a/07-AUSGABEN/check_docs_claims.txt](ABSCHLUSS-3a/07-AUSGABEN/check_docs_claims.txt)
- [ABSCHLUSS-3a/07-AUSGABEN/check_doc_numbers.txt](ABSCHLUSS-3a/07-AUSGABEN/check_doc_numbers.txt)
- [ABSCHLUSS-3a/07-AUSGABEN/kostentor.txt](ABSCHLUSS-3a/07-AUSGABEN/kostentor.txt)
- [ABSCHLUSS-3a/07-AUSGABEN/ereignisstudie_selbsttest.txt](ABSCHLUSS-3a/07-AUSGABEN/ereignisstudie_selbsttest.txt)
- [ABSCHLUSS-3a/07-AUSGABEN/aufloesung.txt](ABSCHLUSS-3a/07-AUSGABEN/aufloesung.txt)
- [ABSCHLUSS-3a/07-AUSGABEN/gegenprobe.txt](ABSCHLUSS-3a/07-AUSGABEN/gegenprobe.txt)
- [ABSCHLUSS-3a/07-AUSGABEN/ereignisstudie.txt](ABSCHLUSS-3a/07-AUSGABEN/ereignisstudie.txt)
- [ABSCHLUSS-3a/07-AUSGABEN/geheimnis_scan.txt](ABSCHLUSS-3a/07-AUSGABEN/geheimnis_scan.txt)

## Abschluss Paket 2

Ergebnisse des Auftrags „Kostentor, Verdrahtung, Wahrheit". Jede Datei ist einzeln
verlinkt, damit sie von aussen abrufbar ist — Verzeichnisseiten sind es nicht.

- [ABSCHLUSS/00-UEBERSICHT.md](ABSCHLUSS/00-UEBERSICHT.md) — je Aufgabe eine Zeile: Ampel, Zahl, Bezugsgroesse
- [ABSCHLUSS/01-KOSTENTOR.md](ABSCHLUSS/01-KOSTENTOR.md) — Kostentabellen, Quellen mit Abrufdatum, Urteil gegen M1 und M2
- [ABSCHLUSS/02-VERDRAHTUNG.md](ABSCHLUSS/02-VERDRAHTUNG.md) — Eintrittspunkte gezaehlt, Quote vorher/nachher, Eichfaelle
- [ABSCHLUSS/03-DOKU-WAHRHEIT.md](ABSCHLUSS/03-DOKU-WAHRHEIT.md) — Widersprueche geschlossen, Geheimnispruefung mit Bezugsgroesse
- [ABSCHLUSS/04-ALPHA.md](ABSCHLUSS/04-ALPHA.md) — Kopie von `ALPHA.md`
- [ABSCHLUSS/05-HALAL-VORFRAGE.md](ABSCHLUSS/05-HALAL-VORFRAGE.md) — Kopie von `HALAL-VORFRAGE.md`
- [ABSCHLUSS/06-ABBRUCHKRITERIUM.md](ABSCHLUSS/06-ABBRUCHKRITERIUM.md) — Kopie von `ABBRUCH.md`
- [ABSCHLUSS/08-SPAETER.md](ABSCHLUSS/08-SPAETER.md) — bewusst zurueckgestellte Funde, je einer mit Begruendung
- [ABSCHLUSS/09-EIGENE-FEHLER.md](ABSCHLUSS/09-EIGENE-FEHLER.md) — was schiefging, ohne Beschoenigung

Rohe Terminalausgaben des Pruefstands, eine Datei je Befehl:

- [ABSCHLUSS/07-AUSGABEN/pytest.txt](ABSCHLUSS/07-AUSGABEN/pytest.txt)
- [ABSCHLUSS/07-AUSGABEN/ruff.txt](ABSCHLUSS/07-AUSGABEN/ruff.txt)
- [ABSCHLUSS/07-AUSGABEN/mypy.txt](ABSCHLUSS/07-AUSGABEN/mypy.txt)
- [ABSCHLUSS/07-AUSGABEN/gen_docs.txt](ABSCHLUSS/07-AUSGABEN/gen_docs.txt)
- [ABSCHLUSS/07-AUSGABEN/check_docs_claims.txt](ABSCHLUSS/07-AUSGABEN/check_docs_claims.txt)
- [ABSCHLUSS/07-AUSGABEN/check_doc_numbers.txt](ABSCHLUSS/07-AUSGABEN/check_doc_numbers.txt)
- [ABSCHLUSS/07-AUSGABEN/kostentor.txt](ABSCHLUSS/07-AUSGABEN/kostentor.txt)
- [ABSCHLUSS/07-AUSGABEN/atr_messung.txt](ABSCHLUSS/07-AUSGABEN/atr_messung.txt)
- [ABSCHLUSS/07-AUSGABEN/geheimnispruefung.txt](ABSCHLUSS/07-AUSGABEN/geheimnispruefung.txt)
- [ABSCHLUSS/07-AUSGABEN/eichfaelle.txt](ABSCHLUSS/07-AUSGABEN/eichfaelle.txt)

Wurzeldokumente, die in diesem Auftrag entstehen:

- [ABBRUCH.md](ABBRUCH.md) — beziffertes Abbruchkriterium fuer das Gesamtvorhaben
- [ALPHA.md](ALPHA.md) — woher der Vorteil kommen soll, auf einer Seite
- [HALAL-VORFRAGE.md](HALAL-VORFRAGE.md) — Vorlage fuer einen qualifizierten Gelehrten
