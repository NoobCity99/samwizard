import tempfile
import unittest
from pathlib import Path

from app.system_actions import CommandResult
from app.tailscale_manager import (
    detect_tailscale,
    extract_login_url,
    install_tailscale,
    parse_tailscale_status,
    start_tailscale_login,
    tailscale_ipv4,
    ubuntu_codename,
)


class FakeRunner:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def __call__(self, args, input_text=None, env=None):
        self.calls.append(list(args))
        response = self.responses.get(tuple(args))
        if response is None:
            return CommandResult(list(args), 0, "", "")
        return CommandResult(list(args), *response)


class TailscaleManagerTests(unittest.TestCase):
    def test_detect_tailscale_reports_not_installed(self):
        runner = FakeRunner({("tailscale", "version"): (1, "", "not found")})

        result = detect_tailscale(runner)

        self.assertFalse(result["installed"])
        self.assertFalse(result["connected"])
        self.assertEqual(result["message"], "Tailscale is not installed yet.")

    def test_detect_tailscale_reports_connected_ipv4(self):
        runner = FakeRunner(
            {
                ("tailscale", "version"): (0, "1.90.0\n", ""),
                ("systemctl", "is-active", "tailscaled"): (0, "active\n", ""),
                ("tailscale", "status", "--json"): (0, '{"BackendState":"Running","TailscaleIPs":["100.64.0.10"]}', ""),
                ("tailscale", "ip", "-4"): (0, "100.64.0.10\n", ""),
            }
        )

        result = detect_tailscale(runner)

        self.assertTrue(result["installed"])
        self.assertTrue(result["connected"])
        self.assertEqual(result["ipv4"], "100.64.0.10")

    def test_parse_tailscale_status_handles_invalid_json(self):
        result = parse_tailscale_status("not-json")

        self.assertFalse(result["logged_in"])
        self.assertEqual(result["backend_state"], "Unreadable")

    def test_tailscale_ipv4_ignores_invalid_output(self):
        runner = FakeRunner({("tailscale", "ip", "-4"): (0, "not-an-ip\n100.64.0.11\n", "")})

        self.assertEqual(tailscale_ipv4(runner), "100.64.0.11")

    def test_extract_login_url_from_tailscale_up_output(self):
        output = "To authenticate, visit:\n\n\thttps://login.tailscale.com/a/abc123\n"

        self.assertEqual(extract_login_url(output), "https://login.tailscale.com/a/abc123")

    def test_start_tailscale_login_returns_auth_url_even_with_nonzero_exit(self):
        runner = FakeRunner(
            {
                ("tailscale", "up", "--accept-dns=false", "--timeout=10s"): (
                    1,
                    "Open https://login.tailscale.com/a/abc123\n",
                    "waiting for auth",
                )
            }
        )

        result = start_tailscale_login(runner, root_checker=lambda: True)

        self.assertEqual(result["login_url"], "https://login.tailscale.com/a/abc123")
        self.assertEqual(result["result"]["status"], "passed")

    def test_ubuntu_codename_reads_os_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "os-release"
            path.write_text('NAME="Ubuntu"\nVERSION_CODENAME=noble\n', encoding="utf-8")

            self.assertEqual(ubuntu_codename(path), "noble")

    def test_install_tailscale_uses_explicit_apt_repo_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            os_release = Path(directory) / "os-release"
            os_release.write_text("VERSION_CODENAME=noble\n", encoding="utf-8")
            runner = FakeRunner()

            results = install_tailscale(
                runner,
                root_checker=lambda: True,
                os_release_path=os_release,
                keyring_path=Path(directory) / "tailscale-archive-keyring.gpg",
                list_path=Path(directory) / "tailscale.list",
            )

        self.assertTrue(all(result["status"] == "passed" for result in results))
        self.assertIn(
            [
                "curl",
                "-fsSL",
                "https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg",
                "-o",
                str(Path(directory) / "tailscale-archive-keyring.gpg"),
            ],
            runner.calls,
        )
        self.assertIn(["apt-get", "install", "-y", "tailscale"], runner.calls)
        self.assertIn(["systemctl", "enable", "--now", "tailscaled"], runner.calls)


if __name__ == "__main__":
    unittest.main()
