# ABBRUCH.md — wann dieses Vorhaben endet

*Entwurf des ausführenden Agenten (Paket 2, A2). Die Entscheidung trifft der Auftraggeber;
die Unterschriftszeile steht am Ende. Alle Zahlen sind mit den Messungen aus Paket 2
gefüllt, nicht als Gerüst gelassen.*

**Wozu dieses Dokument.** Ein Vorhaben ohne vorab bezifferte Abbruchbedingung endet nicht,
es versickert — und zwar immer erst, nachdem es teuer geworden ist. Die Bedingungen unten
stehen **vor** den Läufen, gegen die sie messen. Wird eine erreicht, ist das das Ergebnis,
keine Diskussionsgrundlage.

**Gemeinsame Regel für alle Bedingungen:** *nicht bewertbar = nicht erfüllt.* Eine
Bedingung, deren Messung fehlt oder scheitert, gilt als **ausgelöst**, nicht als
übersprungen. Das ist die einzige Richtung, in der ein Versäumnis nicht zum Weiterlaufen
führt.

---

## Bedingung 1 — Kostentor rot

| | |
|---|---|
| **Messbare Schwelle** | Erforderliche Trefferquote p\* > 62 % bei **allen bewertbaren** Prüfinstrumenten, mindestens jedoch vier, bei **allen** erhobenen Brokern, bei S = 1,0 × Median-ATR(14) auf H1. Sind weniger als vier Instrumente bewertbar, gilt die Bedingung als **ausgelöst** (Kernregel: eine fehlende Messung ist keine bestandene) |
| **Messzeitpunkt** | Bei jeder Neuerhebung der Broker-Kosten, mindestens halbjährlich; zusätzlich sofort bei Auslösung von Bedingung 3 |
| **Wer misst** | `python tools/kostentor.py` gegen `config/broker_costs.json` und `config/atr_measurements.json` |
| **Beim Auslösen** | Ende des Vorhabens in der jetzigen Auslegung (Stundenhorizont, mehrere Trades je Tag). Keine Strategiearbeit. Die Gegenrechnung aus Tabelle 5 des Werkzeugs benennt dann den Horizont, ab dem es rechnerisch trüge — sie ist die einzige zulässige Fortsetzung |

**Stand am 2026-08-17 (bestätigt durch Ausführung, Ausgabe in
`ABSCHLUSS/07-AUSGABEN/kostentor.txt`):** nicht ausgelöst. M1 = GRÜN mit 4 grünen
Instrumenten von 6 (XAUUSD 51,0 %, DE40 51,6 %, NVDA 52,3 %, EURUSD 55,5 %), GBPJPY gelb
bei 57,8 %, BTCUSD nicht bewertbar.

**Berichtigung vom 2026-08-17 (Abschluss).** Die erste Fassung verlangte p\* > 62 % bei
**allen sechs** Instrumenten. Da BTCUSD dauerhaft „nicht bewertbar" ist (keine Kostenzeile
bei keinem der vier Broker), konnte ROT damit **nie** eintreten — eine Ampel, die nicht rot
werden kann, schützt nicht. Das widersprach der Kernregel dieses Dokuments, dass eine
fehlende Messung als ausgelöst gilt. Die Schwelle ist darauf umgestellt: alle bewertbaren,
mindestens vier. Am Stand vom 2026-08-17 ändert das nichts (fünf bewertbar, M1 grün).

**Nachtrag vom 2026-08-17 (Prüfung des eigenen Bestands).** Der Absatz darüber beschrieb
eine Umstellung, die es **im Werkzeug nicht gab**. `tools/kostentor.py` prüfte weiterhin
`len(rot) == len(UNIVERSUM)` — also alle sechs — und die Regel „weniger als vier bewertbar
= ausgelöst" hatte gar keine Umsetzung. Die dem Abschluss beiliegende Rohausgabe
widersprach diesem Dokument wörtlich. Damit war die einzige grüne Ampel des Vorhabens
nicht gemessen, sondern konstruiert: genau die Fehlerklasse, die der Absatz darüber
benennt, nur eine Ebene tiefer. Der Grund, warum das monatelang unbemerkt blieb: das
M1-Urteil entstand als Nebenwirkung einer `print`-Kaskade, und kein Test konnte den
Unterschied sehen.

