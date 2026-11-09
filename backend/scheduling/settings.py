"""Shared web/CLI scheduling intervals."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def settings():
    config = json.loads((ROOT / "config/scheduled-tests.json").read_text())
    return max(60, float(config["interval_seconds"])), max(20, float(config["account_delay_seconds"]))


