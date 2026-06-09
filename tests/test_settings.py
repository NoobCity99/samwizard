import os
import unittest
from unittest.mock import patch

from app.settings import DEV_SESSION_SECRET, session_secret_key


class SettingsTests(unittest.TestCase):
    def test_session_secret_uses_environment_value(self):
        with patch.dict(os.environ, {"SAMWIZARD_SECRET_KEY": "service-secret"}, clear=False):
            self.assertEqual(session_secret_key(), "service-secret")

    def test_session_secret_keeps_dev_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(session_secret_key(), DEV_SESSION_SECRET)


if __name__ == "__main__":
    unittest.main()
