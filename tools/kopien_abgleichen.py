#!/usr/bin/env python3
"""Zieht die Dokumentkopien des Abschlussordners an ihren Originalen nach.

Der Abschlussordner muss in sich geschlossen sein, darum liegen einzelne Dokumente
dort ein zweites Mal. Jede dieser Kopien traegt im Kopf die Zusicherung::

    <!-- Wortgleiche Kopie von archiv/ALPHA.md (...). -->

Diese Zusicherung war nachweislich nicht selbsttragend: ``archiv/ABSCHLUSS/04-ALPHA.md``
bezeichnete sich als wortgleich und wich um 311 Zeilen ab -- der Abschlussordner gab
zur Kernfrage des Vorhabens zwei einander widersprechende Antworten, von denen eine
sich selbst als identisch mit der anderen bezeichnete.

Dieses Werkzeug schreibt; geprueft wird in ``tools/check_doc_numbers.py``. Beide
benutzen dieselbe Zerlegung aus diesem Modul, damit die Regel nicht zweimal im Haus
steht -- genau die Fehlerklasse, gegen die dieses Repo an mehreren Stellen anlaeuft.

Aufruf::

    python tools/kopien_abgleichen.py            # schreibt
    python tools/kopien_abgleichen.py --pruefen  # meldet nur, aendert nichts
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools import doku_menge  # noqa: E402

#: Der Kopf einer Kopie: ein HTML-Kommentar, der das Original benennt. Die Gruppe
#: faengt den Dateinamen -- ohne ihn ist die Zusicherung nicht pruefbar und die Datei
#: gilt nicht als Kopie.
KOPF = re.compile(
    r"^<!--\s*Wortgleiche Kopie von\s+(?P<original>[^\s(]+\.md)\b.*?-->[^\S\r\n]*\r?\n",
    re.DOTALL,
)


#: Zeilenenden gehoeren NICHT zum Vergleich. Das ist eine bewusste Entscheidung, keine
#: Nachlaessigkeit: dieses Repo laeuft mit ``core.autocrlf=true`` und ohne
#: ``.gitattributes``, git speichert also LF und checkt unter Windows CRLF aus. Ein
#: Byte-Vergleich wuerde je nach Arbeitskopie mal anschlagen und mal nicht -- ein Tor,
#: dessen Urteil vom Rechner abhaengt, ist kein Tor. Verglichen wird darum der Inhalt,
#: den git tatsaechlich ablegt.
def _normal(text: str) -> str:
    return text.replace("\r\n", "\n")


def _lies(pfad: Path) -> str:
    """Liest ohne die stille Zeilenenden-Uebersetzung von ``read_text``.

    ``Path.read_text`` uebersetzt CRLF nach LF und ``write_text`` wieder zurueck. Wer
    beides benutzt, kann eine Zeilenenden-Abweichung weder erzeugen noch sehen -- die
    erste Fassung dieses Werkzeugs hat genau das getan.
    """
    return pfad.read_bytes().decode("utf-8")


class KopieFehler(Exception):
    """Eine Kopie-Zusicherung, die sich nicht aufloesen laesst. Nie stillschweigend."""


def zerlege(text: str) -> tuple[str, str] | None:
    """``(kopf, rumpf)`` wenn ``text`` sich als Kopie ausweist, sonst ``None``.

    Der Kopf enthaelt den Kommentar samt der ihn abschliessenden Leerzeile; der Rumpf
    ist das, was mit dem Original wortgleich sein muss.
    """
    treffer = KOPF.match(text)
    if treffer is None:
        return None
    rest = text[treffer.end() :]
    # Die Leerzeile zwischen Kommentar und Titel gehoert zum Kopf, nicht zum Rumpf.
    for ende in ("\r\n", "\n"):
        if rest.startswith(ende):
            return text[: treffer.end() + len(ende)], rest[len(ende) :]
    return text[: treffer.end()], rest


def original_von(kopie: Path, text: str) -> Path:
    """Der Pfad, auf den sich die Zusicherung beruft. Fehlt er, ist das ein Fehler."""
    zerlegt = zerlege(text)
    if zerlegt is None:
        raise KopieFehler(f"{kopie}: keine Kopie-Zusicherung im Kopf.")
    treffer = KOPF.match(text)
    assert treffer is not None  # durch zerlege() bereits sichergestellt
    name = treffer.group("original")
    pfad = REPO / name
    if not pfad.is_file():
        raise KopieFehler(
            f"{kopie}: beruft sich auf {name}, aber diese Datei gibt es nicht."
        )
    return pfad


def finde_kopien() -> list[Path]:
    """Alle Markdown-Dateien des Repos, die sich selbst als Kopie ausweisen."""
    gefunden: list[Path] = []
    for pfad in sorted(REPO.rglob("*.md")):
        # archiv/: eingefroren, per Manifest gesichert (tools/archiv_manifest.py); die
        # Kopie-Zusicherungen dort beziehen sich auf bewegte Originale (E-015).
        if any(teil in {".git", "node_modules"} for teil in pfad.parts):
            continue
        if not doku_menge.ist_lebend(pfad.relative_to(REPO).as_posix()):
            continue
        try:
            text = _lies(pfad)
        except (OSError, UnicodeDecodeError):
            continue
        if zerlege(text) is not None:
            gefunden.append(pfad)
    return gefunden


def abweichende(*, streng: bool = False) -> list[tuple[Path, Path]]:
    """Die Paare (Kopie, Original), die nicht wortgleich sind.

    ``streng=True`` vergleicht zeichengenau **einschliesslich** der Zeilenenden. Das
    benutzt nur der Schreiber, damit er keine Arbeitskopie hinterlaesst, die er selbst
    nicht mehr nachziehen wuerde. Das Tor urteilt bewusst ohne (siehe ``_normal``).
    """
    schief: list[tuple[Path, Path]] = []
    for kopie in finde_kopien():
        text = _lies(kopie)
        quelle = original_von(kopie, text)
        zerlegt = zerlege(text)
        assert zerlegt is not None
        _, rumpf = zerlegt
        original = _lies(quelle)
        gleich = rumpf == original if streng else _normal(rumpf) == _normal(original)
        if not gleich:
            schief.append((kopie, quelle))
    return schief


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--pruefen",
        action="store_true",
        help="nur melden, nichts schreiben (Rueckgabe 1 bei Abweichung)",
    )
    args = ap.parse_args()

    kopien = finde_kopien()
    if not kopien:
        print("Keine Datei weist sich als Kopie aus — nichts zu tun.")
        return 0

    schief = abweichende(streng=not args.pruefen)
    if args.pruefen:
        for kopie, quelle in schief:
            rel_k = kopie.relative_to(REPO).as_posix()
            rel_q = quelle.relative_to(REPO).as_posix()
            print(
                f"FEHLGESCHLAGEN — {rel_k} nennt sich wortgleiche Kopie von "
                f"{rel_q}, ist es aber nicht.",
                file=sys.stderr,
            )
        if schief:
            print(
                "\nNachziehen mit: python tools/kopien_abgleichen.py", file=sys.stderr
            )
            return 1
        print(f"ok — {len(kopien)} Kopie(n) wortgleich mit ihren Originalen.")
        return 0

    for kopie, quelle in schief:
        text = _lies(kopie)
        zerlegt = zerlege(text)
        assert zerlegt is not None
        kopf, _ = zerlegt
        # ``kopf`` traegt die Trennzeile zum Rumpf bereits -- hier keine zweite
        # einfuegen, sonst weicht die frisch geschriebene Kopie sofort wieder ab.
        # Der Rumpf wird byteweise uebernommen, damit das Werkzeug die Zeilenenden
        # des Originals nicht stillschweigend umschreibt.
        kopie.write_bytes(kopf.encode("utf-8") + quelle.read_bytes())
        print(
            f"nachgezogen: {kopie.relative_to(REPO).as_posix()} "
            f"<- {quelle.relative_to(REPO).as_posix()}"
        )
    if not schief:
        print(f"ok — {len(kopien)} Kopie(n) waren bereits wortgleich.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
