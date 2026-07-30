# -*- coding: utf-8 -*-
"""Compatibility entrypoint for the active offline episode recompute CLI.

The production scheduler points directly to ``episode_rules_v13_5.py``.  This
module is kept for older scripts that still call ``exports/compute_episodes.py``;
it delegates to the same CLI so there is only one implementation to maintain.
"""

from __future__ import annotations

import sys
from pathlib import Path


EXPORTS_DIR = Path(__file__).resolve().parent
if str(EXPORTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPORTS_DIR))

from episode_rules_v13_5 import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
