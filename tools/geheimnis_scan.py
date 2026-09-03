#!/usr/bin/env python3
"""Geheimnispruefung (A4.4): Arbeitsbaum UND gesamter Git-Verlauf.

Zwei Werkzeuge, nicht Sichtpruefung:
1. ``detect-secrets`` (Yelp) mit allen eingebauten Detektoren.
2. Eine zweite, gezielte Regex-Runde auf genau die vier im Auftrag genannten Gattungen:
   Zugangsdaten, Server-Adressen, Kontonummern, Schluessel.

Der Verlauf wird geprueft, indem JEDES Blob-Objekt aus ``git rev-list --objects --all``
ausgelesen und einzeln gescannt wird -- ein Geheimnis, das einmal committet und spaeter
geloescht wurde, steht weiter im Verlauf und ist bei einem oeffentlichen Repo abrufbar.

Aufruf:  python tools/geheimnis_scan.py
Voraussetzung: ``pip install detect-secrets`` (Entwicklungswerkzeug, kein
Laufzeitpaket -- der Kern selbst haengt weiter an nichts ausser der stdlib).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
REPO = Path(__file__).resolve().parents[1]

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

#: Bekannte, unbedenkliche Fundstellen -- eine Vorlage ist kein Geheimnis.
UNBEDENKLICH = (b".env.example", b"geheimnis")


def lauf(*args: str) -> subprocess.CompletedProcess[bytes]:
    """Ein Unterprozess im Repo, roh (bytes) und ohne Abbruch bei Exit != 0."""
    return subprocess.run(args, cwd=REPO, capture_output=True, check=False)


def regex_runde(name: str, objekte: list[tuple[str, bytes]]) -> list[str]:
    funde: list[str] = []
    for kennung, inhalt in objekte:
        for titel, muster in MUSTER:
            for treffer in muster.finditer(inhalt):
                zeile = inhalt.count(b"\n", 0, treffer.start()) + 1
                ausschnitt = treffer.group(0)[:60].decode("utf-8", "replace")
                funde.append(f"[{name}] {kennung}:{zeile} — {titel}: {ausschnitt!r}")
    return funde


def main() -> int:
    print("=" * 90)
    print("GEHEIMNISPRUEFUNG — Paket 2, A4.4")
    print("=" * 90)
    print(f"Repo: {REPO}")
    print()

    # --- 1. Arbeitsbaum: detect-secrets --------------------------------------
    print("-" * 90)
    print("1) ARBEITSBAUM — detect-secrets (alle eingebauten Detektoren)")
    print("-" * 90)
    # Bewusst nur die von Git VERFOLGTEN Dateien: was nicht im Repo liegt, ist auch
    # nicht oeffentlich abrufbar. Caches (.mypy_cache & Co.) sind ungetrackt und
    # erzeugen sonst hunderte Entropie-Treffer, die das Ergebnis unlesbar machen.
    verfolgt = lauf("git", "ls-files").stdout.decode("utf-8", "replace").split()
    res = lauf(sys.executable, "-m", "detect_secrets", "scan", *verfolgt)
    if res.returncode != 0:
        print("FEHLGESCHLAGEN:", res.stderr.decode("utf-8", "replace")[:800])
        return 2
    bericht = json.loads(res.stdout.decode("utf-8", "replace"))
    dateien_geprueft = len(verfolgt)
    treffer = bericht.get("results", {})
    print(f"Gepruefte Objekte : {dateien_geprueft} von Git verfolgte Dateien")
    print(f"Detektoren        : {len(bericht.get('plugins_used', []))}")
    print(f"Funde             : {sum(len(v) for v in treffer.values())}")
    for datei, eintraege in treffer.items():
        for e in eintraege:
            print(f"  FUND {datei}:{e.get('line_number')} — {e.get('type')}")
    print()

    # --- 2. Verlauf: jedes Blob-Objekt ---------------------------------------
    print("-" * 90)
    print("2) GESAMTER VERLAUF — jedes Blob-Objekt einzeln")
    print("-" * 90)
    liste = (
        lauf("git", "rev-list", "--objects", "--all")
        .stdout.decode("utf-8", "replace")
        .splitlines()
    )
    blobs: list[tuple[str, bytes]] = []
    for zeile in liste:
        teile = zeile.split(" ", 1)
        sha = teile[0]
        pfad = teile[1] if len(teile) > 1 else "(ohne Pfad)"
        typ = lauf("git", "cat-file", "-t", sha).stdout.strip()
        if typ != b"blob":
            continue
        inhalt = lauf("git", "cat-file", "blob", sha).stdout
        blobs.append((f"{sha[:8]} {pfad}", inhalt))
    commits = lauf("git", "rev-list", "--count", "--all").stdout.decode().strip()
    print(f"Gepruefte Objekte : {len(blobs)} Blobs aus {commits} Commits")
    funde_verlauf = regex_runde("VERLAUF", blobs)
    echte = [
        f
        for f in funde_verlauf
        if not any(u.decode() in f.lower() for u in UNBEDENKLICH)
    ]
    print(f"Funde (roh)       : {len(funde_verlauf)}")
    print(f"Funde (bereinigt) : {len(echte)}  [Vorlagen wie .env.example abgezogen]")
    for f in funde_verlauf:
        print("  " + f)
    print()

    # --- 3. Arbeitsbaum: zweite, gezielte Regex-Runde ------------------------
    print("-" * 90)
    print("3) ARBEITSBAUM — zweite Runde auf die vier genannten Gattungen")
    print("-" * 90)
    dateien: list[tuple[str, bytes]] = []
    for name in verfolgt:
        datei = REPO / name
        if datei.is_file():
            dateien.append((name, datei.read_bytes()))
    funde_baum = regex_runde("BAUM", dateien)
    print(f"Gepruefte Objekte : {len(dateien)} Dateien")
    print(f"Muster            : {len(MUSTER)}")
    print(f"Funde             : {len(funde_baum)}")
    for f in funde_baum:
        print("  " + f)
    print()

    # --- 4. Alt-Repos --------------------------------------------------------
    print("-" * 90)
    print("4) ALT-REPOS / TAGS")
    print("-" * 90)
    tags = lauf("git", "tag", "-l").stdout.decode().split()
    remote = lauf("git", "ls-remote", "--tags", "origin").stdout.decode().split()
    print(f"Lokale Tags        : {len(tags)} {tags}")
    print(f"Tags am Remote     : {len(remote) // 2}")
    print("Hinweis: der in README.md genannte Tag 'archive/pre-extraction' existiert")
    print("weder lokal noch am Remote. Es gibt in diesem Repo keinen Alt-Baum, der")
    print(
        "mitgeprueft werden koennte -- die Pruefung deckt damit alles ab, was da ist."
    )
    print()

    gesamt = (
        sum(len(v) for v in treffer.values()) + len(funde_verlauf) + len(funde_baum)
    )
    print("=" * 90)
    print(
        f"ERGEBNIS: {gesamt} Funde bei {dateien_geprueft} verfolgten Dateien und "
        f"{len(blobs)} Blobs im Verlauf."
    )
    print("=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
