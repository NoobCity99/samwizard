import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from build_release import DEFAULT_VERSION, build_bundle


REPO_ROOT = Path(__file__).resolve().parents[1]
LATEST_BUNDLE_URL = "https://github.com/NoobCity99/samwizard/releases/latest/download/samwizard-app.tar.gz"


class InstallerReleaseTests(unittest.TestCase):
    def test_install_script_has_valid_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(REPO_ROOT / "samwizard.sh")],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_install_script_contains_expected_service_contract(self):
        content = (REPO_ROOT / "samwizard.sh").read_text(encoding="utf-8")

        self.assertIn("/opt/samwizard", content)
        self.assertIn("/etc/samwizard/samwizard.env", content)
        self.assertIn("/var/lib/samwizard", content)
        self.assertIn("/etc/systemd/system/samwizard.service", content)
        self.assertIn("SAMWIZARD_SECRET_KEY", content)
        self.assertIn("SAMWIZARD_STATE_DIR", content)
        self.assertIn("samwizard-app.tar.gz", content)
        self.assertIn(LATEST_BUNDLE_URL, content)
        self.assertNotIn("releases/download/test3/samwizard-app.tar.gz", content)
        self.assertIn("systemctl enable samwizard", content)
        package_line = next(
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith("apt-get install -y curl")
        )
        self.assertIn(" ufw ", f" {package_line} ")
        self.assertIn("ntfs-3g", content)
        self.assertIn("exfatprogs", content)
        self.assertIn("hfsplus", content)
        self.assertIn("hfsprogs", content)

    def test_release_version_defaults_to_next_phase_version(self):
        self.assertEqual(DEFAULT_VERSION, "0.7.0")
        self.assertEqual((REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip(), "0.7.0")

    def test_release_bundle_contains_app_files_and_excludes_local_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "samwizard-app.tar.gz"
            build_bundle(output=output, version="0.7.0")

            with tarfile.open(output, "r:gz") as archive:
                names = set(archive.getnames())

        self.assertIn("app/main.py", names)
        self.assertIn("app/academy/routes.py", names)
        self.assertIn("app/academy/progress.py", names)
        self.assertIn("app/academy/tree.py", names)
        self.assertIn("app/academy/trees/ubuntu_cli_basics.json", names)
        self.assertIn("app/tailscale_manager.py", names)
        self.assertIn("app/firewall_manager.py", names)
        self.assertIn("app/templates/base.html", names)
        self.assertIn("app/templates/academy.html", names)
        self.assertIn("app/templates/landing.html", names)
        self.assertIn("app/static/assets/academy/.gitkeep", names)
        self.assertIn("app/static/assets/academy/icons/.gitkeep", names)
        self.assertIn("app/templates/tailscale_done.html", names)
        self.assertIn("app/templates/tailscale_firewall.html", names)
        self.assertIn("requirements.txt", names)
        self.assertIn("README.md", names)
        self.assertIn("VERSION", names)
        self.assertNotIn("tests/test_installer_release.py", names)
        self.assertFalse(any(name.startswith(".git/") for name in names))
        self.assertFalse(any(".venv" in name for name in names))
        self.assertFalse(any("__pycache__" in name for name in names))


if __name__ == "__main__":
    unittest.main()
