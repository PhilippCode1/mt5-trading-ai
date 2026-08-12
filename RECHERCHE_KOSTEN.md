# RECHERCHE_KOSTEN.md — R1: Handelskosten bei EU-MT5-Brokern

*Teil 3, Paket 1, Rechercheauftrag R1. Ziel: ein realistisches Kostenmodell braucht reale
Zahlen. Ohne sie ist jeder Backtest Fiktion. Abrufdatum aller Web-Quellen: **2026-08-12**.*

**Methode.** Neun parallele Rechercheure (vier je Broker, vier je Kostendimension) plus ein
Plausibilitäts-Skeptiker mit Web-Gegenprobe. Jede Zahl trägt eine Vertrauensmarke:
`measured` (belastbare Quelle, meist Broker-eigene Preisseite), `estimate` (Vergleichsseite/
geschätzt, konservativ eher hoch) oder `literature` (Fachliteratur/Definition). Roh-Spread und
Kommission sind **strikt getrennt** ausgewiesen, nie „all-in" vermischt.

---

## 1. Die vier Broker (alle EU-reguliert, alle MT5)

| Broker | Regulierung (EU-Entität) | Ausführungsmodell | swapfrei für EU-Kunden? |
|---|---|---|---|
| **IC Markets (EU) Ltd** | CySEC 362/18 | **A-Book** (NDD/ECN, 25+ LPs; Selbstauskunft) | **Ja** — auch EU/CySEC; Admin-Gebühr nach ~5 Tagen |
| **Pepperstone EU Ltd** | CySEC 388/20 · BaFin (GmbH) | **A-Book** (NDD/STP, Smart Order Routing) | **Nein** für typische EU/EEA-Residenten (Länderliste schließt EU aus) |
| **Admirals (Admiral Markets)** | CySEC · estn. EFSA | **Hybrid** (Principal/Market-Maker, hedgt Netto) | Ja (Trade.MT5); Admin-Gebühr nach 3 Tagen |
| **Tickmill Europe Ltd** | CySEC 278/15 | **Hybrid** (Raw = A-Book/STP, Classic = B-Book) | Ja (umwandelbar); Karenz ~3 Nächte |

**Skeptiker-Urteil:** IC Markets, Pepperstone und Tickmill sind belastbar; **Admirals ist die
schwächste Quelle** (offizielle Preisseiten lieferten HTTP 403 → alle Zahlen aus Drittquellen,
konservativ am oberen Ende → systematisch nach oben verzerrt).

---

## 2. Kosten je Instrument (Roh-Spread + Kommission getrennt)

Primärwerte vom günstigsten belastbaren A-Book (IC Markets Raw / Pepperstone Razor). „Komm RT"
= Kommission je Standardlot Roundturn, USD-Konto. Quelle sofern nicht anders: Broker-eigene
EU-Preisseiten (icmarkets.eu, Pepperstone-CySEC-Kosten-Dokument), `measured`.

| Instrument | Klasse | Roh-Spread (Ø) | Komm RT | Marke |
|---|---|---|---|---|
| EURUSD | fx_major | ~0,1 pip (ab 0,0) | 7,00 USD (3,50/Seite) | measured |
| EURGBP | fx_minor | ~0,25 pip (IC) / ~0,40 pip (Pep) | 7,00 USD | measured |
| XAUUSD | gold | ~0,08–0,15 USD/Unze (8–15 Cent) → ~8–15 USD/Lot (100 oz) | 7,00 USD (Razor-Gold) | measured (Spread) / Kommission-Zuordnung teils unsicher¹ |
| US500 | index_major | ~0,4 Index-Punkte | 0 (nur-Spread) | measured |
| AAPL | equity | ~1–3 US-Cent/Aktie (Börsenspread durchgereicht) | Pepperstone 0,04 USD/Aktie RT; IC 0,1 %/Seite | measured (Pep) / estimate (IC) |

Alternative Broker-Kommissionen (FX/Metalle Roundturn): **Tickmill Raw 6,00 USD** (3/Seite,
per Web bestätigt), **Admirals Zero.MT5 ~3,60–6,00 USD** (volumengestaffelt, hier konservativ
6,00). Index- und Aktien-CFDs sind bei allen vier meist kommissionsfrei (Kosten im Spread).

