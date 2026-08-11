"""U1-Rauchtest: das Paket importiert, und die Werkzeugkette laeuft auf echtem Code.

Bewusst trivial. Der Punkt ist nicht die Aussage des Tests, sondern dass
``ruff``/``mypy``/``pytest`` beweisbar stehen, bevor die erste Fachdatei kommt.
"""

from __future__ import annotations

import mt5_trading_ai


def test_package_imports() -> None:
    assert mt5_trading_ai.__doc__
