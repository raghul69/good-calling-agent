"""Compatibility entrypoint for outbound production preflight.

The canonical implementation lives at repo root in `verify_outbound_preflight.py`.
This wrapper keeps older docs/automation that call `scripts/preflight_outbound.py`
working.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from verify_outbound_preflight import main


if __name__ == "__main__":
    raise SystemExit(main())