¹ **Gold-Kommission unsicher:** Das Pepperstone-CySEC-Dokument (Stand Juni 2022) führte XAUUSD
noch *spread-only* (Kommission 0, im Spread). Das aktuelle „Razor-Gold"-Modell berechnet die
FX-Kommission zusätzlich bei engerem Roh-Spread. Ob die EU-Entität das spiegelt, ist **nicht
100 % verifiziert** → Gold-All-in-Kosten evtl. zu hoch angesetzt. Konservativ = sicher.

---

## 3. Spread-Ausweitung (R1.2) — alle Faktoren `estimate`

**Kein Broker veröffentlicht Stress-Spreads.** Broker publizieren nur Normal-/Durchschnitts-
werte; jede Ausweitung ist aus Edukations-/Vergleichs-/Forenquellen geschätzt, konservativ
(eher hoch). Die Kommission bleibt bei Stress konstant — es weitet sich **nur der Roh-Spread**.

| Ereignis | Ausweitungsfaktor (ggü. Normal) | Quelle (Abruf 2026-08-12) |
|---|---|---|
| News (NFP/CPI/FOMC) | ~5–10x typisch; 20–50x in den ersten Sekunden | wikifx, priceactionninja, fxnx |
| FOMC-Vorlauf (30 Min vorher) | ~1,3–1,5x | fxnx.com |
| Sessionwechsel/Rollover (16:30–17:30 ET, Peak ~16:54) | ~3–10x (Majors), Ausreißer ~16x | forexpeacearmy, tradethatswing |
| Dünne Liquidität / Feiertage | ~3–10x; Großfeiertage auf Majors ~10–20x | startrader, wikifx |

**Offen:** Belastbare Werte nur durch eigenes Messen der Tick-/Spread-Logs des Ziel-Brokers
(z. B. MT5 `SymbolInfoInteger(SPREAD)` über Zeit). Faktoren als **Band** führen, nicht als
Punktwert (Broker-Streuung enorm, z. B. EUR/NZD zeitgleich 10 vs. 70 pip).

---

## 4. Swap / Overnight-Finanzierung (R1.3)

FX-Longs typisch negativ, Shorts leicht positiv (Zinsdifferenzial + Broker-Aufschlag); Gold-
Long negativ; Freitag = **Dreifach-Swap** (Wochenende vorfinanziert). Werte floaten täglich.

| Instrument | Swap Long / Short je Lot/Nacht | Marke | Quelle |
|---|---|---|---|
| EURUSD (IC Markets) | ~−8,24 / +1,51 USD | measured | icmarkets.eu Swap-Tabelle |
| EURGBP (IC Markets) | −6,68 / +0,84 Punkte | measured | icmarkets.eu |
| XAUUSD (IC/Pep, konservativ) | ~−60 / +10…−20 USD | estimate | Broker-Live-Tabellen, geschätzt |
| US500 (IC Markets) | −1,78 / −0,09 Punkte (beidseitig negativ: Admin-Markup frisst Carry) | measured | icmarkets.eu |
| AAPL (IC Markets) | −5,93 % / +0,93 % p.a. anteilig | estimate | icmarkets.eu (Short-Vorzeichen fragwürdig²) |

**Effekt einer über Nacht gehaltenen EURUSD-Long-Position** (Notional bei 1 Lot ≈ 110 000 USD):
~−8,24 USD/Nacht ist unabhängig vom Hebel (er hängt am Notional, nicht am Eigenkapital). Bei
Hebel 5 bindet das Eigenkapital ~22 000 USD → −8,24 USD ≈ **−0,037 %/Nacht** aufs Eigenkapital;
bei Hebel 10 (~11 000 USD Eigenkapital) ≈ **−0,075 %/Nacht**. Über Nacht gehaltene Positionen
sind teuer — das Kostenmodell rechnet Finanzierung je Nacht inkl. Dreifach-Tag.

