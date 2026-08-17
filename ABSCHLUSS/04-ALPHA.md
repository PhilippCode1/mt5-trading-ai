<!-- Wortgleiche Kopie von ALPHA.md (Paket 2, §7 des Auftrags). Gepflegt wird die
     Wurzeldatei; diese Kopie steht hier, weil der Abschlussordner in sich
     geschlossen sein muss. -->

# ALPHA.md — woher der Vorteil kommen soll

*Geschrieben vor der ersten Zeile Strategiecode (Paket 2, A5). Vier Fragen, Klartext.
Wo es keine haltbare Antwort gibt, steht das da — das ist ein Ergebnis, kein Versagen.*

---

## 1. Welche Quelle? — Information, Geschwindigkeit oder Struktur?

**Antwort: keine der drei ist heute belegbar benannt.**

Die drei Quellen und warum jede hier ausscheidet:

- **Information.** Ein Vorteil aus Information verlangt Daten, die andere nicht haben oder
  nicht so schnell verarbeiten: Orderflow, Positionierungsdaten, Fundamentaldaten vor der
  Verarbeitung durch andere, alternative Datensätze. Das Vorhaben hat **nichts davon**. Es
  liest OHLC-Kerzen von einem Retail-MT5-Terminal — dieselben Kerzen, die jeder andere
  Retail-Kunde desselben Brokers auch sieht, und eine gefilterte Fassung dessen, was die
  Interbank sieht.
- **Geschwindigkeit.** Ein Vorteil aus Geschwindigkeit verlangt Kolokation, direkte
  Marktanbindung und Latenzen im Mikrosekundenbereich. Der Pfad hier ist ein Python-Prozess
  auf einem Notebook über ein Retail-Terminal über einen Broker-Server. Die Latenz liegt
  drei bis fünf Größenordnungen daneben. Diese Tür ist nicht halb offen, sie ist zu.
- **Struktur.** Ein Vorteil aus Struktur entsteht, wenn ein anderer Marktteilnehmer aus
  nicht-ökonomischen Gründen handeln **muss** — Index-Rebalancing, Margin-Liquidationen,
  Fonds-Mittelzuflüsse, regulatorische Fristen, Hedging-Zwang von Optionsmarktmachern. Das
  ist die **einzige** der drei Quellen, die für einen Kleinanleger überhaupt erreichbar ist.
  Erreichbar heißt aber nicht: hier belegt. Das Vorhaben hat bis heute **keine benannte
  Zwangslage** und keinen Datensatz, an dem eine gemessen wäre.

**Damit ist Frage 1 offen, und zwar nicht aus Bequemlichkeit.** Der einzige gangbare Weg
ist Struktur, und er verlangt zuerst eine konkrete, benennbare Zwangslage — nicht eine
Signalidee. Solange die fehlt, ist jede Strategiearbeit Kurvenanpassung an Rauschen, egal
wie sauber die Validierungsschicht darunter ist.

---

## 2. Wer verliert? — die Gegenpartei benennen

**Antwort: bei einem CFD auf einem B-Book-Konto ist die Gegenpartei der eigene Broker.
Das ist die schlechteste denkbare Antwort auf diese Frage.**

Ein CFD wird nicht an einer Börse gehandelt. Der Broker ist Vertragspartner. Er kann die
Gegenposition intern halten (B-Book) oder extern absichern (A-Book). Bei einem B-Book gilt:

> Der Gewinn des Kunden ist der Verlust des Brokers.

Nach den ESMA-Pflichtangaben verlieren **74–89 % der Retail-CFD-Konten** Geld
(ESMA-Produktinterventionsmaßnahme 2018; Erhebung in `RECHERCHE_KOSTEN.md`). Das B-Book ist
im Aggregat hochprofitabel — genau deshalb existiert es. Ein dauerhaft **profitabler**
Kunde ist aus dieser Sicht kein Kunde, sondern ein Kostenposten. Der Anreiz zur
selektiven Schlechterstellung (Requotes, asymmetrische Slippage, `last look`) ist damit
strukturell da, nicht hypothetisch. `RECHERCHE_KOSTEN.md` führt den belegten Präzedenzfall:
FXCM behielt positive Slippage ein und reichte negative weiter — über 57.000 Konten,
2008–2010, NFA-Strafe 2,0 Mio. USD plus CFTC-Vergleich 14,2 Mio. USD.

**Die ehrliche Formulierung lautet also:** die Gegenpartei ist nicht „der Markt", sondern
ein Unternehmen, dessen Geschäftsmodell davon lebt, dass diese Strategie *nicht*
funktioniert — und das die Ausführung kontrolliert, an der sich entscheidet, ob sie
funktioniert.

Bei einem echten A-Book-Broker (Straight-Through-Processing, Verdienst nur an Kommission
und Spread) verschwindet der Interessenkonflikt. Dann ist die Gegenpartei ein
Liquiditätsgeber im Interbankenmarkt — und die Frage „warum gibt der mir Geld ab?" führt
zurück zu Frage 1, die unbeantwortet ist.

