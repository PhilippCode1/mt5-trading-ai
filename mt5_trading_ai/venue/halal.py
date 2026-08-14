"""Der Halal-Screen: das mechanisch Pruefbare erzwingen, die fiqh-Grenze benennen (S4).

Kernregel 16: Halal-Konformitaet ist Anforderung -- und "Du entscheidest das nicht
allein." Dieser Screen prueft daher nur, was **mechanisch** pruefbar ist (swapfreies
Konto, zinsfreie Margin, Instrument nicht offensichtlich verboten) und zertifiziert nie
"halal". Die fiqh-Grundfrage -- ob ein gehebelter CFD ueberhaupt zulaessig ist (gharar,
fehlendes Eigentum, Termincharakter) -- bleibt **immer** offen und wird zur Gelehrten-/
Philipp-Pruefung markiert. Fail-closed.

**Aufrufer (Paket 5):** ``Mt5Venue.submit_order`` ruft ``screen_halal`` fuer jede
eroeffnende Live-Order. Nicht mechanisch konform -> Ablehnung; da
``requires_scholar_review`` IMMER wahr ist, kann eine Live-Order nur eroeffnen, wenn ein
Mensch die Gelehrten-Entscheidung als ``halal_scholar_review_id`` hinterlegt hat --
Kernregel 16 systemseitig durchgesetzt. Auf Demo entfaellt der Screen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mt5_trading_ai.venue.protocol import AssetClass

HALAL_SCREEN_VERSION = "halal-screen-v1"

#: Anlageklassen mit einem Geschaeftsfeld, das gesondert geprueft werden muss.
_NEEDS_BUSINESS_SCREEN = frozenset({AssetClass.EQUITY})
#: Anlageklassen, die als solche fiqh-umstritten sind.
_DISPUTED_CLASSES = frozenset({AssetClass.CRYPTO})


@dataclass(frozen=True)
class HalalVerdict:
    mechanically_conformant: bool    # swapfrei + Instrument nicht offensichtl. verboten
    requires_scholar_review: bool    # die fiqh-Grundfrage (CFDs) -- immer True
    reasons: tuple[str, ...] = field(default_factory=tuple)
    version: str = HALAL_SCREEN_VERSION


def screen_halal(
    *,
    asset_class: AssetClass,
    account_swap_free: bool,
    interest_bearing_margin: bool,
) -> HalalVerdict:
    """Screene Instrument + Kontokonfiguration auf mechanische Halal-Konformitaet.

    ``mechanically_conformant`` ist nur True, wenn das Konto swapfrei ist, die Margin
    zinsfrei und das Instrument nicht verboten. ``requires_scholar_review``
    ist **immer** True: der Code entscheidet die Grundfrage nicht (Kernregel 16).
    """
    reasons: list[str] = []
    if not account_swap_free:
        reasons.append("konto_nicht_swapfrei_overnight_zins_riba")
    if interest_bearing_margin:
        reasons.append("verzinsliche_margin_riba")
    if asset_class in _NEEDS_BUSINESS_SCREEN:
        reasons.append("aktien_cfd_geschaeftsfeld_screening_noetig")
    if asset_class in _DISPUTED_CLASSES:
        reasons.append("krypto_fiqh_umstritten")
    return HalalVerdict(
        mechanically_conformant=not reasons,
        requires_scholar_review=True,
        reasons=tuple(reasons),
    )
