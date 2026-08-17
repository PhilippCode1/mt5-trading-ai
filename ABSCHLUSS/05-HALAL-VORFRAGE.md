<!-- Wortgleiche Kopie von HALAL-VORFRAGE.md (Paket 2, §7 des Auftrags). Gepflegt wird die
     Wurzeldatei; diese Kopie steht hier, weil der Abschlussordner in sich
     geschlossen sein muss. -->

# Vorlage für eine Fatwa-Anfrage — Differenzkontrakte (CFDs) auf einem Handelskonto

*Bismillāh ar-Raḥmān ar-Raḥīm.*

**An:** einen qualifizierten Gelehrten (muftī) mit Kenntnis in `fiqh al-muʿāmalāt`
**Von:** dem Betreiber des Vorhabens
**Zweck:** Dieses Dokument beschreibt einen Sachverhalt und stellt drei getrennte Fragen.
Es ist so verfasst, dass es **unverändert** weitergegeben werden kann.

---

## 0. Vorbemerkung — was dieses Dokument nicht tut

Der Verfasser dieses Dokuments beantwortet die Fragen **nicht**. Er beschreibt den
Mechanismus so genau wie möglich, damit ein Gelehrter urteilen kann. Wo eine Beschreibung
wertend klingen könnte, ist sie durch die technische Tatsache ersetzt.

Ein Hinweis vorab, weil er erfahrungsgemäß Verwirrung stiftet:

> Das Produktetikett **„swap-frei"** (auch: „islamisches Konto") beantwortet **allein
> Frage 3** dieses Dokuments. Es sagt nichts über Frage 1 (kein Eigentum am Basiswert) und
> nichts über Frage 2 (Margin und Hebel). Ein swap-freies Konto ändert an den ersten beiden
> Mechanismen nichts.

Der Betreiber hat bisher **keinen** Handel durchgeführt. Der technische Aufbau sperrt jeden
Ausführungspfad, bis eine Antwort auf dieses Dokument vorliegt: der Code verlangt vor jeder
eröffnenden Order am Echtgeldkonto eine hinterlegte Kennung der Gelehrten-Entscheidung und
lehnt sonst ab. Die Entscheidung des Gelehrten wird also technisch erzwungen, nicht nur
dokumentiert.

---

## 1. Der Sachverhalt in einfachen Worten

Ein **Differenzkontrakt** (englisch *contract for difference*, kurz CFD) ist eine
Vereinbarung zwischen zwei Parteien — dem Kunden und einem Broker-Unternehmen — über die
**Differenz** des Preises eines Bezugsgegenstands zwischen zwei Zeitpunkten.

Beispiel mit Zahlen:

1. Der Kunde vereinbart mit dem Broker einen Kontrakt, der sich auf den Goldpreis bezieht,
   in einer Größe von 100 Unzen. Der Goldpreis steht bei 4.300 USD je Unze.
2. Der Kunde **kauft kein Gold**. Es wird kein Gold geliefert, gelagert oder übereignet.
   Es entsteht kein Anspruch auf Gold. Der Kunde hat keinerlei Eigentumsrecht an Gold.
3. Der Kunde hinterlegt eine Sicherheitsleistung (*margin*). Bei Gold verlangt die
   europäische Aufsicht von Kleinanlegern mindestens 5 % des Kontraktwerts, also
   21.500 USD von 430.000 USD.
4. Steht der Goldpreis später bei 4.320 USD, zahlt der Broker dem Kunden die Differenz:
   100 × 20 USD = 2.000 USD. Steht er bei 4.280 USD, zahlt der Kunde 2.000 USD an den
   Broker.
5. Hält der Kunde den Kontrakt über Mitternacht der Serverzeit hinaus, wird ihm ein
   **Übernachtbetrag** (*swap*) belastet oder gutgeschrieben. Er wird als Jahressatz
   berechnet und tagesweise verbucht. Bei einem der erhobenen Anbieter beträgt er für eine
   Kaufposition in Gold −0,01764 % des Kontraktwerts pro Nacht, also gerundet 6,4 % im Jahr.
   Für Bitcoin liegt derselbe Satz bei −0,05583 % pro Nacht, gerundet 20 % im Jahr.

Der Broker ist bei diesem Geschäft **Vertragspartner**, nicht Vermittler an eine Börse.
Er kann die Gegenposition intern behalten; dann ist der Gewinn des Kunden sein Verlust.

---

## 2. Die drei Fragen — getrennt zu beantworten