---

## 3. Warum bleibt es bestehen? — warum räumt die Gegenpartei die Lücke nicht weg?

**Antwort: es gibt keine, weil es keine benannte Lücke gibt.** Ein Vorteil ohne einen Grund
für seinen Fortbestand ist eine Rückschau, kein Vorteil.

Was sich hilfsweise sagen ließe — und warum es nicht trägt:

- *„Institutionelle können nicht klein genug handeln."* Das ist der ernsthafteste Kandidat
  und der einzige, der für einen Kleinanleger überhaupt strukturell wirkt: eine Chance über
  wenige tausend Euro ist für einen Fonds nicht darstellbar. Aber sie ist auch für dieses
  Vorhaben nicht darstellbar, denn die gemessenen Kosten fressen sie. Genau das zeigt das
  Kostentor: bei EURUSD und GBPJPY liegt die Kostenuntergrenze der eigenen Risikoschicht
  **über** dem gemessenen Median-ATR auf H1 (11,01 bp gegen 10,04 bp; 18,35 bp gegen
  11,72 bp) — ein Stundenhorizont ist dort nach der Politik des Systems selbst nicht
  handelbar. Die Nische, in der ein Kleinanleger allein wäre, ist auf dieser Zeitskala
  bereits von den Kosten besetzt.
- *„Maschinelles Lernen findet Muster, die Menschen übersehen."* Das benennt keine
  Gegenpartei und keinen Grund für Fortbestand. Es ist die Hoffnung, dass ein Suchverfahren
  etwas findet, wonach mit ungleich mehr Rechenleistung, Daten und Personal bereits gesucht
  wird. Wenn ein Muster echt und dauerhaft wäre, wäre die Frage, warum ausgerechnet dieser
  Sucher es behalten darf — und diese Frage bleibt unbeantwortet.
- *„Die eigene Disziplin ist der Vorteil."* Disziplin verhindert Verluste aus eigenen
  Fehlern. Sie erzeugt keinen positiven Erwartungswert gegen Kosten. Wer bei null Vorteil
  diszipliniert handelt, verliert langsamer, nicht weniger sicher.

---

## 4. Wie widerlegt man es? — die vorregistrierte Messung

Da auf 1 bis 3 keine haltbare Antwort steht, ist die zu widerlegende Hypothese nicht
„Strategie X funktioniert", sondern die davorliegende:

> **H0 (zu widerlegen): Es gibt in den zugänglichen Daten keine strukturelle Zwangslage,
> die nach echten Kosten einen positiven Erwartungswert trägt.**

Ein Vorhaben, das H0 nicht widerlegen kann, hat keinen Vorteil. Die Widerlegung ist
**vorregistriert**, bevor gerechnet wird — im Versuchsregister `gates/trials.py`
(anhängend, keine Löschung, Herkunft pflichtig) und gegen die vorregistrierten Kriterien
in `gates/criteria.py`:

| Feld | Wert |
|---|---|
| Kennzahl | Deflated Sharpe (`criteria.py::deflated_sharpe_ratio`) auf Out-of-Sample |
| Schwelle | `min_deflated_sharpe = 0,95`, gegen die deklarierte Kampagnengröße deflationiert |
| Versuchszahl | vorregistriert in `ABBRUCH.md` §2 — **60**; `engine.py` erzwingt sie als Untergrenze |
| Splits | Purge/Embargo pflichtig (`backtest/splits.py`), Walk-Forward bis Datenende |
| Kosten | die **gemessenen** Round-Turn-Kosten aus `config/broker_costs.json`, nicht Annahmen |
| Widerlegt, wenn | nach der vorregistrierten Versuchszahl kein Kandidat DSR > 0,95 auf OoS erreicht |

Die Messung wird **nur einmal** gegen den Out-of-Sample-Block gefahren. Ein zweiter Lauf
gegen dieselben Daten ist ein weiterer Versuch und erhöht die Deflationsschwelle — das
rechnet `criteria.py::expected_max_sharpe` automatisch mit ein.

---

## Was daraus folgt

Auf drei von vier Fragen steht keine haltbare Antwort. Nach der eigenen Regel des Auftrags
(A5) wird genau das hier festgehalten **und** als Auslösebedingung in `ABBRUCH.md`
nachgetragen (dort Bedingung 6).

Das heißt nicht, dass das Vorhaben ergebnislos ist. Es heißt, dass die Reihenfolge feststeht:
**zuerst eine benennbare Zwangslage mit einer benennbaren Gegenpartei, dann Strategiecode.**
Wer diese Reihenfolge umdreht, baut ein Suchverfahren, das in Rauschen etwas finden wird —
und die Validierungsschicht dieses Repos ist gut genug, um es ihm hinterher wieder
wegzunehmen. Das ist teuer erkaufte Ehrlichkeit; billiger ist, gar nicht erst zu suchen,
bevor Frage 1 beantwortet ist.
