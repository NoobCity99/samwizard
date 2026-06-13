from __future__ import annotations

import os
from pathlib import Path


DEV_SESSION_SECRET = "samwizard-dev-session-secret"
DEV_STATE_DIR = Path(".samwizard-state")


def session_secret_key() -> str:
    return os.environ.get("SAMWIZARD_SECRET_KEY") or DEV_SESSION_SECRET


def samwizard_state_dir() -> Path:
    return Path(os.environ.get("SAMWIZARD_STATE_DIR") or DEV_STATE_DIR)