Die drei Punkte sind bewusst getrennt, weil sie unterschiedliche Rechtsfragen berühren und
weil eine Antwort auf einen Punkt die anderen nicht miterledigt.

### Frage 1 — Kein Eigentum am Basiswert

**Der Mechanismus.** Getauscht wird ausschließlich die Kursdifferenz. Der Bezugsgegenstand
(Gold, ein Währungspaar, ein Aktienindex, eine Aktie, Bitcoin) wird zu keinem Zeitpunkt
gehalten, geliefert oder übereignet. Es gibt keine Besitzübertragung (`qabḍ`), keinen
Lagerort, keine Lieferpflicht und keinen Anspruch auf den Gegenstand. Der Kontrakt kann
jederzeit durch eine Gegenbuchung beendet werden; abgerechnet wird stets nur in Geld.

Bei einer **Verkaufsposition** (der Kunde gewinnt bei fallendem Preis) verkauft der Kunde
etwas, das er nie besessen hat und nie besitzen wird.

**Die Frage.** Ist ein solcher reiner Differenzvertrag ohne Eigentum, Besitz und
Lieferpflicht am Bezugsgegenstand zulässig? Falls die Beurteilung von der Art des
Bezugsgegenstands abhängt (Gold und Silber als `ribawī`-Güter; Währungen als `ṣarf`;
Aktienindizes; Einzelaktien; Bitcoin): bitte die Unterscheidung ausdrücklich benennen.

*Ergänzende Angabe für den Fall, dass sie erheblich ist:* Bei Gold und bei Währungen
verlangen die klassischen Regeln zu `ṣarf` eine Abwicklung im selben Sitzungsakt. Beim
Differenzkontrakt findet **überhaupt keine** Abwicklung des Gegenstands statt, weder sofort
noch verzögert.

### Frage 2 — Margin und Hebel

**Der Mechanismus.** Der Kunde stellt eine Sicherheitsleistung und bewegt damit einen
Kontraktwert, der ein Vielfaches davon beträgt. Die aufsichtsrechtlichen Obergrenzen für
Kleinanleger in der Europäischen Union sind: 30-faches bei Haupt-Währungspaaren,
20-faches bei Nebenpaaren, Gold und Hauptindizes, 5-faches bei Einzelaktien, 2-faches bei
Kryptowährungen.

Wirtschaftlich betrachtet: der Kunde trägt Gewinn und Verlust auf den **vollen**
Kontraktwert, hinterlegt aber nur einen Bruchteil. Die Differenz stellt der Broker. Fällt
die Sicherheitsleistung unter 50 % des Ersteinschusses, schließt der Broker die Position
zwangsweise (*margin close-out*).

**Zwei Lesarten, zwischen denen zu entscheiden ist:**

- *Lesart A — Darlehen:* Der Broker stellt dem Kunden Kapital gegen Sicherheit zur
  Verfügung. Dann ist zu klären, ob eine Vergütung dafür `ribā` ist.
- *Lesart B — kein Darlehen:* Es fließt kein Kapital an den Kunden. Es wird nichts gekauft,
  wofür Geld nötig wäre. Der Hebel ist lediglich die vereinbarte Bezugsgröße des
  Differenzbetrags — der Kunde schuldet nur die Differenz, nie den Kontraktwert. Dann wäre
  kein Darlehen gegeben, sondern eine Vereinbarung über einen erhöhten Einsatz.

**Die Frage.** Welche der beiden Lesarten trifft den Sachverhalt? Falls Lesart A: ist eine
solche Konstruktion zulässig, und ändert sich etwas, wenn für die Sicherheitsleistung
**keine** Zinszahlung anfällt? Falls Lesart B: verschiebt sich die Beurteilung dadurch zur
Frage des `maysir` (Spiel um Ungewisses) oder des `gharar` (übermäßige Ungewissheit)?

### Frage 3 — Overnight-Finanzierung (Swap)

**Der Mechanismus.** Wird eine Position über den täglichen Stichzeitpunkt hinaus gehalten,
wird ein Betrag belastet oder gutgeschrieben. Er wird als **Jahressatz auf den
Kontraktwert** berechnet und tageweise verbucht — die Anbieter nennen die Formel
ausdrücklich, zum Beispiel: *Kontraktwert × Volumen × Satz ÷ 360*. An einem festgelegten
Wochentag wird der dreifache Betrag verbucht, weil das Wochenende mit abgerechnet wird.

Die Höhe folgt einem Referenzzinssatz zuzüglich eines Aufschlags des Brokers (bei den
erhobenen Anbietern typischerweise 2,5 bis 3,0 Prozentpunkte).

