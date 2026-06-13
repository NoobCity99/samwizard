import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.settings import DEV_SESSION_SECRET, DEV_STATE_DIR, samwizard_state_dir, session_secret_key


class SettingsTests(unittest.TestCase):
    def test_session_secret_uses_environment_value(self):
        with patch.dict(os.environ, {"SAMWIZARD_SECRET_KEY": "service-secret"}, clear=False):
            self.assertEqual(session_secret_key(), "service-secret")

    def test_session_secret_keeps_dev_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(session_secret_key(), DEV_SESSION_SECRET)

    def test_state_dir_uses_environment_value(self):
        with patch.dict(os.environ, {"SAMWIZARD_STATE_DIR": "/tmp/samwizard-state"}, clear=False):
            self.assertEqual(samwizard_state_dir(), Path("/tmp/samwizard-state"))

    def test_state_dir_keeps_dev_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(samwizard_state_dir(), DEV_STATE_DIR)


if __name__ == "__main__":
    unittest.main()
