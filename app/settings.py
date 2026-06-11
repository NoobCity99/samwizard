from __future__ import annotations

import os


DEV_SESSION_SECRET = "samwizard-dev-session-secret"


def session_secret_key() -> str:
    return os.environ.get("SAMWIZARD_SECRET_KEY") or DEV_SESSION_SECRET