**Die Frage.** Ist dieser Übernachtbetrag `ribā`? Und wenn ja: ist ein sogenanntes
**swap-freies** Konto eine Lösung, wenn der Anbieter statt des Zinssatzes eine
**pauschale Verwaltungsgebühr je Lot und Nacht** erhebt, die betragsmäßig ähnlich hoch ist
und ebenfalls nur für das Halten über Nacht anfällt? Oder ist eine solche Gebühr nur eine
Umbenennung desselben Sachverhalts?

> **Ausdrücklich festgehalten:** Selbst wenn Frage 3 durch ein swap-freies Konto oder durch
> Handel ausschließlich innerhalb eines Tages entfällt, sind Frage 1 und Frage 2 dadurch
> **nicht** beantwortet.

---

## 3. Die Alternativkonstruktion — zum Vergleich mitgeliefert

Damit über beides geurteilt werden kann, hier der Gegenentwurf. Er ist technisch
umsetzbar; der Betreiber führt ihn nur an, wenn der Gelehrte ihn für zulässig hält.

**Physischer Kassahandel ohne Hebel auf tatsächlich gehaltene Werte:**

- Der Käufer erwirbt den Gegenstand **vollständig bezahlt** aus eigenem Vermögen. Es gibt
  keine Sicherheitsleistung, kein Fremdkapital, keinen Zwangsschluss.
- Der Gegenstand wird **tatsächlich gehalten**: Aktien im eigenen Depot mit
  Stimm- und Dividendenrecht; Gold als zugeordnetes physisches Metall mit Lagerung.
- Es wird **nichts leerverkauft**. Verkauft wird nur, was vorher gekauft wurde.
- Es fällt **kein** Übernachtbetrag an, weil nichts finanziert wird.
- Für Aktien käme zusätzlich ein Geschäftsfeld- und Verschuldungs-Screening in Betracht
  (Ausschluss unzulässiger Geschäftsfelder, Grenzen für zinstragende Verschuldung und
  Zinserträge), wie es etablierte Indexanbieter anwenden.

### Was von der bestehenden Arbeit erhalten bliebe

Sachlich, ohne Bewertung:

| Bestandteil | Bleibt erhalten? |
|---|---|
| `venue/protocol.py` — plattformunabhängiger Handelsplatz-Vertrag | ja, unverändert |
| `gates/` — Bewertungstor, vorregistrierte Kriterien, Versuchsregister | ja, unverändert |
| `backtest/`, `data/` — Validierungsschicht, Splits, Datenqualitätstor | ja, unverändert |
| `risk/limits.py`, `risk/sizing.py` — Verlustgrenzen, Positionsgröße | ja, unverändert |
| `execution/freshness.py`, `execution/reconcile.py` — Frische, Buchabgleich | ja, unverändert |
| `risk/leverage.py` — Hebelklammer | entfiele (ohne Hebel gegenstandslos) |
| `venue/mt5.py` — MT5-Adapter | entfiele, ersetzt durch einen Broker-Adapter für Kassahandel |
| `costs/halal.py` — swapfreie Finanzierung | entfiele (keine Finanzierung) |

Der Bruch läge also **nicht** in der Prüf- und Sicherheitsschicht, sondern im Adapter und
in der Hebelklammer. Der Kern wäre nicht verloren.

Ausdrücklich zu bedenken ist auch, dass die Alternativkonstruktion andere wirtschaftliche
Eigenschaften hat: ohne Hebel und ohne Leerverkauf sind sowohl die Ertragserwartung als auch
das Verlustrisiko deutlich kleiner, und der Zeithorizont wird länger. Das ist keine
Rechtsfrage, gehört aber zur ehrlichen Beschreibung der Alternative.

---

## 4. Was der Betreiber vom Urteil erbittet

1. Eine getrennte Antwort auf **jede** der drei Fragen.
2. Falls eine Frage bejaht werden kann: unter welchen Bedingungen.
3. Falls die Konstruktion insgesamt unzulässig ist: ob die Alternativkonstruktion aus §3
   zulässig wäre, und ob am Aktien-Screening etwas zu ergänzen ist.
4. Eine Kennung oder ein Datum, unter dem die Entscheidung dokumentiert werden kann. Der
   Code verlangt sie als Feld; ohne sie bleibt jeder Ausführungspfad gesperrt.

Der Betreiber hat die technische Vorbereitung so gebaut, dass ein negatives Urteil
**folgenlos** bleibt: es wurde noch nicht gehandelt, und die Sperren sind zu.

*Wa-Llāhu aʿlam.*
