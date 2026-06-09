import tempfile
import unittest
from pathlib import Path

from app.command_log import command_log_from_state
from app.system_actions import CommandResult
from app.wifi_actions import apply_wifi_setup, netplan_wifi_yaml


class FakeRunner:
    def __init__(self, failures=None):
        self.calls = []
        self.failures = failures or {}

    def __call__(self, args, input_text=None, env=None):
        self.calls.append((args, input_text, env))
        failure = self.failures.get(tuple(args))
        if failure:
            return failure
        return CommandResult(args=args, returncode=0, stdout="ok")


def connected_internet():
    return {
        "connected": True,
        "message": "Internet connection found.",
        "details": ["HTTPS port 443 accepted a connection."],
    }


def missing_internet():
    return {
        "connected": False,
        "message": "No internet connection was found.",
        "details": ["DNS failed."],
    }


class WifiActionTests(unittest.TestCase):
    def test_netplan_yaml_contains_real_password_for_file_content(self):
        content = netplan_wifi_yaml("wlan0", "Home WiFi", "secret-password")

        self.assertIn('password: "secret-password"', content)
        self.assertIn('"Home WiFi"', content)

    def test_apply_wifi_setup_blocks_when_not_root(self):
        results = apply_wifi_setup(
            {},
            interface="wlan0",
            ssid="Home WiFi",
            password="secret-password",
            root_checker=lambda: False,
        )

        self.assertEqual(results[0]["id"], "wifi_root_required")
        self.assertEqual(results[0]["status"], "failed")

    def test_apply_wifi_setup_success_masks_password_in_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            state = {}
            netplan_path = Path(directory) / "99-samba-wizard-wifi.yaml"
            runner = FakeRunner()

            results = apply_wifi_setup(
                state,
                interface="wlan0",
                ssid="Home WiFi",
                password="secret-password",
                command_runner=runner,
                root_checker=lambda: True,
                netplan_path=netplan_path,
                internet_checker=connected_internet,
            )

            written = netplan_path.read_text(encoding="utf-8")

        self.assertTrue(all(result["status"] == "passed" for result in results))
        self.assertIn('password: "secret-password"', written)
        self.assertIn(["netplan", "generate"], [call[0] for call in runner.calls])
        self.assertIn(["netplan", "apply"], [call[0] for call in runner.calls])
        self.assertNotIn("secret-password", repr(command_log_from_state(state)))
        self.assertIn("********", repr(command_log_from_state(state)))

    def test_apply_wifi_setup_stops_on_netplan_generate_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            state = {}
            runner = FakeRunner(
                failures={
                    ("netplan", "generate"): CommandResult(
                        args=["netplan", "generate"],
                        returncode=1,
                        stderr="bad yaml",
                    )
                }
            )
            results = apply_wifi_setup(
                state,
                interface="wlan0",
                ssid="Home WiFi",
                password="secret-password",
                command_runner=runner,
                root_checker=lambda: True,
                netplan_path=Path(directory) / "wifi.yaml",
                internet_checker=connected_internet,
            )

        self.assertEqual(results[-1]["id"], "generate")
        self.assertEqual(results[-1]["status"], "failed")
        self.assertNotIn(["netplan", "apply"], [call[0] for call in runner.calls])

    def test_apply_wifi_setup_reports_post_apply_internet_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            results = apply_wifi_setup(
                {},
                interface="wlan0",
                ssid="Home WiFi",
                password="secret-password",
                command_runner=FakeRunner(),
                root_checker=lambda: True,
                netplan_path=Path(directory) / "wifi.yaml",
                internet_checker=missing_internet,
            )

        self.assertEqual(results[-1]["id"], "wifi_internet")
        self.assertEqual(results[-1]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