Behoben. Die Ampel liegt jetzt in `tools/kostentor.py::m1_ampel` als reine Funktion, die
Datenlage wird **vor** dem günstigen Fall geprüft, und `tests/test_kostentor_ampel.py`
hält einen roten Eichfall: alle bewertbaren Instrumente über 62 %, ein Instrument nicht
bewertbar — die alte Fassung urteilte GELB, die neue ROT. Neu gemessen ändert sich am
Ergebnis nichts: fünf bewertbar, vier grün, `ic_markets_eu` trägt drei davon, **M1 bleibt
grün** (Rohausgabe `ABSCHLUSS-3a/07-AUSGABEN/kostentor.txt`). Der Vorbehalt darunter gilt
unverändert.

**Ausdrücklicher Vorbehalt, der zur Bedingung gehört.** Das grüne Urteil hat **keine
Reserve**. Unter fünf gleich vertretbaren Lesartenderselben Daten (Tabelle 2b des Werkzeugs)
fällt EURUSD in drei Fällen aus dem grünen Block; es bleiben dann exakt die geforderten drei
Instrumente. Zusätzlich gilt: bei EURUSD und GBPJPY liegt die Kostenuntergrenze der eigenen
Risikoschicht (10 × K) **über** dem gemessenen Median-ATR (11,01 gegen 10,04 bp; 18,35 gegen
11,72 bp) — ein Stop von 1,0 × ATR ist dort nach der Politik des Systems selbst nicht
handelbar. **Das grüne Urteil wird also von Gold, dem Index und der Einzelaktie getragen,
nicht von den Währungspaaren.** Wer die Auslegung auf Währungspaare stützt, hat kein grünes
Kostentor.

---

## Bedingung 2 — Kein Kandidat übersteht die Deflation

| | |
|---|---|
| **Messbare Schwelle** | Nach **60** vorregistrierten Versuchen kein Kandidat mit Deflated Sharpe ≥ 0,95 auf Out-of-Sample |
| **Messzeitpunkt** | Fortlaufend; die Auslösung wird geprüft, sobald `total_trials` im Register 60 erreicht |
| **Wer misst** | `gates/criteria.py::evaluate_criteria` gegen das Register `gates/trials.py`; die Kampagnengröße ist in `backtest/engine.py` als Untergrenze erzwungen (`n_trials = max(n_trials, expected_trials)`) |
| **Beim Auslösen** | Ende des Vorhabens. Keine 61. Runde, keine neue Merkmalsfamilie, keine „letzte Idee" |

**Warum genau 60 — gerechnet, nicht geraten.** Die Mehrfachvergleichs-Korrektur in
`criteria.py` ist eine Selektionsbias-Deflation nach Bailey/López de Prado: die Hürde
`expected_max_sharpe(N)` wächst mit der Zahl der Versuche, während die Schwelle
`min_deflated_sharpe = 0,95` fest bleibt. Gemessen mit den Funktionen des Repos
(T = 1000 Beobachtungen):

| Versuche N | Deflationshürde `sr0` | nötige Sharpe je Beobachtung | annualisiert (×√252) |
|---:|---:|---:|---:|
| 1 | 0,0000 | 0,05208 | **0,83** |
| 10 | 1,5746 | 0,10212 | 1,62 |
| 30 | 2,0734 | 0,11805 | 1,87 |
| **60** | **2,3453** | **0,12675** | **2,01** |
| 100 | 2,5306 | 0,13269 | 2,11 |
| 200 | 2,7655 | 0,14022 | 2,23 |

Bei 60 Versuchen verlangt die Deflation eine annualisierte Out-of-Sample-Sharpe von **2,01**.
Das ist die Grenze, an der weiteres Suchen aufhört zu helfen: jeder zusätzliche Versuch hebt
die Hürde schneller, als eine breitere Suche den besten Kandidaten plausibel verbessert —
von 60 auf 200 Versuche steigt die Anforderung um 0,22 Sharpe-Punkte, und eine dauerhaft
gehaltene Sharpe über 2 ist bei einem Retail-Zugang ohne benannte Vorteilsquelle nicht
belegbar. Unterhalb von 60 wäre die Zahl dagegen zu klein, um eine Merkmalsfamilie ernsthaft
abzusuchen. **Diese Zahl wird jetzt festgelegt und nicht später angehoben** — eine
nachträgliche Erhöhung wäre genau der Mehrfachvergleich, gegen den die Deflation schützt.

