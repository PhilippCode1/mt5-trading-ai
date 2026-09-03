"""T5, Schritt 4: MODULES.md mit Aufrufern je Modul; README-Kennzahlenblock aus dem Code erzeugen.

Eigenes Skript (2026-09-03). Patcht tools/gen_docs.py: (1) je Modul die Zahl der
Importzeilen aus Paket, Werkzeugen und Tests (das Architekturdokument aus dem Code,
A8); (2) der KENNZAHLEN-Block in README.md wird von gen_docs geschrieben und von
``--check`` gegen den Code gehalten -- eine Zahl an einer Stelle, erzeugt statt gepflegt.

Aufruf: python PROGRAMM/auftrag-01-fundament/belege/05-gen-docs-aufrufer.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
NL = chr(10)


def main() -> int:
    p = REPO / "tools/gen_docs.py"
    s = p.read_text(encoding="utf-8")
    assert "def _aufrufer(" not in s, "schon gepatcht"

    # Kopf: Zweck erweitern
    alt = '"""Erzeugt MODULES.md AUS DEM CODE des Pakets ``mt5_trading_ai``.' + NL
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        '"""Erzeugt MODULES.md und den README-Kennzahlenblock AUS DEM CODE des Pakets.' + NL
        + NL
        + "MODULES.md ist das Architekturdokument (Abnahmekatalog A8): je Modul Zeilen, erste" + NL
        + "Docstring-Zeile, oeffentliche API und die Aufrufer -- gezaehlt als Importzeilen aus" + NL
        + "dem Paket, den Werkzeugen und den Tests. Ein Modul mit 0 Aufrufern ausserhalb der" + NL
        + "Tests hat keinen nachgewiesenen Aufrufpfad (Regel 5 des Rahmens). Der" + NL
        + "KENNZAHLEN-Block in README.md wird hier geschrieben, nicht gepflegt." + NL,
    )
    alt = "  python tools/gen_docs.py            schreibt MODULES.md" + NL
    assert s.count(alt) == 1
    s = s.replace(alt, "  python tools/gen_docs.py            schreibt MODULES.md und den README-Block" + NL)

    # Importe und Shim
    alt = "REPO = Path(__file__).resolve().parents[1]" + NL + 'PKG = REPO / "mt5_trading_ai"' + NL
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        "REPO = Path(__file__).resolve().parents[1]" + NL
        + "if str(REPO) not in sys.path:" + NL
        + "    sys.path.insert(0, str(REPO))" + NL
        + NL
        + "from tools.check_doc_numbers import canonical  # noqa: E402" + NL
        + NL
        + 'PKG = REPO / "mt5_trading_ai"' + NL
        + 'README = REPO / "README.md"' + NL
        + 'ANFANG = "<!-- KENNZAHLEN-ANFANG"' + NL
        + 'ENDE = "<!-- KENNZAHLEN-ENDE -->"' + NL,
    )
    if "import re" + NL not in s:
        s = s.replace("import ast" + NL, "import ast" + NL + "import re" + NL, 1)

    # Aufrufer-Zaehlung
    alt = "def render() -> str:" + NL
    assert s.count(alt) == 1
    aufrufer = NL.join(
        [
            "_QUELLEN: dict[str, list[Path]] = {}",
            "",
            "",
            "def _zeilen(wurzel: Path) -> list[Path]:",
            "    if wurzel.name not in _QUELLEN:",
            '        _QUELLEN[wurzel.name] = [',
            '            p for p in wurzel.rglob("*.py") if "__pycache__" not in p.parts',
            "        ]",
            "    return _QUELLEN[wurzel.name]",
            "",
            "",
            "def _aufrufer(stamm: str, wurzel: Path, selbst: Path) -> int:",
            '    """Importzeilen aus ``wurzel``, die das Modul ``stamm`` (z. B. risk/sizing) treffen."""',
            '    punkt = stamm.replace("/", ".")',
            '    name = stamm.split("/")[-1]',
            '    paket = ".".join(stamm.split("/")[:-1])',
            "    muster = [",
            '        re.compile(rf"^\\s*from mt5_trading_ai\\.{re.escape(punkt)} import"),',
            '        re.compile(rf"^\\s*import mt5_trading_ai\\.{re.escape(punkt)}\\b"),',
            "    ]",
            "    if paket:",
            "        muster.append(",
            "            re.compile(",
            '                rf"^\\s*from mt5_trading_ai\\.{re.escape(paket)} import .*\\b{re.escape(name)}\\b"',
            "            )",
            "        )",
            "    n = 0",
            "    for p in _zeilen(wurzel):",
            "        if p == selbst:",
            "            continue",
            '        for z in p.read_text(encoding="utf-8", errors="replace").splitlines():',
            "            if any(m.search(z) for m in muster):",
            "                n += 1",
            "    return n",
            "",
            "",
            "def render() -> str:",
        ]
    )
    s = s.replace(alt, aufrufer + NL)
    alt = '        "Diese Datei ist die **einzige** Stelle, an der die Zeilenzahl je Modul steht.",'
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        '        "Diese Datei ist die **einzige** Stelle, an der die Zeilenzahl je Modul steht.",' + NL
        + '        "Je Modul stehen die Aufrufer als Importzeilen (Paket / Werkzeuge / Tests);",' + NL
        + '        "0 Aufrufer ausserhalb der Tests heisst: kein nachgewiesener Aufrufpfad.",',
    )
    alt = '        out.append(f"Zeilen: {len(text.splitlines())}")' + NL
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        alt
        + '        stamm = path.relative_to(PKG).with_suffix("").as_posix()' + NL
        + '        a = _aufrufer(stamm, PKG, path)' + NL
        + '        b = _aufrufer(stamm, REPO / "tools", path)' + NL
        + '        c = _aufrufer(stamm, REPO / "tests", path)' + NL
        + '        out.append(f"Aufrufer: Paket {a} · Werkzeuge {b} · Tests {c}")' + NL,
    )

    # README-Block schreiben und pruefen
    alt = "def main() -> int:" + NL
    assert s.count(alt) == 1
    block = NL.join(
        [
            "def kennzahlen_block() -> str:",
            "    canon = canonical()",
            "    zeilen = [",
            '        ANFANG + " (erzeugt von tools/gen_docs.py, geprueft von tests/test_readme_numbers.py) -->"',
            "    ]",
            '    zeilen += [f"- {k}: {v}" for k, v in canon.items()]',
            "    zeilen.append(ENDE)",
            '    return "\\n".join(zeilen)',
            "",
            "",
            "def readme_mit_block() -> tuple[str, str]:",
            '    """(aktueller README-Text, README-Text mit erzeugtem Block)."""',
            '    text = README.read_text(encoding="utf-8")',
            "    start = text.index(ANFANG)",
            "    ende = text.index(ENDE) + len(ENDE)",
            "    return text, text[:start] + kennzahlen_block() + text[ende:]",
            "",
            "",
            "def main() -> int:",
        ]
    )
    s = s.replace(alt, block + NL)
    alt = (
        "    generated = render()" + NL
        + "    if args.check:" + NL
        + '        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""' + NL
        + "        if current != generated:" + NL
    )
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        "    generated = render()" + NL
        + "    readme_alt, readme_neu = readme_mit_block()" + NL
        + "    if args.check:" + NL
        + "        if readme_alt != readme_neu:" + NL
        + "            print(" + NL
        + '                "FEHLGESCHLAGEN — der README-Kennzahlenblock ist veraltet. "' + NL
        + '                "`python tools/gen_docs.py` ausfuehren."' + NL
        + "            )" + NL
        + "            return 1" + NL
        + '        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""' + NL
        + "        if current != generated:" + NL,
    )
    alt = '    OUT.write_text(generated, encoding="utf-8")' + NL
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        '    OUT.write_text(generated, encoding="utf-8", newline="\\n")' + NL
        + "    if readme_alt != readme_neu:" + NL
        + '        README.write_text(readme_neu, encoding="utf-8", newline="\\n")' + NL
        + '        print("README.md: Kennzahlenblock erneuert.")' + NL,
    )
    p.write_text(s, encoding="utf-8", newline="")
    print("tools/gen_docs.py: Aufrufer je Modul, README-Block erzeugt und geprueft")
    return 0


if __name__ == "__main__":
    sys.exit(main())
