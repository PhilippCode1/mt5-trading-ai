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
- module_count: 18
- test_function_count: 193
- source_lines: 4129
<!-- KENNZAHLEN-ENDE -->
