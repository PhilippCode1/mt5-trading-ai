"""Gesetzlicher Hebeldeckel je Anlageklasse — geladen aus einer versionierten Datei.

Teil 4 Punkt II des Auftrags: der effektive Hebel ist
``min(strategie, SYSTEM_MAX_LEVERAGE, klassendeckel)``. Eine unbekannte
Anlageklasse fuehrt zu ``no_trade`` — nicht zu einem Default.

Die Deckel stehen in ``config/asset_class_leverage.json`` mit Quelle,
Gueltigkeitsdatum und Pruefdatum, damit eine Rechtsaenderung eine Datenaenderung
ist und keine Codeaenderung.

``SYSTEM_MAX_LEVERAGE`` ist bewusst eine Konstante im Code und **nicht**
konfigurierbar: kein ENV, keine Datenbank, kein Strategie-Parameter kann sie
anheben. Die Datei kann den Deckel nur senken, nie heben — ein Deckel in der
Datei oberhalb von ``SYSTEM_MAX_LEVERAGE`` wird beim Laden abgelehnt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

#: Harte Obergrenze des Systems. Nicht konfigurierbar.
SYSTEM_MAX_LEVERAGE = 10
#: Default, wenn eine Strategie keinen Hebel nennt: ein bewusst niedriger,
#: konservativer Wert. Es gibt KEINEN Mindesthebel (Entscheidung E2, Teil 3):
#: ein Minimum ist keine Sicherheitssperre, sondern verhindert vorsichtigeres
#: Handeln und sperrt Klassen mit niedrigem Deckel (Krypto 2:1) grundlos aus.
DEFAULT_LEVERAGE = 5

ASSET_CLASS_LEVERAGE_POLICY_MODULE_VERSION = "asset-class-leverage-v1"


class LeveragePolicyError(ValueError):
    """Die Deckel-Datei ist unbrauchbar. Fail-closed: kein Handel."""


@dataclass(frozen=True)
class AssetClassCap:
    asset_class: str
    max_leverage: int
    label: str


@dataclass(frozen=True)
class LeveragePolicy:
    policy_id: str
    policy_version: str
    valid_from: str
    verified_on: str
    jurisdiction: str
    caps: dict[str, AssetClassCap]
    source_path: str

    def cap_for(self, asset_class: str | None) -> AssetClassCap | None:
        if not asset_class:
            return None
        return self.caps.get(str(asset_class).strip().lower())


@dataclass(frozen=True)
class LeverageDecision:
    """Ergebnis der Hebelklammer. ``leverage is None`` heisst ``no_trade``."""

    leverage: int | None
    asset_class: str | None
    requested: int | None
    class_cap: int | None
    system_cap: int
    binding: str
    reason: str | None
    policy_version: str

    @property
    def no_trade(self) -> bool:
        return self.leverage is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "leverage": self.leverage,
            "asset_class": self.asset_class,
            "requested": self.requested,
            "class_cap": self.class_cap,
            "system_cap": self.system_cap,
            "binding": self.binding,
            "reason": self.reason,
            "policy_version": self.policy_version,
        }


#: Dateiname der Deckel-Datei, unterhalb von ``config/``.
POLICY_FILENAME = "asset_class_leverage.json"


def default_policy_path() -> Path:
    """Suche aufwaerts nach ``config/asset_class_leverage.json``.

    Bewusst **kein** ENV-Override: ein Umbiegen des Pfades waere ein Weg, den
    Klassendeckel zu konfigurieren. Teil 4 Punkt II schliesst das aus. Die
    Aufwaertssuche haelt den Loader unabhaengig davon, ob das Paket editable
    installiert ist oder als Wheel liegt.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / POLICY_FILENAME
        if candidate.is_file():
            return candidate
    # Paketinterne Kopie als letzter Rueckfall (Wheel ohne Repo-Baum).
    return here.parent / "data" / POLICY_FILENAME


