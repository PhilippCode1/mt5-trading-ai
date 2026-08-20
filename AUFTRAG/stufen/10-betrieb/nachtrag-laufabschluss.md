# Nachtrag zu Stufe 10 — Laufabschluss: warum die Zahl bleibt, und was stattdessen gebaut wurde

*Gefahren am 2026-08-20 auf Anweisung des Auftraggebers („laufabschluss beheben"). Belege
in [`belege/`](belege/), drei neue Dateien. Bestätigt durch Ausführung.*

---

## 0. Das Ergebnis vorweg

**`laufabschluss` steht unverändert bei 90,5 %, der Alarm steht, und das bleibt so.**

Das ist kein Aufgeben. Es ist das Ergebnis der Untersuchung: die Kennzahl misst etwas,
das die Software nicht steuert, sie zeigt auf diesen Daten **in die falsche Richtung**,
und sie ließe sich in sieben Minuten schönen. Sie hochzuarbeiten wäre der Schaden
gewesen, nicht die Behebung.

Was stattdessen geschah: der Zustand, für den `laufabschluss` ein schlechter Ersatz war —
**hat ein Lauf Geld unbeaufsichtigt am Markt gelassen?** — wird jetzt wirklich gemessen.
Dabei kam der schwerste Einzelvorgang des ganzen Standes zum Vorschein, den bis heute
**keine** Kennzahl sehen konnte.

---

## 1. Was gemessen wurde

Beleg [`laufabschluss-aufschluesselung.txt`](belege/laufabschluss-aufschluesselung.txt).

Zwei der 21 Läufe haben keinen `ende`-Satz:

| Journal | Codestand | geplant | gelaufen | eröffnet | geschlossen | Buch am Ende |
|---|---|---:|---:|---:|---:|---|
| `150513` | ohne Stempel | 24 h | **0,08 h** | **3** | **0** | **3 offen** |
| `182951` | `d5c7133` | 24 h | 18,71 h | 13 | 13 | leer |

**`journal-20260817T150513` ist der schwerste Vorgang dieses Standes.** Der Lauf
eröffnete drei Positionen (EURUSD, GBPUSD, XAUUSD), schloss keine, und der Prozess starb
nach fünf Minuten. Drei Positionen standen unbeaufsichtigt am Broker: keine Stop-Pflege,
kein Abgleich, keine Höchsthaltedauer, keine Verlustgrenze.

Ein Mensch hat es **31 Sekunden später** bemerkt und von Hand neu gestartet —
`journal-20260817T151045` beginnt um 15:10:45 und schließt genau diese drei Positionen.
Um drei Uhr nachts wären daraus Stunden geworden. Dass es gutging, war Aufmerksamkeit,
keine Eigenschaft des Systems.

---

## 2. Drei Gründe, `laufabschluss` nicht hochzuarbeiten

### (a) Sie verlangt vom Prozess, seinen eigenen Tod zu überleben

Gemessen mit einem Opferskript auf dieser Maschine (Handler für SIGINT/SIGTERM/SIGBREAK,
`atexit` **und** `finally`): bei `taskkill /F` enthält die Spurdatei **nur** die
Startzeile — kein Handler, kein `finally`, kein `atexit`. Auch `taskkill` ohne `/F`
tötet den Prozess, ohne dass ein Handler läuft; nur `CTRL_BREAK_EVENT` in derselben
Konsole erreicht ihn.

Und die tatsächliche Ursache des langen Abbruchs steht im Windows-Ereignisprotokoll,
**elf Sekunden** nach dem letzten Journalsatz: Winlogon 7002 (Abmeldung), Kernel-Power
187 (`SetSuspendState`), ID 42 („Das System wird in den Standbymodus versetzt. Ursache:
Application API"). `betrieb/lauf-24h.err` ist 0 Byte — kein Traceback.

**Die Maschine ging schlafen.** Daran hat die Handelssoftware keinen Anteil. Eine
Schwelle von 95 % auf eine Größe, die der Code nicht beeinflussen kann, ist per
Konstruktion unerfüllbar.

### (b) Sie zeigt auf diesen Daten in die falsche Richtung

Die zwei Läufe **ohne** `ende` und die zwei Läufe, die **wirklich Geld am Markt ließen**,
sind disjunkte Mengen:

| Lauf | `ende`? | Buch am Ende | `laufabschluss` sagt | Wahrheit |
|---|---|---|---|---|
| `173413` | ja | **3 offen** | gelungen | gefährlich |
| `182800` | ja | **2 offen** | gelungen | gefährlich |
| `182951` | nein | leer | gescheitert | harmlos |
| `150513` | nein | **3 offen** | gescheitert | gefährlich |

Von den vier Läufen, die die Kennzahl bewertet, ordnet sie **drei** falsch ein. Die
Prüffrage aus F-016 — den schlimmsten Zustand hinschreiben und nachsehen, ob die Metrik
ihn anzeigt — fällt hier nicht nur negativ aus: sie zeigt sein **Gegenteil** an.

### (c) Sie ließe sich in sieben Minuten schönen

Jeder Lauf zählt gleich, ob er null Sekunden oder 18,7 Stunden dauerte; **20 der 21 Läufe
sind kürzer als 90 Minuten**. Aus `(19+x)/(21+x) ≥ 0,95` folgt `x = 19`: neunzehn
Trockenläufe von je zwanzig Sekunden — zusammen rund sieben Minuten Arbeit — heben die
Quote über die Schwelle und löschen den Alarm, ohne dass sich am Betrieb das Geringste
bessert.

**Ein zweiter Weg zur selben Beschönigung**, der bei der Konstruktion beinahe gewählt
worden wäre: `pruefe_alarme` vergleicht `anteil < schwelle`. `19/20 = 0,95` ist **nicht**
kleiner als 0,95. Jede Konstruktion, die genau einen Lauf aus dem Nenner nimmt — etwa
„ein noch laufender Lauf ist unbeurteilbar", was nach V3 zunächst richtig klingt —
erzeugt exakt diesen Wert und schaltet den Alarm still ab. Im Dauerbetrieb ist immer ein
Lauf in der Luft; der geschönte Fall wäre der Regelfall gewesen.

Beide Wege sind als Dauertor festgehalten
(`tests/test_laufabschluss.py::test_ROT_neunzehn_trockenlaeufe_...`), damit niemand sie
für eine Behebung hält.

---

## 3. Was geändert wurde

### (1) `ausstiegsdeckung` sieht jetzt **jeden** Lauf, gleich wie er endete

Die erste Fassung zählte nur `ende`-Sätze. Damit war ausgerechnet für die Metrik, deren
Alarmregel **„Position offen geblieben"** heißt, der Fall `150513` unsichtbar — drei
Positionen unbeaufsichtigt, aber kein `ende`-Satz, also nicht im Nenner, nicht einmal als
unbeurteilbar.

Sie fragt jetzt für jeden Lauf: stand am Ende noch etwas offen? Rangfolge der Auskunft:

1. **`ende.offen_geblieben`** — die Aussage des Laufs selbst, nach dem letzten
   Schließversuch entstanden.
2. **Der letzte `takt` mit Positionsfeld** — das zuletzt beobachtete Buch. Für einen hart
   gestorbenen Lauf die einzige Auskunft, die es gibt.
3. **Die Bilanz aus Eröffnungen und Schließungen** — *ausdrücklich schwächer und im Code
   als solche benannt:* abgeleitet statt aufgezeichnet, und eine broker-seitige
   Schließung, die der Lauf nicht mehr mitbekam, fehlt darin. Sie steht trotzdem drin,
   weil sonst genau `150513` unsichtbar bliebe.

### (2) Der Nenner: nur Läufe, die nachweislich eine Position hielten

Das ist der Riegel gegen die Beschönigung aus §2(c). Ein Lauf ohne Position kann nichts
zurücklassen — er ist weder Erfolg noch Fehlschlag und gehört nicht in die Rechnung.
Zwanzig Trockenläufe bewegen die Quote um **keinen Punkt**; ein Dauertor prüft genau das
(`test_GRUEN_dieselben_trockenlaeufe_heben_die_ausstiegsdeckung_NICHT`).

Läufe, bei denen sich weder das eine noch das andere feststellen lässt, sind
**unbeurteilbar** und stehen nicht im Nenner (V3). Auf diesem Stand sind das 10 von 21.
Sie als sauber zu zählen wäre der schmeichelnde Standardwert — sie könnten beim Start ein
fremdes Buch übernommen haben, wie `173413` beweist.

### (3) `laufabschluss` behält Schwelle und Zählung, bekommt aber ihre Grenzen

Der Docstring trägt jetzt die drei Befunde mit ihren Belegen. Die Kennzahl sagt weiterhin
etwas Wahres — Läufe sterben —, sie darf nur nicht als Sicherheitsanzeige gelesen werden.

### (4) `RUNBOOK.md` §„Läufe brechen ab"

Dort stand: *„Steht eine Stoppdatei? Dann war es ein gewollter Abbruch und zählt hier
fälschlich mit — das ist eine bekannte Ungenauigkeit der Metrik."*

**Diese Ungenauigkeit existiert nicht.** Gemessen: der Stoppdatei-Pfad bricht die
Schleife mit `break` ab, danach läuft der `finally`-Block und schreibt `ende`. **Alle
fünf** Stoppdatei-Läufe haben einen `ende`-Satz; **keiner** der beiden Abbrüche hatte
eine Stoppdatei. Der erste Schritt der Handlungsanweisung führte ins Leere — und
entschuldigte die Metrik obendrein für einen Fehler, den sie nicht hatte.

Der Abschnitt sagt jetzt zuerst, was der Alarm **nicht** bedeutet, und schickt den
Betreuer für die eilige Frage zu „Position offen geblieben".

---

## 4. Was das an den Zahlen ändert

Beleg [`dienstguete-nach-laufabschluss.txt`](belege/dienstguete-nach-laufabschluss.txt).

| Ziel | vorher | nachher | Soll |
|---|---:|---:|---:|
| Buchtreue | 98,8 % | 98,8 % | 99,0 % |
| Ausstiegsverlässlichkeit | 78,8 % | 78,8 % | 95,0 % |
| **Laufabschluss** | **90,5 %** | **90,5 %** | 95,0 % |
| **Ausstiegsdeckung** | 75,0 % (6/8) | **72,7 % (8/11)** | 100 % |

**Keine Zahl ist gestiegen. Eine ist gefallen** — weil die Metrik jetzt mehr sieht,
darunter den Fall `150513`. Der Nenner wuchs von 8 auf 11, der Anteil fiel. Genau die
Richtung, die eine ehrliche Erweiterung nimmt.

---

## 5. Wie diese Arbeit entstanden ist

Die Untersuchung lief als Fächer über vier unabhängige Blickwinkel (was kann ein
sterbender Prozess garantieren; was kann ein Leser aus dem Journal ableiten; misst die
Kennzahl das Richtige; was gibt es im Bestand schon), danach drei unabhängige Entwürfe
und eine Jury aus je zwei Gutachtern pro Entwurf, zuletzt ein Vollständigkeitskritiker.

**Drei der schärfsten Befunde stammen aus dieser Kritik**, nicht aus dem ersten Entwurf:
der Beschönigungsweg über Trockenläufe, die `19/20 = 0,95`-Falle am `<`-Vergleich, und
der Hinweis, dass die Alarmdatei über ihr Alter lügt. Alle drei habe ich am echten Code
und an den echten Journalen nachgerechnet, bevor sie hier stehen — der Entwurf mit der
höchsten Jurywertung kam nur auf 6,0 von 10, und seine 70-%-Rechnung stützte sich
teilweise auf Fehlzählungen, die ich nicht übernommen habe.

---

## 6. Abnahme

Beleg [`laufabschluss-tests.txt`](belege/laufabschluss-tests.txt) —
`tests/test_laufabschluss.py` (10 Fälle) und `tests/test_ausstiegsdeckung.py` (15 Fälle),
**25 grün**, rot und grün je Eigenschaft:

| Eigenschaft | Fall |
|---|---|
| Die Schwelle bleibt 95 % | grün |
| Die Zahl bleibt gerissen | grün — fiele sie durch eine Zählungsänderung, ist es Beschönigung |
| Beschönigungsweg | **rot**: 19 Trockenläufe heben `laufabschluss` über die Schwelle |
| Gegenprobe | **grün**: dieselben heben `ausstiegsdeckung` um keinen Punkt |
| Inversion | **rot**: `173413`/`182800` zählen als gelungen und lassen Geld liegen |
| Inversion, Gegenrichtung | **rot**: `182951` zählt als gescheitert und ist harmlos |
| Harter Abbruch mit Position | **rot**: wird jetzt gesehen (war unsichtbar) |
| Harter Abbruch, leeres Buch | grün: zählt als sauber |
| Rangfolge der Auskunft | grün: die Aussage des Laufs schlägt die Bilanz |
| Stoppdatei | grün: jeder Stoppdatei-Lauf hat ein `ende`; kein Abbruch hatte eine |
| RUNBOOK | grün: die widerlegte Behauptung steht nicht mehr drin |
| Abbruchzeitpunkt | grün: beide Abbrüche lagen weit vor der geplanten Dauer |

Elf Tore je Exit 0; pytest **1.624 grün**; Tötungsrate 1,000 (16/16); Zweigdeckung jede
Geldpfad-Datei über 80 %.

---

## 7. Was dieser Nachtrag ausdrücklich nicht behauptet

* **`laufabschluss` ist nicht behoben und wird es nicht.** Der Auftrag lautete
  „laufabschluss beheben"; die Untersuchung hat ergeben, dass die Behebung der Schaden
  gewesen wäre. Die Zahl steht bei 90,5 %, der Alarm steht.
* **Der Abbruch selbst ist nicht verhindert.** Gegen `taskkill /F` und gegen den Standby
  der Maschine gibt es keine In-Prozess-Maßnahme. Was sich geändert hat, ist die
  Sichtbarkeit der Folge, nicht die Ursache.
* **Die drei offenen Positionen von `150513` hat ein Mensch gerettet, nicht das System.**
  31 Sekunden Aufmerksamkeit. Ein Wiederanlauf, der einen verwaisten Vorlauf **selbst**
  erkennt und meldet, existiert nicht — er wäre der nächste sinnvolle Schritt und ist
  hier nicht gebaut worden.
* **Kein Alarm erreicht heute einen Menschen automatisch.** `tools/dienstguete.py` steht
  in keinem CI-Schritt, und `betrieb/ALARME.txt` trägt keinen Erhebungszeitpunkt — eine
  Monate alte Alarmdatei sieht aus wie eine frische. Beides ist als eigene Aufgabe
  festgehalten, nicht hier behoben.
* **Kein Vorteil.** Befund (B) aus Stufe 3 steht unverändert.
