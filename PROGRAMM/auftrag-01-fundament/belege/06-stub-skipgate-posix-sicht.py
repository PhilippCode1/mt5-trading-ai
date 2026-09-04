"""Simulation der POSIX-Sicht auf standard_zustandsordner (T6 "T", Windows-Pfad-Test).

Zeigt, warum tests/test_risiko_zustand.py::test_localappdata_wird_nur_unter_windows_gefragt
auf ubuntu-latest rot war (CI-Lauf 4d02db3) und mit PureWindowsPath gruen ist. Die alte
und die neue Entscheidungsregel werden mit PurePosixPath als "Path der laufenden
Plattform" nachgerechnet -- das ist genau die Sicht der Linux-CI.
"""

from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

sys.path.insert(0, sys.argv[1])
from mt5_trading_ai.execution.risiko_zustand import standard_zustandsordner  # noqa: E402

LOKAL = r"C:\Users\<konto>\AppData\Local"
HEIM_POSIX = PurePosixPath("/home/runner")
KONTO = Path.home().name  # Kontoname des Rechners, in der Ausgabe redigiert


def alt_posix(roh: str) -> PurePosixPath:
    """risiko_zustand.py:407 vor T6, mit Path := PurePosixPath (Linux-Sicht)."""
    if roh and PurePosixPath(roh).is_absolute():
        return PurePosixPath(roh) / "mt5_trading_ai" / "risiko"
    return HEIM_POSIX / ".local" / "state" / "mt5_trading_ai" / "risiko"


def neu_posix(roh: str, *, windows: bool) -> PurePosixPath:
    """standard_zustandsordner nach T6, mit Path := PurePosixPath (Linux-Sicht)."""
    rein = PureWindowsPath if windows else PurePosixPath
    if roh and rein(roh).is_absolute():
        return PurePosixPath(roh) / "mt5_trading_ai" / "risiko"
    return HEIM_POSIX / ".local" / "state" / "mt5_trading_ai" / "risiko"


print(f"LOCALAPPDATA (Testwert): {LOKAL!r}")
print(f"PurePosixPath(LOKAL).is_absolute()   = {PurePosixPath(LOKAL).is_absolute()}")
print(f"PureWindowsPath(LOKAL).is_absolute() = {PureWindowsPath(LOKAL).is_absolute()}")
print(f"Path(LOKAL).is_absolute() auf diesem Rechner ({sys.platform}) = {Path(LOKAL).is_absolute()}")
print()
alt = alt_posix(LOKAL)
print(f"ALT, Windows-Zweig unter POSIX: {alt}")
print(f"  parts[:-2] = {alt.parts[:-2]}")
print(f"  erwartet   = {PurePosixPath(LOKAL).parts}  -> gleich: {alt.parts[:-2] == PurePosixPath(LOKAL).parts}")
print("  (das ist die Assertion aus dem CI-Beleg 00-ci-nach-t0.txt, Zeile 22)")
neu = neu_posix(LOKAL, windows=True)
print(f"NEU, Windows-Zweig unter POSIX: {neu}")
print(f"  PureWindowsPath(str(neu)) == PureWindowsPath(LOKAL, 'mt5_trading_ai', 'risiko'): {PureWindowsPath(str(neu)) == PureWindowsPath(LOKAL, 'mt5_trading_ai', 'risiko')}")
print(f"  PureWindowsPath(str(neu)).is_absolute(): {PureWindowsPath(str(neu)).is_absolute()}")
neu_p = neu_posix("/home/runner/eigener-zustand", windows=False)
print(f"NEU, POSIX-Zweig unter POSIX (XDG_STATE_HOME=/home/runner/eigener-zustand): {neu_p}")
print()
print("Echte Funktion auf diesem Rechner:")
XDG = "/home/test/eigener-zustand"
umg = {"LOCALAPPDATA": LOKAL, "XDG_STATE_HOME": XDG}
w = standard_zustandsordner(umgebung=umg, ist_windows=True)
p = standard_zustandsordner(umgebung=umg, ist_windows=False)
print(f"  ist_windows=True : {str(w).replace(KONTO, '<konto>')}")
print(f"  ist_windows=False: {str(p).replace(KONTO, '<konto>')}")
print(f"  PureWindowsPath(str(w)) == PureWindowsPath(LOKAL, 'mt5_trading_ai', 'risiko'): {PureWindowsPath(str(w)) == PureWindowsPath(LOKAL, 'mt5_trading_ai', 'risiko')}")
print(f"  PurePosixPath(p.as_posix()) == PurePosixPath(XDG, 'mt5_trading_ai', 'risiko'): {PurePosixPath(p.as_posix()) == PurePosixPath(XDG, 'mt5_trading_ai', 'risiko')}")
print(f"  'AppData' not in str(p): {'AppData' not in str(p)}")
print()
print("Gegenprobe der alten Testfassung (XDG = Path.home()/'eigener-zustand', nur auf dem")
print("laufenden Rechner absolut) gegen die neue Regel auf diesem Rechner:")
alt_xdg = str(Path.home() / "eigener-zustand")
print(f"  PurePosixPath({alt_xdg.replace(KONTO, '<konto>')!r}).is_absolute() = {PurePosixPath(alt_xdg).is_absolute()}")
print("  -> der POSIX-Zweig nimmt den Heimatpfad; darum traegt der Test jetzt einen POSIX-Pfad.")
