#!/usr/bin/env python3
"""Optional entry point for the standalone PLU handbook exporter."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from tools.plu_catalog.export import main
except ModuleNotFoundError as error:
    if error.name in {"reportlab", "PIL"}:
        raise SystemExit(
            "Missing PDF dependencies. Run: "
            ".venv/bin/python -m pip install -r tools/plu_catalog/requirements.txt"
        ) from None
    raise


if __name__ == "__main__":
    raise SystemExit(main())
