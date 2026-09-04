# Haltepunkte (Programm NEUAUFBAU)

Nur Philipp entscheidet: Geld, Zugangsdaten, Broker/Anlageklasse/Instrumentenart, Recht
und Ethik, Echtgeld-Freigabe. Je Eintrag: Sachlage, Messung, Empfehlung, Alternative.
Ein Haltepunkt blockiert nur, was von ihm abhängt; an allem anderen wird weitergearbeitet.
Anhängend; ein erledigter Haltepunkt bekommt einen Nachtrag, keine Löschung.

## H-003 — Zugangsdaten im Klartext im Altbestand, Widerruf steht aus (übernommen aus dem Altstand, offen seit 2026-08-19)

**Kategorie.** Zugangsdaten.

**Sachlage.** Der Altbestand `bitget-btc-ai` liegt heute unter
`C:\Users\<konto>\OneDrive\Documents\Cursor1\mt5-trading-ai` (der Ordner wurde umbenannt; der
Eintrag des Altstands nennt noch `…\Cursor1\bitget-btc-ai`). Dort liegen — nicht
versioniert, von mir **nicht gelesen** — `.env`, `.env.local`, `.env.production`,
`.env.local.backup`, `.env.production.backup` (Verzeichnisliste vom 2026-09-03). Der
Altstand-Bericht vom 2026-08-19 nennt darin einen Börsenschlüsselsatz, ein
Zugangstoken für die Bedienoberfläche, einen Anbieterschlüssel für ein Sprachmodell und
ein Nachrichten-Token. Der Ordner wird über einen Cloud-Dienst synchronisiert.

**Messung.** `git ls-files` des Altbestands führt nur `.env.*.example`-Dateien (7); die
fünf genannten Dateien sind ungetrackt. Dazu liegt dort ein ungepushter Commit bf6bcd3
(PROGRAMM/-Kopie einer früheren Sitzung) und eine ungetrackte `HERKUNFT.md`.

**Empfehlung.** Schlüssel bei den jeweiligen Anbietern widerrufen und neu ausstellen;
danach die fünf Dateien und die Archive löschen; danach den Commit bf6bcd3 verwerfen
(`git reset --hard 5c39ebb` in jenem Repository). Reihenfolge nicht verhandelbar: Löschen
vor Widerrufen lässt die Schlüssel gültig.

**Alternative.** Nur löschen, nicht widerrufen — beseitigt die Kopie, nicht die
Gültigkeit. Nicht empfohlen.

**Was ich tue.** Nichts davon; ich lese die Dateien nicht und lösche nichts außerhalb
dieses Repositories. Das Programm hängt nicht daran.

---

## Keine Haltepunkte, aber Handlungen, die nur Philipp vornehmen kann

- **Terminal-Anmeldung für A9.** Der lesende Smoke-Test verlangt ein laufendes
  MT5-Terminal mit angemeldetem Demokonto (Übersicht §2.4). Ich starte das Terminal
  bei Bedarf, melde aber kein Konto an. Fehlt die Anmeldung, ist A9 rot und steht so in
  der Meldung.

## Hinweis (kein Haltepunkt): Platte zu 99,4 % belegt — 2026-09-04

`Get-PSDrive C`: 2,9 GB frei von 475 GB. Drei Testfaelle, die temporaere Git-Repositories anlegen, fielen
deshalb im Pre-Push-Lauf (F-008); nach dem Aufraeumen eigener Reste (3,7 GB frei) liefen sie gruen. Die
restlichen rund 470 GB sind Daten ausserhalb dieses Programms — ich raeume dort nichts. Auftrag 1 kommt
mit dem jetzigen Platz durch; die Zweigdeckung und das Mutationstor kopieren das Repository mehrfach, und
unter etwa 3 GB wird das wieder scheitern.
