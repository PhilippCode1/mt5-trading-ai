#!/usr/bin/env python3
"""Geheimnis-Scan (Katalog A5): Arbeitsbaum UND gesamte Git-Historie, mit Basislinie.

WARUM
-----
Ein Geheimnis, das einmal committet und spaeter geloescht wurde, steht weiter im
Verlauf und ist bei einem oeffentlichen Repo abrufbar. Darum wird jedes Blob-Objekt aus
``git rev-list --objects --all`` gescannt, nicht nur der Arbeitsbaum. Der Altstand
dieses Werkzeugs gab immer Exit 0 zurueck (Bewertung 6.3) -- ein Scan ohne
Rueckgabewert ist kein Tor. Jetzt gilt: Exit 1 bei jedem Fund, der nicht in der
Basislinie steht.

DREI RUNDEN
-----------
1. ``detect-secrets`` (Yelp, alle eingebauten Detektoren) ueber jedes Objekt aus Baum
   und Verlauf. Die Objekte werden unter ihrem Dateinamen in einen temporaeren Ordner
   gelegt, damit dateityp-abhaengige Detektoren und Filter genauso arbeiten wie beim
   Kommandozeilenaufruf.
2. Eine gezielte Regex-Runde (``MUSTER``) auf die vier Gattungen des Auftrags:
   Zugangsdaten, Server-Adressen, Kontonummern, Schluessel.
3. Kontoname: ``C:\\Users\\<name>`` (auch ``/c/Users/<name>`` und die Bindestrich-
   Schreibweise ``C--Users-<name>-...``) in verfolgten Dateien --
   gezaehlt und je Datei gelistet, nach Gruppen: lebend, ``archiv/``,
   ``PROGRAMM/eingang/``, ``PROGRAMM/masterprompts/`` (die drei letzten sind per
   Manifest eingefroren, Plan Entscheidung 7). Tor per Vorgabe ueber die LEBENDEN
   Dateien (``--kontoname-sperre lebend``); ``--kontoname-sperre alle`` nimmt die
   eingefrorenen Gruppen dazu. Abschalten gibt es nicht. Ein Platzhalter steht in
   spitzen Klammern (``C:\\Users\\<konto>``) oder ist ``...`` -- beides zaehlt nicht;
   jeder andere Name zaehlt, auch ein erfundener: das Werkzeug kann Namen nicht
   unterscheiden, und eine Ausnahmeliste waere ein Loch. Namen werden nie ausgegeben.

Objekte werden je Blob-SHA genau einmal gescannt: eine unveraenderte Datei im
Arbeitsbaum ist dasselbe Objekt wie ihr Blob im Verlauf. Eine geaenderte, noch nicht
committete Datei ist ein neues Objekt (``git hash-object``, mit den Filtern des Repos,
also plattformunabhaengig).

BASISLINIE (``.secrets.baseline``, eigenes Format, JSON)
--------------------------------------------------------
Jeder Eintrag bindet einen Fund an das Git-Objekt (Blob-SHA), die Gattung und den
Abdruck des Fundtextes (SHA-256, 16 Hex). Aendert sich die Datei, aendert sich der
Blob -- der Eintrag deckt den Fund dann nicht mehr. Jeder Eintrag traegt eine Klasse
aus ``KLASSEN`` und eine Begruendung; ohne beides ist die Basislinie ungueltig (Exit
2). Die Basislinie selbst wird nicht gescannt (sie besteht aus Abdruecken), ihre
Begruendungen laufen aber durch die Regex-Runde: ein Muster in einer Begruendung macht
die Basislinie ungueltig.

EXIT
----
0 kein neuer Fund und kein Kontoname im Tor; 1 neue Funde oder Kontonamen im Tor;
2 Werkzeugfehler (kein Git-Repo, flacher Klon, ``detect-secrets`` fehlt, Basislinie
fehlt oder ungueltig). Ausgabe utf-8, nur repo-relative Pfade, nie der Fundtext.

AUFRUF
------
::

    python tools/geheimnis_scan.py [--repo PFAD] [--basislinie PFAD]
                                   [--kontoname-sperre lebend|alle] [--alles]
    python tools/geheimnis_scan.py --basislinie-schreiben

``--basislinie-schreiben`` schreibt den aktuellen Stand: bekannte Eintraege behalten
Klasse und Begruendung, neue bekommen die Klasse ``ungeprueft`` -- und die sperrt, bis
jemand sie einordnet.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[1]
BASISLINIE = ".secrets.baseline"
FORMAT = "geheimnis_scan/1"
UNGEPRUEFT = "ungeprueft"
#: Ab so vielen Objekten laeuft detect-secrets im Prozess-Pool (Start ~20 s unter
#: Windows); darunter sequentiell im selben Prozess -- derselbe Scan je Datei.
PARALLEL_AB = 200

MUSTER: list[tuple[str, re.Pattern[bytes]]] = [
    (
        "MT5-Login (Kontonummer als login=/login:)",
        re.compile(rb"(?i)\blogin\s*[=:]\s*[\"']?\d{6,12}"),
    ),
    (
        "Kontonummer (account/konto = 6-12 Ziffern)",
        re.compile(
            rb"(?i)\b(?:account|konto)(?:_?(?:id|number|nr))?\s*[=:]\s*[\"']?\d{6,12}"
        ),
    ),
    (
        "Passwort im Klartext",
        re.compile(
            rb"(?i)\b(?:password|passwort|passwd|pwd)\s*[=:]\s*[\"'][^\"'\s]{4,}"
        ),
    ),
    (
        "API-Schluessel / Token",
        re.compile(
            rb"(?i)\b(?:api[_-]?key|apikey|secret|token|bearer)\s*[=:]\s*"
            rb"[\"'][A-Za-z0-9_\-/+]{16,}"
        ),
    ),
    (
        "Privater Schluessel (PEM)",
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    ),
    (
        "Broker-Serveradresse (MT5-Servername)",
        re.compile(
            rb"(?i)\b(?:server)\s*[=:]\s*[\"'][A-Za-z][A-Za-z0-9]*-(?:Demo|Live|Real)"
            rb"[A-Za-z0-9]*[\"']"
        ),
    ),
    ("IP-Adresse mit Port", re.compile(rb"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b")),
    ("AWS-Zugangsschluessel", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
    (
        "Slack-/GitHub-Token",
        re.compile(rb"\b(?:xox[baprs]-|ghp_|github_pat_)[A-Za-z0-9_-]{10,}"),
    ),
]

#: Windows-Kontoname in einem Pfad (``C:\Users\<name>``, ``/c/Users/<name>``) oder in
#: der Bindestrich-Schreibweise eines Pfads (``C--Users-<name>-...``, so kodieren
#: Werkzeugordner einen Pfad in einem Ordnernamen). Der Name darf nicht mit ``.``
#: beginnen -- ``...`` ist die Redaktionsmarke, kein Name -- und nicht mit ``<``.
KONTONAME = re.compile(
    rb"(?:\b[A-Za-z]:|/[A-Za-z])[\\/]+Users[\\/]+([A-Za-z0-9_\-][A-Za-z0-9_.\-]*)"
    rb"|\b[A-Za-z]--Users-([A-Za-z0-9_][A-Za-z0-9_.]*)"
)


def kontonamen(inhalt: bytes) -> list[bytes]:
    """Alle Kontonamen in ``inhalt``, in beiden Schreibweisen."""
    return [m.group(1) or m.group(2) for m in KONTONAME.finditer(inhalt)]


#: Erlaubte Klassen der Basislinie. Jede sagt, WARUM der Fund kein Geheimnis ist.
KLASSEN: dict[str, str] = {
    "pruefsumme": (
        "Hex-Pruefsumme oder Objektkennung (SHA-1/SHA-256/Blob-ID) in einem Beleg, "
        "Manifest oder Register -- Entropie ohne Zugang"
    ),
    "testdatum": (
        "Erfundene Testdaten in Tests, Werkzeugen oder Belegen (Beispiel-Login, "
        "Kontonummer, Commit-Kennung), nachgelesen: kein echtes Konto"
    ),
    "adresse-lokal": (
        "Loopback- oder Beispieladresse mit Port (127.0.0.1) in Code oder Beleg -- "
        "kein erreichbarer Dienst"
    ),
}

BASISLINIE_FELDER = (
    "objekt",
    "pfad",
    "zeile",
    "gattung",
    "abdruck",
    "klasse",
    "begruendung",
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX16 = re.compile(r"^[0-9a-f]{16}$")


class WerkzeugFehler(Exception):
    """Der Scan kann nicht urteilen -- Exit 2, benannter Grund, kein Traceback."""


@dataclass
class Objekt:
    sha: str
    inhalt: bytes
    pfad: str
    im_baum: set[str] = field(default_factory=set)
    im_verlauf: bool = False


@dataclass(frozen=True)
class Fund:
    objekt: str
    pfad: str
    zeile: int
    gattung: str
    abdruck: str

    @property
    def schluessel(self) -> tuple[str, str, str]:
        return (self.objekt, self.gattung, self.abdruck)


@dataclass(frozen=True)
class Eintrag:
    objekt: str
    pfad: str
    zeile: int
    gattung: str
    abdruck: str
    klasse: str
    begruendung: str

    @property
    def schluessel(self) -> tuple[str, str, str]:
        return (self.objekt, self.gattung, self.abdruck)

    def als_dict(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in BASISLINIE_FELDER}


def abdruck(text: bytes) -> str:
    return hashlib.sha256(text).hexdigest()[:16]


# --- Git -------------------------------------------------------------------------


def git(repo: Path, *args: str, eingabe: bytes | None = None) -> bytes:
    try:
        res = subprocess.run(
            ["git", *args], cwd=repo, input=eingabe, capture_output=True, check=False
        )
    except FileNotFoundError as e:
        raise WerkzeugFehler("git nicht gefunden") from e
    if res.returncode != 0:
        grund = res.stderr.decode("utf-8", "replace").strip().splitlines()
        raise WerkzeugFehler(
            f"git {args[0]} scheiterte (Exit {res.returncode}): "
            f"{grund[0] if grund else 'ohne Meldung'}"
        )
    return res.stdout


def _blobs_lesen(repo: Path, shas: list[str]) -> dict[str, bytes]:
    """Ein ``git cat-file --batch`` fuer alle Blobs statt zwei Aufrufe je Objekt."""
    roh = git(repo, "cat-file", "--batch", eingabe=("\n".join(shas) + "\n").encode())
    inhalte: dict[str, bytes] = {}
    pos = 0
    while pos < len(roh):
        ende = roh.index(b"\n", pos)
        kopf = roh[pos:ende].decode("ascii", "replace").split()
        pos = ende + 1
        if len(kopf) != 3:  # "<sha> missing"
            continue
        sha, _typ, laenge = kopf[0], kopf[1], int(kopf[2])
        inhalte[sha] = roh[pos : pos + laenge]
        pos += laenge + 1
    return inhalte


def objekte_sammeln(repo: Path, ausgelassen: frozenset[str]) -> dict[str, Objekt]:
    """Alle Blobs des Verlaufs plus die verfolgten Dateien des Arbeitsbaums."""
    if git(repo, "rev-parse", "--is-shallow-repository").strip() == b"true":
        raise WerkzeugFehler(
            "flacher Klon: der Verlauf ist unvollstaendig (fetch-depth: 0 setzen)"
        )
    liste = git(repo, "rev-list", "--objects", "--all").decode("utf-8", "replace")
    pfade: dict[str, str] = {}
    for zeile in liste.splitlines():
        sha, _, pfad = zeile.partition(" ")
        if sha:
            pfade[sha] = pfad
    typen = git(
        repo, "cat-file", "--batch-check", eingabe=("\n".join(pfade) + "\n").encode()
    ).decode("ascii", "replace")
    blob_shas = [
        teile[0]
        for teile in (z.split() for z in typen.splitlines())
        if len(teile) == 3 and teile[1] == "blob"
    ]
    objekte: dict[str, Objekt] = {}
    for sha, inhalt in _blobs_lesen(repo, blob_shas).items():
        pfad = pfade.get(sha, "")
        if PurePosixPath(pfad).name in ausgelassen:
            continue
        objekte[sha] = Objekt(sha, inhalt, pfad or "(ohne Pfad)", im_verlauf=True)

    verfolgt = [
        p
        for p in git(repo, "ls-files", "-z").decode("utf-8", "replace").split("\0")
        if p and (repo / p).is_file() and PurePosixPath(p).name not in ausgelassen
    ]
    if verfolgt:
        hashes = (
            git(
                repo,
                "hash-object",
                "--stdin-paths",
                eingabe=("\n".join(verfolgt) + "\n").encode("utf-8"),
            )
            .decode("ascii")
            .split()
        )
        if len(hashes) != len(verfolgt):
            raise WerkzeugFehler("git hash-object lieferte nicht je Datei einen Hash")
        for pfad, sha in zip(verfolgt, hashes, strict=True):
            if sha not in objekte:
                inhalt = (repo / pfad).read_bytes().replace(b"\r\n", b"\n")
                objekte[sha] = Objekt(sha, inhalt, pfad)
            objekte[sha].im_baum.add(pfad)
    return objekte


# --- Runden ----------------------------------------------------------------------


def runde_detect_secrets(objekte: dict[str, Objekt]) -> tuple[list[Fund], int]:
    """Alle Detektoren von detect-secrets ueber jedes Objekt; (Funde, Detektoren)."""
    try:
        from detect_secrets.core import baseline as ds_baseline
        from detect_secrets.core.secrets_collection import SecretsCollection
        from detect_secrets.settings import default_settings, get_settings
    except ImportError as e:
        raise WerkzeugFehler(
            "detect-secrets fehlt (pip install -r requirements-dev.txt)"
        ) from e
    funde: list[Fund] = []
    with tempfile.TemporaryDirectory(prefix="gs-") as tmp:
        wurzel = Path(tmp)
        for sha, obj in objekte.items():
            name = PurePosixPath(obj.pfad).name or "ohne_pfad"
            ordner = wurzel / sha[:12]
            ordner.mkdir()
            (ordner / name).write_bytes(obj.inhalt)
        kurz = {sha[:12]: sha for sha in objekte}
        with default_settings():
            detektoren = len(get_settings().plugins)
            if len(objekte) >= PARALLEL_AB:
                sammlung = ds_baseline.create(
                    str(wurzel), should_scan_all_files=True, root=str(wurzel)
                )
            else:
                # Derselbe Scan je Datei, nur ohne Prozess-Pool: der Pool kostet
                # unter Windows rund 20 s Start, ein kleines Repo braucht ihn nicht.
                sammlung = SecretsCollection(root=str(wurzel))
                for datei in sorted(wurzel.rglob("*")):
                    if datei.is_file():
                        sammlung.scan_file(datei.relative_to(wurzel).as_posix())
        for dateiname, geheimnis in sammlung:
            kurz_sha = dateiname.replace("\\", "/").split("/", 1)[0]
            sha = kurz[kurz_sha]
            wert = str(geheimnis.secret_value or "")
            funde.append(
                Fund(
                    sha,
                    objekte[sha].pfad,
                    int(geheimnis.line_number),
                    f"detect-secrets: {geheimnis.type}",
                    abdruck(wert.encode("utf-8")),
                )
            )
    return funde, detektoren


def runde_muster(objekte: dict[str, Objekt]) -> list[Fund]:
    funde: list[Fund] = []
    for sha, obj in objekte.items():
        for titel, muster in MUSTER:
            for treffer in muster.finditer(obj.inhalt):
                zeile = obj.inhalt.count(b"\n", 0, treffer.start()) + 1
                funde.append(
                    Fund(
                        sha,
                        obj.pfad,
                        zeile,
                        f"Muster: {titel}",
                        abdruck(treffer.group(0)),
                    )
                )
    return funde


#: Per Manifest eingefrorene Gruppen; jede andere verfolgte Datei ist "lebend".
EINGEFROREN = ("archiv/", "PROGRAMM/eingang/", "PROGRAMM/masterprompts/")
LEBEND = "lebend"
#: Geltungsbereiche des Kontonamen-Tors. Kein "aus": die Zaehlung ist immer ein Tor.
SPERREN = ("lebend", "alle")


def gruppe(pfad: str) -> str:
    for praefix in EINGEFROREN:
        if pfad.startswith(praefix):
            return praefix
    return LEBEND


@dataclass
class Kontonamen:
    je_datei: dict[str, int]
    je_name: list[int]  # Trefferzahl je Name, absteigend -- ohne die Namen

    @property
    def treffer(self) -> int:
        return sum(self.je_datei.values())

    @property
    def je_gruppe(self) -> dict[str, int]:
        aus = {LEBEND: 0, **dict.fromkeys(EINGEFROREN, 0)}
        for pfad, n in self.je_datei.items():
            aus[gruppe(pfad)] += n
        return aus

    def im_tor(self, sperre: str) -> int:
        """Treffer im Geltungsbereich des Tors: ``lebend`` oder ``alle``."""
        if sperre not in SPERREN:
            raise WerkzeugFehler(
                f"--kontoname-sperre {sperre!r}: erlaubt sind {', '.join(SPERREN)}"
            )
        return self.treffer if sperre == "alle" else self.je_gruppe[LEBEND]


def runde_kontoname(objekte: dict[str, Objekt]) -> Kontonamen:
    je_datei: dict[str, int] = {}
    je_name: dict[bytes, int] = {}
    for obj in objekte.values():
        if not obj.im_baum:
            continue
        namen = kontonamen(obj.inhalt)
        if not namen:
            continue
        for pfad in obj.im_baum:
            je_datei[pfad] = len(namen)
        for name in namen:
            je_name[name] = je_name.get(name, 0) + len(obj.im_baum)
    return Kontonamen(je_datei, sorted(je_name.values(), reverse=True))


# --- Basislinie ------------------------------------------------------------------


def basislinie_laden(pfad: Path) -> dict[tuple[str, str, str], Eintrag]:
    name = pfad.name
    if not pfad.is_file():
        raise WerkzeugFehler(
            f"Basislinie fehlt: {name} (leer anlegen mit --basislinie-schreiben)"
        )
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise WerkzeugFehler(f"Basislinie {name} ist kein JSON: {e}") from e
    if not isinstance(daten, dict) or daten.get("format") != FORMAT:
        raise WerkzeugFehler(f"Basislinie {name}: Feld 'format' muss {FORMAT!r} sein")
    roh = daten.get("eintraege")
    if not isinstance(roh, list):
        raise WerkzeugFehler(f"Basislinie {name}: Feld 'eintraege' fehlt")
    eintraege: dict[tuple[str, str, str], Eintrag] = {}
    ungeprueft = 0
    for nr, roh_eintrag in enumerate(roh, start=1):
        if not isinstance(roh_eintrag, dict) or tuple(roh_eintrag) != BASISLINIE_FELDER:
            raise WerkzeugFehler(
                f"Basislinie {name}, Eintrag {nr}: genau die Felder "
                f"{', '.join(BASISLINIE_FELDER)} in dieser Reihenfolge"
            )
        try:
            eintrag = Eintrag(
                objekt=str(roh_eintrag["objekt"]),
                pfad=str(roh_eintrag["pfad"]),
                zeile=int(roh_eintrag["zeile"]),
                gattung=str(roh_eintrag["gattung"]),
                abdruck=str(roh_eintrag["abdruck"]),
                klasse=str(roh_eintrag["klasse"]),
                begruendung=str(roh_eintrag["begruendung"]),
            )
        except (TypeError, ValueError) as ex:
            raise WerkzeugFehler(
                f"Basislinie {name}, Eintrag {nr}: Feldtyp ({ex})"
            ) from ex
        if not HEX40.match(eintrag.objekt) or not HEX16.match(eintrag.abdruck):
            raise WerkzeugFehler(
                f"Basislinie {name}, Eintrag {nr}: objekt (40 Hex) oder abdruck "
                "(16 Hex) ungueltig"
            )
        if eintrag.klasse == UNGEPRUEFT:
            ungeprueft += 1
        elif eintrag.klasse not in KLASSEN:
            raise WerkzeugFehler(
                f"Basislinie {name}, Eintrag {nr}: Klasse {eintrag.klasse!r} "
                f"unbekannt (erlaubt: {', '.join(KLASSEN)})"
            )
        if not eintrag.begruendung.strip() or len(eintrag.begruendung) > 400:
            raise WerkzeugFehler(
                f"Basislinie {name}, Eintrag {nr}: Begruendung fehlt oder > 400 Zeichen"
            )
        for titel, muster in MUSTER:
            if muster.search(eintrag.begruendung.encode("utf-8")):
                raise WerkzeugFehler(
                    f"Basislinie {name}, Eintrag {nr}: die Begruendung enthaelt "
                    f"selbst ein Muster ({titel})"
                )
        if eintrag.schluessel in eintraege:
            raise WerkzeugFehler(f"Basislinie {name}, Eintrag {nr}: doppelt")
        eintraege[eintrag.schluessel] = eintrag
    if ungeprueft:
        raise WerkzeugFehler(
            f"Basislinie {name}: {ungeprueft} von {len(eintraege)} Eintraegen tragen "
            f"die Klasse {UNGEPRUEFT!r} -- einordnen, dann gilt die Basislinie"
        )
    return eintraege


def basislinie_schreiben(
    pfad: Path, funde: list[Fund], alt: dict[tuple[str, str, str], Eintrag]
) -> tuple[int, int]:
    """Aktuellen Stand schreiben; (uebernommen, neu als ungeprueft)."""
    eintraege: dict[tuple[str, str, str], Eintrag] = {}
    uebernommen = neu = 0
    for f in sorted(funde, key=lambda f: (f.pfad, f.zeile, f.gattung, f.objekt)):
        if f.schluessel in eintraege:
            continue
        bekannt = alt.get(f.schluessel)
        if bekannt is not None:
            klasse, begruendung = bekannt.klasse, bekannt.begruendung
            uebernommen += 1
        else:
            klasse, begruendung = UNGEPRUEFT, "noch nicht eingeordnet"
            neu += 1
        eintraege[f.schluessel] = Eintrag(
            f.objekt, f.pfad, f.zeile, f.gattung, f.abdruck, klasse, begruendung
        )
    basislinie_speichern(pfad, list(eintraege.values()))
    return uebernommen, neu


def basislinie_speichern(pfad: Path, eintraege: list[Eintrag]) -> None:
    """Ein Eintrag je Zeile, sortiert -- lesbar im Diff, gueltiges JSON."""
    eintraege = sorted(eintraege, key=lambda e: (e.pfad, e.zeile, e.gattung, e.objekt))
    kopf = {
        "format": FORMAT,
        "hinweis": (
            "Basislinie von tools/geheimnis_scan.py. Ein Eintrag gilt nur fuer genau "
            "dieses Git-Objekt (Blob-SHA): aendert sich die Datei, faellt der Fund "
            "nicht mehr darunter. abdruck = SHA-256 des Fundtextes, 16 Hex. Jeder "
            "Eintrag braucht eine Klasse aus 'klassen' und eine Begruendung."
        ),
        "klassen": KLASSEN,
    }
    zeilen = [json.dumps(e.als_dict(), ensure_ascii=False) for e in eintraege]
    text = json.dumps(kopf, ensure_ascii=False, indent=2)[:-2]
    text += ',\n  "eintraege": [\n    ' + ",\n    ".join(zeilen) + "\n  ]\n}\n"
    pfad.write_text(text, encoding="utf-8", newline="\n")


# --- Lauf ------------------------------------------------------------------------


def _quelle(obj: Objekt) -> str:
    if obj.im_baum and obj.im_verlauf:
        return "Baum+Verlauf"
    return "Baum" if obj.im_baum else "Verlauf"


def _fundzeile(f: Fund, obj: Objekt) -> str:
    pfad = sorted(obj.im_baum)[0] if obj.im_baum else obj.pfad
    return (
        f"{_quelle(obj):12s} {pfad}:{f.zeile}  {f.gattung}  "
        f"abdruck {f.abdruck}  objekt {f.objekt[:12]}"
    )


def lauf(
    repo: Path,
    basislinie: Path,
    *,
    schreiben: bool = False,
    kontoname_sperre: str = LEBEND,
    alles: bool = False,
) -> int:
    t0 = time.perf_counter()
    if not (repo / ".git").exists():
        raise WerkzeugFehler("kein Git-Repository (kein .git im Repo-Pfad)")
    # Die Basislinie wird vor dem Scan gelesen: eine ungueltige sperrt sofort,
    # nicht erst nach 90 s Scan.
    bekannt = {} if schreiben else basislinie_laden(basislinie)
    kopf = git(repo, "rev-parse", "--short", "HEAD").decode().strip()
    commits = git(repo, "rev-list", "--count", "--all").decode().strip()
    objekte = objekte_sammeln(repo, frozenset({basislinie.name}))
    t_git = time.perf_counter() - t0
    im_baum = sum(1 for o in objekte.values() if o.im_baum)
    im_verlauf = sum(1 for o in objekte.values() if o.im_verlauf)
    dateien = sum(len(o.im_baum) for o in objekte.values())
    print("=" * 88)
    print("GEHEIMNIS-SCAN (Abnahmekatalog A5) -- Arbeitsbaum und gesamter Verlauf")
    print("=" * 88)
    print(
        f"HEAD {kopf}, {commits} Commits, {im_verlauf} Blobs im Verlauf, {dateien} "
        f"verfolgte Dateien ({im_baum} davon eigene Objekte); {len(objekte)} Objekte "
        f"gescannt; Git-Lesen {t_git:.1f} s"
    )

    t1 = time.perf_counter()
    funde_ds, detektoren = runde_detect_secrets(objekte)
    t_ds = time.perf_counter() - t1
    t2 = time.perf_counter()
    funde_muster = runde_muster(objekte)
    t_muster = time.perf_counter() - t2
    kontonamen = runde_kontoname(objekte)
    funde = funde_ds + funde_muster
    print(
        f"Runde 1 detect-secrets ({detektoren} Detektoren): {len(funde_ds)} Funde, "
        f"{t_ds:.1f} s"
    )
    print(
        f"Runde 2 Muster ({len(MUSTER)} Muster): {len(funde_muster)} Funde, "
        f"{t_muster:.1f} s"
    )

    if schreiben:
        alt: dict[tuple[str, str, str], Eintrag] = {}
        if basislinie.is_file():
            try:
                alt = basislinie_laden(basislinie)
            except WerkzeugFehler as e:
                print(f"Hinweis: bisherige Basislinie nicht uebernommen ({e})")
        uebernommen, neu = basislinie_schreiben(basislinie, funde, alt)
        print(
            f"geschrieben: {basislinie.name} -- {uebernommen} Eintraege uebernommen, "
            f"{neu} neu als {UNGEPRUEFT!r}"
        )
        return 0

    verwendet: set[tuple[str, str, str]] = set()
    neue: list[Fund] = []
    je_klasse: dict[str, int] = {}
    for f in funde:
        eintrag = bekannt.get(f.schluessel)
        if eintrag is None:
            neue.append(f)
        else:
            verwendet.add(f.schluessel)
            je_klasse[eintrag.klasse] = je_klasse.get(eintrag.klasse, 0) + 1
    verwaist = len(bekannt) - len(verwendet)
    klassen = ", ".join(f"{k} {n}" for k, n in sorted(je_klasse.items()))
    print(
        f"Basislinie {basislinie.name}: {len(bekannt)} Eintraege, {len(verwendet)} "
        f"verwendet, {verwaist} ohne Fund im Repo; bekannte Funde je Klasse: "
        f"{klassen or '-'}"
    )
    if alles:
        for f in sorted(funde, key=lambda f: (f.pfad, f.zeile, f.gattung)):
            eintrag = bekannt.get(f.schluessel)
            marke = f"bekannt/{eintrag.klasse}" if eintrag else "NEU"
            print(f"  {marke:22s} {_fundzeile(f, objekte[f.objekt])}")

    print("-" * 88)
    print(f"NEUE FUNDE: {len(neue)}")
    for f in sorted(neue, key=lambda f: (f.pfad, f.zeile, f.gattung)):
        print(f"  NEU  {_fundzeile(f, objekte[f.objekt])}")

    print("-" * 88)
    im_tor = kontonamen.im_tor(kontoname_sperre)
    je_gruppe = kontonamen.je_gruppe
    print(
        f"KONTONAME (C:\\Users\\<name> in verfolgten Dateien; Platzhalter <...> und "
        f"... zaehlen nicht): {kontonamen.treffer} Treffer in "
        f"{len(kontonamen.je_datei)} Dateien, {len(kontonamen.je_name)} Namen "
        f"(Treffer je Name: {kontonamen.je_name or '-'}); nach Gruppe: "
        + ", ".join(f"{g} {n}" for g, n in je_gruppe.items())
    )
    print(
        f"  Tor --kontoname-sperre {kontoname_sperre}: {im_tor} Treffer im "
        f"Geltungsbereich -> {'rot' if im_tor else 'gruen'}"
    )
    reihenfolge = {g: i for i, g in enumerate(je_gruppe)}
    for pfad, n in sorted(
        kontonamen.je_datei.items(),
        key=lambda x: (reihenfolge[gruppe(x[0])], -x[1], x[0]),
    ):
        print(f"  {n:3d}  [{gruppe(pfad)}] {pfad}")

    print("=" * 88)
    rot = bool(neue) or im_tor > 0
    print(
        f"ERGEBNIS: {len(neue)} neue Funde, {len(verwendet)} bekannte, "
        f"{kontonamen.treffer} Kontonamen ({im_tor} im Tor '{kontoname_sperre}'); "
        f"Dauer {time.perf_counter() - t0:.1f} s; Exit {1 if rot else 0}"
    )
    return 1 if rot else 0


def main(argv: list[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--repo", type=Path, default=REPO, help="Repository (Vorgabe: dieses)"
    )
    ap.add_argument(
        "--basislinie",
        type=Path,
        default=None,
        help=f"Basislinie (Vorgabe: <repo>/{BASISLINIE})",
    )
    ap.add_argument(
        "--basislinie-schreiben",
        action="store_true",
        help="aktuellen Stand als Basislinie schreiben (neue Funde als ungeprueft)",
    )
    ap.add_argument(
        "--kontoname-sperre",
        choices=SPERREN,
        default=LEBEND,
        help=(
            "Kontonamen machen den Lauf rot: in lebenden Dateien (Vorgabe) oder in "
            "allen verfolgten, also auch in den eingefrorenen Gruppen archiv/, "
            "PROGRAMM/eingang/, PROGRAMM/masterprompts/"
        ),
    )
    ap.add_argument("--alles", action="store_true", help="auch bekannte Funde listen")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    basislinie = (
        Path(args.basislinie).resolve() if args.basislinie else repo / BASISLINIE
    )
    try:
        return lauf(
            repo,
            basislinie,
            schreiben=args.basislinie_schreiben,
            kontoname_sperre=args.kontoname_sperre,
            alles=args.alles,
        )
    except WerkzeugFehler as e:
        # Auch im Fehlerfall kein Rechnerpfad in der Ausgabe (CI-Protokolle sind
        # oeffentlich): git nennt in seinen Meldungen gern den absoluten Pfad.
        text = str(e)
        for absolut in sorted(
            {str(repo), repo.as_posix(), str(basislinie), basislinie.as_posix()},
            key=len,
            reverse=True,
        ):
            text = text.replace(absolut, "<pfad>")
        print(f"WERKZEUGFEHLER: {text}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
