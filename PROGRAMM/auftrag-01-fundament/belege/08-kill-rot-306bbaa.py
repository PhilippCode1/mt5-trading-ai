"""A6 ROT gegen 306bbaa: der Zustand ueberlebt den Abschuss NICHT (Gegenlese T10, E22).

Bei 306bbaa ist RiskManager(zustand=None) die Vorgabe -- fluechtig. Dieser Prozess
setzt einen Drawdown-Halt, wird von aussen hart abgeschossen, und ein zweiter Prozess
fragt ohne jede Umgebungsvariable, ob der Halt noch wirkt.
"""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

WT = Path(sys.argv[1])
KIND = '''
import sys, time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[1] + "/tools")
from wiederanlaufprobe import TS, _autorisiere, _konto
from mt5_trading_ai.execution.risk_manager import RiskManager
kern = RiskManager()                      # 306bbaa: zustand=None ist die Vorgabe
kern.observe_equity(TS, Decimal("10000"))
urteil = _autorisiere(kern, _konto("8000"), TS + timedelta(minutes=1))
print("HALT" if (not urteil.approved and urteil.latch_halt) else "KEIN HALT", flush=True)
while True:
    time.sleep(0.2)
'''
FRAGE = '''
import sys
from datetime import timedelta
from decimal import Decimal
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[1] + "/tools")
from wiederanlaufprobe import TS, _autorisiere, _konto
from mt5_trading_ai.execution.risk_manager import RiskManager
kern = RiskManager()
urteil = _autorisiere(kern, _konto("10000"), TS + timedelta(hours=2))
print(f"approved={urteil.approved} latch_halt={urteil.latch_halt} reason={urteil.reason}")
'''
umgebung = {k: v for k, v in os.environ.items() if not k.startswith("MT5_")}
kind = subprocess.Popen([sys.executable, "-B", "-c", KIND, str(WT)], cwd=WT, env=umgebung,
                        stdout=subprocess.PIPE, text=True, encoding="utf-8")
erste = kind.stdout.readline().strip()
print("Lauf 1 (306bbaa):", erste)
subprocess.run(["taskkill", "/F", "/T", "/PID", str(kind.pid)], capture_output=True)
kind.wait(timeout=30)
print("Abschuss: taskkill /F /T -> Rueckgabewert", kind.returncode)
zweite = subprocess.run([sys.executable, "-B", "-c", FRAGE, str(WT)], cwd=WT, env=umgebung,
                        capture_output=True, text=True, encoding="utf-8")
print("Lauf 2 (Neustart, volles Konto):", (zweite.stdout or zweite.stderr).strip()[-300:])
print("ROT" if "approved=True" in zweite.stdout else "nicht rot")