² Skeptiker: IC/AAPL Short-Finanzierung +0,93 % p.a. (Trader *erhält*) ist für einen Aktien-CFD-
Short untypisch (Short zahlt meist Leihgebühr). Als `estimate` markiert, Vorzeichen fragwürdig.

---

## 5. Slippage (R1.4)

Größenordnungen, überwiegend `literature`/`estimate` (keine öffentliche broker-eigene Slippage-
Statistik für FX/CFD). In der Losgröße 0,01–1 Lot ist Slippage praktisch größenunabhängig (weit
unter Orderbuchtiefe); nur die Kommission skaliert mit dem Lot.

| Instrument | Ruhig (Peak-Liquidität) | Bewegt / High-Impact-News |
|---|---|---|
| EURUSD | 0–0,5 pip (20–30 % positiv) | 3–10+ pip; Stop-Lücken 20–50 (bis 100+) |
| XAUUSD | <1 USD/Unze (~0,2–0,5) | 2–10 USD/Unze |
| Indizes (US30/US500/GER40) | ~0–2 Punkte | 5–30+ Punkte (FOMC-ATR 100+) |

**Offen:** Belastbare eigene Zahlen nur aus Fill-Logs des Demo-/Realkontos. Das Kostenmodell
setzt einen **konservativen, dokumentierten Slippage-Default**, der später an eigenen Fills
nachgemessen wird.

---

## 6. A-Book vs. B-Book (R1.5) — Grundlage für Tor E3

- **A-Book (STP/NDD/ECN):** Broker ist *nicht* Gegenpartei; leitet an LPs/Interbank weiter,
  verdient an Kommission + Spread. Requotes praktisch abwesend, Slippage **symmetrisch** (auch
  positiv), Latenz minimal.
- **B-Book (Market Maker/Dealing Desk):** Broker *ist* Gegenpartei; Kundenverlust = Broker-
  Umsatz. **Struktureller Interessenkonflikt** — und ESMA-Pflichtdaten zeigen **74–89 % der
  Retail-CFD-Konten verlieren** (ESMA Product Intervention 2018), das B-Book ist im Aggregat
  hochprofitabel. Für eine **erfolgreiche** Strategie ist genau das das Problem: ein profitabler
  Trader ist aus B-Book-Sicht ein Verlustbringer → Anreiz zur selektiven Schlechterstellung über
  Requotes, **asymmetrische Slippage**, `last look`/Verzögerung.

**Belegter Präzedenzfall:** FXCM behielt positive Slippage ein, reichte negative weiter (>57 000
Konten, 2008–2010) → NFA-Strafe 2,0 Mio. USD + CFTC-Vergleich 14,2 Mio. USD (Quellen:
financemagnates, bloomberg; Abruf 2026-08-12).

**Empfehlung für E3:** Echtes A-Book/ECN verlangen (Kommission + Roh-Spread, NDD, symmetrische
Slippage). B-Book für eine profitable Strategie als **disqualifizierend** behandeln. **Hybrid-
Risiko** modellieren: viele Retail-Broker routen profitable Konten intern anders — ohne Order-
Flow-Transparenz nicht messbar.

---

## 7. Halal-Prüfung (R1.6) — ein gravierender Konflikt (Kernregel 16)

**Zinsbestandteile (riba):** (1) Der **Overnight-Swap ist riba al-nasī'a** (Verzugszins aus
Zinsdifferenzial + Aufschlag). (2) **Verzinste Margin/Hebel** ist riba, wenn auf das Darlehen
Zins berechnet wird. (3) **Spread + Kommission sind KEIN Zins** — Entgelt/Marge, unproblematisch.

**Swapfreie Konten lösen das nur teilweise:** Sie streichen den Swap, ersetzen ihn aber meist
durch eine Admin-/Haltegebühr (z. B. Exness 75 USD/Lot/Nacht nach Karenz; Pepperstone-EU
50 USD/Lot je 10 Tage) oder einen verbreiterten Spread. **Neuer Konflikt:** Skaliert die Gebühr
mit Haltedauer oder Zinsdifferenzial, ist sie „riba in Verkleidung" (halal-washing); die
Karenz-Falle (frei, dann Tagesgebühr) = aufgeschobener Zins. Halal nur als **fixes, zeit-/
zinsunabhängiges** Service-Entgelt.

