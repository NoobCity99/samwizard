import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from build_release import build_bundle


REPO_ROOT = Path(__file__).resolve().parents[1]


class InstallerReleaseTests(unittest.TestCase):
    def test_install_script_has_valid_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(REPO_ROOT / "install.sh")],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_install_script_contains_expected_service_contract(self):
        content = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")

        self.assertIn("/opt/samwizard", content)
        self.assertIn("/etc/samwizard/samwizard.env", content)
        self.assertIn("/etc/systemd/system/samwizard.service", content)
        self.assertIn("SAMWIZARD_SECRET_KEY", content)
        self.assertIn("samwizard-app.tar.gz", content)
        self.assertIn("systemctl enable samwizard", content)
        self.assertIn("ufw", content)

    def test_release_bundle_contains_app_files_and_excludes_local_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "samwizard-app.tar.gz"
            build_bundle(output=output, version="0.6.0")

            with tarfile.open(output, "r:gz") as archive:
                names = set(archive.getnames())

        self.assertIn("app/main.py", names)
        self.assertIn("app/templates/base.html", names)
        self.assertIn("requirements.txt", names)
        self.assertIn("README.md", names)
        self.assertIn("VERSION", names)
        self.assertNotIn("tests/test_installer_release.py", names)
        self.assertFalse(any(name.startswith(".git/") for name in names))
        self.assertFalse(any(".venv" in name for name in names))
        self.assertFalse(any("__pycache__" in name for name in names))


if __name__ == "__main__":
    unittest.main()
