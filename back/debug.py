import json
import logging
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "debug-config.json").read_text())
ARTIFACT_DIRECTORY = ROOT / CONFIG["artifact_directory"]

_logger = logging.getLogger("easyplu.debug")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False
if not _logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(handler)


def enabled(feature):
    development = os.getenv("APP_ENV", "production").lower() == "development"
    production = os.getenv("NODE_ENV", "").lower() == "production"
    return bool(development and not production and CONFIG.get("enabled") and CONFIG.get(feature, False))


def log(component, *values):
    if enabled(component):
        _logger.debug("[%s] %s", component, " ".join(str(value) for value in values))


def log_exception(component):
    if enabled(component) and enabled("tracebacks"):
        _logger.debug("[%s] Exception details", component, exc_info=True)