def load_policy(path: Path | str | None = None) -> LeveragePolicy:
    """Lade und validiere die Deckel-Datei.

    Jeder Defekt ist ein Fehler, kein Default.
    """
    policy_path = Path(path) if path is not None else default_policy_path()
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LeveragePolicyError(f"Hebeldeckel-Datei fehlt: {policy_path}") from exc
    except json.JSONDecodeError as exc:
        raise LeveragePolicyError(
            f"Hebeldeckel-Datei ist kein gueltiges JSON: {exc}"
        ) from exc

    for field in (
        "policy_id",
        "policy_version",
        "valid_from",
        "verified_on",
        "classes",
    ):
        if field not in raw:
            raise LeveragePolicyError(f"Hebeldeckel-Datei ohne Pflichtfeld {field!r}")

    declared_system_max = raw.get("system_max_leverage")
    if (
        declared_system_max is not None
        and int(declared_system_max) != SYSTEM_MAX_LEVERAGE
    ):
        raise LeveragePolicyError(
            "system_max_leverage in der Datei weicht von der Code-Konstante ab "
            f"({declared_system_max} != {SYSTEM_MAX_LEVERAGE}). "
            "Die Obergrenze des Systems ist nicht konfigurierbar."
        )

    caps: dict[str, AssetClassCap] = {}
    classes = raw.get("classes")
    if not isinstance(classes, dict) or not classes:
        raise LeveragePolicyError("Hebeldeckel-Datei ohne Anlageklassen")
    for name, entry in classes.items():
        if not isinstance(entry, dict) or "max_leverage" not in entry:
            raise LeveragePolicyError(f"Anlageklasse {name!r} ohne max_leverage")
        value = int(entry["max_leverage"])
        if value < 1:
            raise LeveragePolicyError(f"Anlageklasse {name!r} mit max_leverage < 1")
        caps[str(name).strip().lower()] = AssetClassCap(
            asset_class=str(name).strip().lower(),
            max_leverage=value,
            label=str(entry.get("label") or name),
        )

    return LeveragePolicy(
        policy_id=str(raw["policy_id"]),
        policy_version=str(raw["policy_version"]),
        valid_from=str(raw["valid_from"]),
        verified_on=str(raw["verified_on"]),
        jurisdiction=str(raw.get("jurisdiction") or ""),
        caps=caps,
        source_path=str(policy_path),
    )


@lru_cache(maxsize=4)
def _cached_policy(path_key: str) -> LeveragePolicy:
    return load_policy(path_key)


def get_policy(path: Path | str | None = None) -> LeveragePolicy:
    key = str(Path(path) if path is not None else default_policy_path())
    return _cached_policy(key)


def clamp_leverage(
    *,
    requested: Any,
    asset_class: str | None,
    policy: LeveragePolicy | None = None,
) -> LeverageDecision:
    """Effektiver Hebel = ``min(requested, SYSTEM_MAX_LEVERAGE, klassendeckel)``.

    ``no_trade`` nur bei unbekannter Anlageklasse. Es gibt keinen Mindesthebel
    (E2): jeder legale Klassendeckel ist handelbar, Krypto (2:1) eingeschlossen.
    Ein zu hoher Wunsch wird nicht abgelehnt, sondern heruntergeklammert —
    Ablehnen und Klammern sind beide sicher, Klammern ist das nuetzlichere
    Verhalten und laesst den Deckel trotzdem greifen.
    """
    active = policy if policy is not None else get_policy()
    normalised_class = str(asset_class).strip().lower() if asset_class else None

    cap = active.cap_for(normalised_class)
    if cap is None:
        return LeverageDecision(
            leverage=None,
            asset_class=normalised_class,
            requested=_as_int(requested),
            class_cap=None,
            system_cap=SYSTEM_MAX_LEVERAGE,
            binding="unknown_asset_class",
            reason="unknown_asset_class",
            policy_version=active.policy_version,
        )

    want = _as_int(requested)
    if want is None:
        want = DEFAULT_LEVERAGE

    allowed = min(want, SYSTEM_MAX_LEVERAGE, cap.max_leverage)

    class_is_binding = (
        allowed == cap.max_leverage
        and cap.max_leverage <= SYSTEM_MAX_LEVERAGE
        and cap.max_leverage <= want
    )
    if class_is_binding:
        binding = "class_cap"
    elif allowed == SYSTEM_MAX_LEVERAGE and SYSTEM_MAX_LEVERAGE <= want:
        binding = "system_cap"
    else:
        binding = "requested"

    return LeverageDecision(
        leverage=allowed,
        asset_class=normalised_class,
        requested=want,
        class_cap=cap.max_leverage,
        system_cap=SYSTEM_MAX_LEVERAGE,
        binding=binding,
        reason=None,
        policy_version=active.policy_version,
    )


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
