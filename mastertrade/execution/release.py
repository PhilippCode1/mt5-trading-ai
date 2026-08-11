"""Mehrteilige Freigabe fuer Order-Submit an einen echten Markt.

Ersetzt die frueheren Kommerzgates (`MODUL_MATE_GATE_ENFORCEMENT`,
`LIVE_BROKER_REQUIRE_COMMERCIAL_GATES`, Prepaid-Guthabenpruefung). Diese Gates
haben Live-Orders faktisch blockiert — nicht weil sie Sicherheitsgates waren,
sondern weil ein Vertrag in einer Tenant-Tabelle fehlte. Ihr ersatzloses
Entfernen haette den Weg zum Markt geoeffnet.

Der Ersatz ist bewusst **nicht** ein einzelner Schalter. Eroeffnende Orders an
einen echten Markt verlangen vier unabhaengige Schalter **und** eine
nichtleere Freigabekennung. Alle Defaults sind aus.

Zwei Regeln, die die Gestaltung bestimmen:

* **Nicht bewertbar gilt als nicht erfuellt.** Fehlt ein Attribut auf dem
  Settings-Objekt, wird es als fehlend gezaehlt, nicht als erfuellt. Ein
  Tippfehler im Attributnamen macht die Sperre damit strenger, nicht loser.
* **Risikoabbau bleibt immer moeglich.** Die Freigabe gilt fuer eroeffnende
  Orders. Reduce-Only-Orders passieren, weil eine Sperre, die das Schliessen
  einer offenen Position verhindert, das Risiko erhoeht statt es zu senken.
  Ohne je erteilte Freigabe kann es keine offene Position geben, deshalb
  eroeffnet diese Ausnahme keinen Weg zum Markt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LIVE_RELEASE_POLICY_VERSION = "live-release-v1"

#: (Attributname auf dem Settings-Objekt, ENV-Alias). Alle Defaults sind ``False``.
REQUIRED_SWITCHES: tuple[tuple[str, str], ...] = (
    (
        "live_release_owner_ack",
        "LIVE_RELEASE_OWNER_ACK",
    ),
    (
        "live_release_strategy_approved",
        "LIVE_RELEASE_STRATEGY_APPROVED",
    ),
    (
        "live_release_risk_limits_configured",
        "LIVE_RELEASE_RISK_LIMITS_CONFIGURED",
    ),
    (
        "live_release_venue_demo_verified",
        "LIVE_RELEASE_VENUE_DEMO_VERIFIED",
    ),
)

#: Freigabekennung: verweist auf die menschliche Entscheidung (Datum, Strategie,
#: Version). Leer oder fehlend = keine Freigabe.
RELEASE_ID_FIELD = ("live_release_id", "LIVE_RELEASE_ID")

_SENTINEL = object()


@dataclass(frozen=True)
class LiveReleaseDecision:
    """Ergebnis der Freigabepruefung. ``allowed`` ist nur bei Vollstaendigkeit True."""

    allowed: bool
    policy_version: str
    missing: tuple[str, ...]
    reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "policy_version": self.policy_version,
            "missing": list(self.missing),
            "reason": self.reason,
        }


def _switch_is_set(settings: Any, attribute: str) -> bool:
    value = getattr(settings, attribute, _SENTINEL)
    if value is _SENTINEL:
        # Nicht bewertbar -> nicht erfuellt.
        return False
    return value is True


def _release_id_is_set(settings: Any) -> bool:
    value = getattr(settings, RELEASE_ID_FIELD[0], _SENTINEL)
    if value is _SENTINEL or value is None:
        return False
    return bool(str(value).strip())


def evaluate_live_release(settings: Any) -> LiveReleaseDecision:
    """Pruefe die mehrteilige Freigabe fuer eroeffnende Orders an einem echten Markt."""
    missing: list[str] = []
    for attribute, env_alias in REQUIRED_SWITCHES:
        if not _switch_is_set(settings, attribute):
            missing.append(env_alias)
    if not _release_id_is_set(settings):
        missing.append(RELEASE_ID_FIELD[1])

    if missing:
        return LiveReleaseDecision(
            allowed=False,
            policy_version=LIVE_RELEASE_POLICY_VERSION,
            missing=tuple(missing),
            reason="live_release_incomplete",
        )
    return LiveReleaseDecision(
        allowed=True,
        policy_version=LIVE_RELEASE_POLICY_VERSION,
        missing=(),
        reason=None,
    )


def live_release_blocks_opening_order(
    settings: Any, *, reduce_only: bool
) -> LiveReleaseDecision | None:
    """``None`` wenn die Order passieren darf, sonst die ablehnende Entscheidung.

    Reduce-Only passiert immer (siehe Modul-Docstring).
    """
    if reduce_only:
        return None
    decision = evaluate_live_release(settings)
    if decision.allowed:
        return None
    return decision
