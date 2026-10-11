"""Application diagnostics configured by the repository's debug-config.json."""

import json
import logging
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
    return bool(CONFIG.get("enabled") and CONFIG.get(feature, False))


def _redact(value):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if any(word in str(key).lower() for word in ("token", "password", "cookie", "authorization", "otp", "secret")) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


def log(component, *values):
    if enabled(component):
        _logger.debug("[%s] %s", component, " ".join(str(_redact(value)) for value in values))


def log_exception(component):
    if enabled(component) and enabled("tracebacks"):
        _logger.debug("[%s] Exception details", component, exc_info=True)