---

**Stand am 2026-08-17 (Abschluss): NICHT AUSGELÖST — gemessen, aber vor dem
Messzeitpunkt.** Sieben Ereignisstudien aus Paket 3a, höchster Deflated Sharpe **0,686**
auf dem Out-of-Sample-Drittel gegen die Schwelle 0,95. Der Messzeitpunkt dieser Bedingung
liegt jedoch bei **60** vorregistrierten Versuchen; das Register hält **7**. Die Bedingung
ist damit nicht ausgelöst, und es stehen **53 Versuche** offen — befristet durch Bedingung 5.
Beleg: `ABSCHLUSS-3a/05-URTEIL.md` §3 samt Berichtigung.

---

## Bedingung 3 — Realisierte Kosten weichen von der Modellannahme ab

| | |
|---|---|
| **Messbare Schwelle** | Die realisierten Round-Turn-Kosten je Trade weichen im Demobetrieb um mehr als **50 %** von der Modellannahme aus `config/broker_costs.json` ab (in Basispunkten des Nominals, Median über mindestens 30 Trades je Instrument) |
| **Messzeitpunkt** | Nach jeweils 30 abgeschlossenen Demo-Trades je Instrument, danach fortlaufend rollierend |
| **Wer misst** | Der Demobetrieb; die Ist-Kosten je Fill gegen `InstrumentCost.spread_price` + Kommission + Slippage-Annahme |
| **Beim Auslösen** | **Halt.** Keine weitere Eröffnung. Die Kostendatei wird mit den gemessenen Werten neu gefüllt und das Kostentor neu gerechnet. Fällt es dann rot: Bedingung 1 |

**Warum diese Bedingung besonders scharf ist.** Die Slippage in `config/broker_costs.json`
(0,5–2,0 bp je Round-Turn) ist der **einzige ungemessene Posten** in K und zugleich bei den
kostengünstigen Instrumenten der größte: bei XAUUSD macht sie 59 % von K aus. Sie ist
bewusst am unteren Rand gewählt, damit das Kostentor nicht durch eine großzügige Annahme
künstlich rot wird. Genau deshalb muss sie als Erstes gemessen werden — und genau deshalb
löst schon eine Abweichung von 50 % den Halt aus. **Rechnung dazu:** eine Slippage von
2,84 bp statt 0,5 bp lässt DE40 aus dem grünen Block fallen; ab dort wäre nur noch XAUUSD
grün, und M1 wäre gelb.

---

**Stand am 2026-08-17 (Abschluss): AUSGELÖST mangels Messung.** Es gab bis heute keinen
Handelsbetrieb mit Echtgeld und damit keine realisierten Kosten, gegen die sich die
Modellannahme prüfen ließe. Nach der Kernregel dieses Dokuments (eine fehlende Messung gilt
als ausgelöst, nicht als bestanden) ist die Bedingung ausgelöst.

Was seither hinzukam, ohne die Bedingung zu erfüllen: der Demo-Betrieb vom 2026-08-17 liefert
**gemessene Spreads** (EURUSD 0,09 bp gegen 0,05 bp modelliert, XAUUSD bis 1,07 bp gegen
0,18 bp — Faktor 1,7 bis 5,9). Das ist ein Hinweis auf die Richtung, aber keine Messung
realisierter **Round-Turn**-Kosten mit Slippage, und es stammt von einem Demokonto.

---

## Bedingung 4 — Halal-Vorfrage negativ

| | |
|---|---|
| **Messbare Schwelle** | Die Antwort auf `HALAL-VORFRAGE.md` fällt zu **Frage 1** (kein Eigentum am Basiswert) oder zu **Frage 2** (Margin und Hebel) negativ aus |
| **Messzeitpunkt** | Sobald die Antwort des Gelehrten vorliegt |
| **Wer misst** | Der Auftraggeber; die Entscheidung wird als `halal_scholar_review_id` hinterlegt und vom Code an jeder eröffnenden Live-Order erzwungen (`venue/mt5.py::_enforce_halal`) |
| **Beim Auslösen** | Handelsplatzwechsel auf die Alternativkonstruktion aus `HALAL-VORFRAGE.md` §3 (physischer Kassahandel ohne Hebel) **oder** Ende. **Kein Weiterbauen auf dem verworfenen Konstrukt** — insbesondere kein „swap-freies Konto" als Ausweg, denn das beantwortet nur Frage 3 |

