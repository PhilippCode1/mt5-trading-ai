# Warum hier ein Abzug des Versuchsregisters liegt

`TRIALS.jsonl` steht im Wurzelverzeichnis und ist **gitignoriert** — es sind
Laufzeitdaten, kein Quellcode. Damit waere der Versuchszaehler, gegen den dieser
Auftrag deflationiert, nicht nachpruefbar: er lebte nur auf einem Rechner.

Der Stand kennt dafuer bereits ein Muster. `tools/ereignisstudie.py::verlange_register`
schreibt: ein fehlendes Register wird *„geheilt durch den versionierten Abzug
ABSCHLUSS-3a/07-AUSGABEN/trials.jsonl"*. `06-trials-abzug.jsonl` ist derselbe Gedanke
fuer diese Stufe.

**Stand zum Zeitpunkt des Abzugs:** 31 Eintraege.

* 7 aus Paket 3a (Ereignisstudien K1-K5)
* 24 aus den vier Laeufen dieser Stufe (drei Hypothesen plus die swapfreie Zerlegung) — je Lauf sechs: fuenf Walk-Forward-Fenster
  plus Out-of-Sample, alle mit Ausgang `completed`

Vom vorregistrierten Kampagnenbudget (`ABBRUCH.md` §2: 60 Versuche, befristet bis
2027-08-17) sind damit **31 verbraucht, 29 offen**.

Der Abzug ist ein Beleg, kein zweites Register. Massgeblich bleibt `TRIALS.jsonl`
(Entscheidung E-002) — wer den Zaehler nachrechnen will, vergleicht beide.