**Gelehrten-Sicht auf CFDs allgemein — Mehrheitskonsens: haram.** AAOIFI (Shariah Standard
Nr. 1, 2000-05-31), Islamic Fiqh Council der MWL, FCNA stufen konventionelle **gehebelte CFDs/
Forex mehrheitlich als haram** ein, aus vier Gründen: (i) **kein Eigentum/Besitz (qabd)** — der
CFD ist ein Differenzkontrakt, verletzt die bai-al-sarf-Regel; (ii) **gharar** (übermäßige
Unsicherheit durch Hebel); (iii) **maysir/qimār** (reine Preisspekulation, Glücksspielcharakter);
(iv) **riba** über Swap und verzinste Margin. Mufti Taqi Usmani: haram außer bei Spot,
ungehebelt, Zug-um-Zug. Minderheit: Spot ohne Hebel, swapfrei, mit echtem Besitz ggf. erlaubt.

**Tragfähige Alternativen** (Kernregel 16): Sharia-gescreente Aktien, Halal-/Islamic-ETFs (real
gehaltene Basiswerte, z. B. UMMA, SPUS), Sukuk (SPSK), physisches voll-allokiertes Gold.

> **Das ist kein Randdetail.** Der gesamte MT5-**CFD**-Ansatz kollidiert mit der
> Halal-Anforderung. Ich benenne den Konflikt (Regel 16) und **entscheide ihn nicht**. Für eine
> verbindliche Bewertung ist eine persönliche Fatwa eines qualifizierten Gelehrten nötig; die
> hier zitierten Blogs sind Sekundärquellen. Dies ist keine Rechts-/Finanzberatung.

---

## 8. Kalibrierung `hurdle_rate` (Vorbereitung des Baus)

Gemessene EURUSD-Roundturn-Kosten auf einem A-Book: Roh-Spread ~0,1 pip **+** Kommission
7 USD/Lot (≈ 0,7 pip-Äquivalent) = **~0,8 pip ≈ ~0,7–1,0 bp** des Notionals. Die Masterprompt-
Kalibrierung (~1 bp Roundturn) ist damit **realistisch bis leicht konservativ**.

Formel (hergeleitet): `hurdle = trades_pro_tag × handelstage × (kosten_bp / 10 000) × hebel`
(Anteil des Eigenkapitals p. a. brutto, um nach Kosten bei null zu landen). Kontrolle bei 1 bp,
5 Trades/Tag, 250 Tagen: 1250 Roundturns × 0,0001 × Hebel → **Hebel 5 = 0,625 (62,5 %)**,
**Hebel 10 = 1,25 (125 %)**. Deckt sich mit der Vorgabe. Bei breiterem Spread (Gold, Indizes,
Aktien) liegt die Hürde deutlich höher.

---

## 9. Was ins Kostenmodell fließt (Defaults, versioniert)

- Kommission je Klasse: aus der versionierten Datei (A-Book-Standard: FX/Metalle 7 USD RT,
  Indizes/Aktien 0). Fehlt eine Angabe für ein Symbol → **Fehler, nicht Null**.
- Spread: aus dem **echten** Bid/Ask zum Entscheidungszeitpunkt (nicht Durchschnitt).
- Slippage: konservativer, dokumentierter Default-Parameter (kein optimistischer Wert).
- Finanzierung: je gehaltener Nacht inkl. Dreifach-Tag.
- Spread-Ausweitung: als optionaler Stress-Multiplikator (Band aus §3), Default = 1,0.

---

## 10. Offene Punkte

1. Stress-Spreads und Slippage sind nirgends broker-veröffentlicht → am eigenen Demo-/Realkonto
   nachmessen (gehört zum Datenfundament, Paket 2).
2. Gold-Kommission (spread-only vs. Razor-Gold) und AAPL-Short-Swap-Vorzeichen am Ziel-Broker
   verifizieren.
3. Halal-Konflikt (§7) — Entscheidung Philipps + Fatwa; als **S4** in `SPAETER.md` vermerkt.
4. Broker-Wahl → **Tor E3** (unten).