**Stand am 2026-08-17:** nicht ausgelöst, weil noch nicht gefragt. Nach der gemeinsamen
Regel oben gilt „nicht bewertbar = nicht erfüllt": solange keine Antwort vorliegt, ist der
Live-Pfad gesperrt — technisch, nicht nur organisatorisch.

---

## Bedingung 5 — Aufwandsgrenze in Kalenderzeit

| | |
|---|---|
| **Messbare Schwelle** | **12 Monate ab 2026-08-17**, also bis **2027-08-17**, ohne ein grünes Bewertungstor (Bedingung 2 erfüllt: mindestens ein Kandidat mit Deflated Sharpe ≥ 0,95 auf Out-of-Sample, mit vollständiger Herkunft im Register) |
| **Messzeitpunkt** | 2027-08-17, und einmal zur Halbzeit am 2027-02-17 als Zwischenstand ohne Abbruchwirkung |
| **Wer misst** | Der Auftraggeber gegen `gates/trials.py::total_trials` und das letzte Kriterienurteil |
| **Beim Auslösen** | Ende des Vorhabens |

**Warum zwölf Monate.** Die Frist muss lang genug sein, dass 60 vorregistrierte Versuche mit
sauberer Validierung überhaupt durchführbar sind, und kurz genug, dass sie eine Grenze ist.
Zwölf Monate erlauben rund fünf Versuche im Monat neben einer Berufstätigkeit — genug für
eine ernsthafte Suche, zu wenig, um sich unbemerkt in eine unbefristete zu verwandeln.

---

**Stand am 2026-08-17 (Abschluss): NICHT AUSGELÖST, die Uhr läuft.** Frist bis
**2027-08-17**, Zwischenstand ohne Abbruchwirkung am **2027-02-17**. Kein grünes
Bewertungstor erreicht: bester Deflated Sharpe 0,686 gegen 0,95, Lücke **0,264**.

Zum selben Termin 2027-02-17 wird die halbjährliche Kostentor-Neuerhebung aus Bedingung 1
fällig. Beide Termine fallen zusammen; wer den einen bedient, bedient den anderen mit.

---

## Bedingung 6 — Keine benennbare Vorteilsquelle *(nachgetragen aus A5)*

| | |
|---|---|
| **Messbare Schwelle** | `ALPHA.md` beantwortet die Fragen 1 bis 3 (Quelle, Gegenpartei, Fortbestand) weiterhin mit „keine haltbare Antwort" |
| **Messzeitpunkt** | Vor jedem Beginn von Strategiearbeit, und erneut bei Auslösung von Bedingung 5 |
| **Wer misst** | Der Auftraggeber gegen `ALPHA.md` |
| **Beim Auslösen** | **Keine Strategiearbeit.** Zulässig bleibt ausschließlich die Suche nach einer benennbaren strukturellen Zwangslage samt Gegenpartei. Wird binnen der Frist aus Bedingung 5 keine gefunden, endet das Vorhaben |

**Stand am 2026-08-17, nach Paket 3a: WEITERHIN AUSGELÖST — jetzt gemessen statt
angenommen.** Fünf Zwangslagen wurden benannt und in sieben Studien gemessen. Sie
existieren; sie tragen ihre Kosten nicht. Größter Bruttoeffekt 1,36 bp (K3, GBPJPY) gegen
eine Schwelle von 5,51 bp; alle sieben Nettoeffekte negativ; höchster Deflated Sharpe
0,686 gegen die Schwelle 0,95. Bedingung 2 ist damit erstmals **gemessen** — aber
**nicht ausgelöst**: ihre eigene Fassung setzt den Messzeitpunkt bei 60 Versuchen an,
und das Register hält 7. Eine frühere Fassung dieses Absatzes behauptete die Auslösung;
das war falsch und ist in `ABSCHLUSS-3a/05-URTEIL.md` §3 berichtigt. Die Bedingung 6 ist nicht aufgehoben, sondern besser belegt: vorher fehlte die
Antwort, jetzt liegt sie vor und lautet nein. Beleg:
[`ABSCHLUSS-3a/05-URTEIL.md`](ABSCHLUSS-3a/05-URTEIL.md).

