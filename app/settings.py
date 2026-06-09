from __future__ import annotations

import os


DEV_SESSION_SECRET = "samba-wizard-milestone-1-dev"


def session_secret_key() -> str:
    return os.environ.get("SAMWIZARD_SECRET_KEY") or DEV_SESSION_SECRET
