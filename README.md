# MT5 Trading AI

Ein einzelnes, lokal lauffaehiges Python-Paket. Es enthaelt den herausgeloesten Kern
eines Handelssystems: die **Risiko- und Sperrschicht** (Hebelklammer, Verlustgrenzen,
Positionsgroesse, Stop-Budget), die **Freigabe- und Bewertungstore**, die
**Validierungs-Splits** fuer Zeitreihen, die vorregistrierten **Kriterien** samt
**Versuchsregister**, und die **Werkzeuge gegen Dokumentationsdrift**. Alles ist additiv
aus einem groesseren Altbestand uebernommen worden; der Altbestand liegt unveraendert unter
dem Git-Tag `archive/pre-extraction`.

Was das Paket **nicht** ist: kein Dienst, kein Server, kein Container, kein Dashboard,
keine Datenbank. Es haengt an nichts ausser der Python-Standardbibliothek. Die Sperren sind
standardmaessig zu; ein Schalter kann nur lockern, nie verschaerfen, und nur zusammen mit
einer Freigabekennung. Eine nicht bewertbare Bedingung gilt als nicht erfuellt.

Der Aufbau geschieht Paket fuer Paket und wird in `PROGRESS.md` protokolliert — jede Zahl
gemessen, jede Sperre nach dem Umzug einmal absichtlich beschaedigt, damit belegt ist, dass
sie rot wird. Was noch fehlt (Anbindung, Marktdaten, Kosten, Universum, Strategie,
Backtest-Maschine), steht in `FEHLT.md`. Was aus dem Altbestand bewusst zurueckblieb, steht
in `VERLUST.md`.

## Kennzahlen

Gemessen, nicht behauptet — gegen den Code geprueft von `tests/test_readme_numbers.py`.
Aendert sich der Code, ohne dass diese Zahlen nachgezogen werden, wird der Test rot.

<!-- KENNZAHLEN-ANFANG (geprueft von tests/test_readme_numbers.py) -->
- module_count: 32
- test_function_count: 406
- source_lines: 7429
<!-- KENNZAHLEN-ENDE -->

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