**Stand am 2026-08-17, vor Paket 3a: AUSGELÖST.** `ALPHA.md` hält fest, dass auf drei der vier Fragen
keine haltbare Antwort steht. Der Grund ist nicht Nachlässigkeit: Information und
Geschwindigkeit sind für einen Retail-Zugang strukturell verschlossen, und für Struktur
fehlt eine benannte Zwangslage. Diese Bedingung ist damit die **einzige zurzeit
ausgelöste** — und sie ist zugleich die wichtigste, weil sie vor allen anderen liegt.

---

## Was ausdrücklich **kein** Abbruchgrund ist

Damit die Liste nicht in beide Richtungen weich wird:

- Ein einzelner Verlustmonat oder eine Serie von Verlust-Trades. Dafür sind die
  Verlustgrenzen in `risk/limits.py` da, nicht dieses Dokument.
- Ein rotes Tor im Prüfstand. Das ist ein Fehler, der behoben wird.
- Ein einzelnes Instrument, das gelb oder rot wird. Bedingung 1 verlangt **alle
  bewertbaren, mindestens vier** (Fassung vom 2026-08-17).
- Aufgewendete Zeit oder bereits geschriebener Code. Versunkene Kosten zählen nicht.

---

## Wie eine Bedingung wieder aufgehoben wird

*(Nachgetragen am 2026-08-17. Bis dahin regelte dieses Dokument nur die Auslösung — wer
eine Aufhebung feststellen wollte, hatte keine Form dafür, und eine Fortsetzung wäre eine
Auslegungsfrage statt einer Messung gewesen.)*

Eine ausgelöste Bedingung erlischt **nicht von selbst** und **nicht durch Zeitablauf**. Sie
wird aufgehoben, wenn und nur wenn alle vier Punkte erfüllt sind:

1. **Dieselbe Messung**, die zur Auslösung führte, wird mit demselben Werkzeug erneut
   gefahren und liefert einen Wert unter der Schwelle. Kein Ersatzmaß, kein anderes
   Werkzeug, keine andere Bezugsgröße.
2. **Die Rohausgabe liegt bei** — im selben Muster wie `ABSCHLUSS/07-AUSGABEN/`.
3. **Ein datierter Absatz in diesem Dokument** hält Auslösung und Aufhebung
   nebeneinander fest. Der alte Stand wird **nicht** gelöscht (Kernregel 22).
4. **Der Auftraggeber zeichnet gegen.** Ohne Gegenzeichnung ist eine Aufhebung nicht
   festgestellt, sondern nur behauptet.

**Eine Schwelle wird dabei nie verschoben.** Wer die Zahl ändert, statt den Wert zu
erreichen, hebt die Bedingung nicht auf, sondern schafft sie ab — und das ist genau der
Mehrfachvergleich, gegen den dieses Dokument gebaut ist. Die einzige zulässige Änderung
einer Schwelle ist ihre **Verschärfung**.

**Bedingung 4 und 6 kennen keine Aufhebung durch Messung allein.** Bedingung 4 verlangt
eine benannte Gelehrten-Antwort, Bedingung 6 eine Zwangslage, die M6 vollständig besteht.

**Ein Neuanfang ist keine Aufhebung.** Wer nach einem Ende neu beginnt, beginnt ein neues
Vorhaben mit eigener Vorregistrierung, eigenem Versuchsregister und eigener Frist. Das ist
ausdrücklich zulässig — es ist nur nicht dieses hier.

---

## Unterschrift

Der Entwurf ist die Arbeit des ausführenden Agenten. Die Entscheidung ist die des
Auftraggebers.

Ich habe die sechs Bedingungen gelesen und nehme sie als verbindlich an. Mir ist bewusst,
dass Bedingung 6 zum Zeitpunkt der Unterschrift bereits ausgelöst ist und dass Bedingung 1
grün, aber ohne Reserve steht.

Ort, Datum: ______________________    Unterschrift: ______________________
