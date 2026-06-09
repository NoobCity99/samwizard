import json
import unittest
from importlib.util import find_spec
from unittest.mock import patch

if find_spec("fastapi") is None:
    raise unittest.SkipTest("FastAPI is not installed in this Python environment.")

from app.command_log import add_log_entry, command_log_from_state
from app.main import (
    clear_log,
    drive_selection,
    logs_data,
    logs_page,
    run_apply,
    save_drive_selection,
    save_user_setup,
    system_check_next,
    wifi_preview,
)


class FakeRequest:
    def __init__(self, wizard=None):
        self.session = {"wizard": wizard or {}}
        self.headers = {}

    def url_for(self, name, **path_params):
        if name == "static":
            return f"/static{path_params.get('path', '')}"
        return f"/{name}"


def system_info(internet_connected=True):
    return {
        "hostname": {
            "available": True,
            "value": "fileserver",
            "source": "system hostname",
        },
        "local_ips": {
            "available": True,
            "items": ["192.168.1.50"],
            "source": "hostname -I",
            "message": None,
        },
        "os": {
            "available": True,
            "pretty_name": "Ubuntu 26.04 LTS",
            "version": "26.04 LTS",
            "id": "ubuntu",
            "source": "/etc/os-release",
            "message": None,
        },
        "samba": {
            "available": True,
            "installed": False,
            "status": "not_found",
            "version": None,
            "evidence": [],
            "message": "Samba was not found. Nothing was installed or changed.",
        },
        "drives": {
            "available": True,
            "items": [
                {
                    "label": "Backup Drive",
                    "model": None,
                    "path": "/dev/sdb1",
                    "name": "sdb1",
                    "type": "part",
                    "size": "1.0 TB",
                    "filesystem": "ext4",
                    "uuid": "drive-uuid",
                    "mountpoints": [],
                }
            ],
            "message": None,
        },
        "mounts": {
            "available": True,
            "items": [],
            "message": "No mounted folders were reported by findmnt.",
        },
        "internet": {
            "available": internet_connected,
            "connected": internet_connected,
            "status": "connected" if internet_connected else "not_connected",
            "message": "Internet connection found."
            if internet_connected
            else "No internet connection was found. Connect ethernet first, then check again.",
            "details": ["HTTPS port 443 accepted a connection."]
            if internet_connected
            else ["DNS lookup failed for ubuntu.com: temporary DNS failure"],
            "source": "DNS lookup and HTTPS connection to ubuntu.com:443",
        },
    }


class SystemCheckRouteTests(unittest.TestCase):
    def test_system_check_post_blocks_when_internet_is_missing(self):
        request = FakeRequest()

        with patch("app.main.detect_system_info", return_value=system_info(False)):
            response = system_check_next(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Resolve the critical checks before continuing.", response.body.decode())
        self.assertIn("OK, I connected ethernet", response.body.decode())

    def test_system_check_post_continues_when_internet_is_connected(self):
        request = FakeRequest()

        with patch("app.main.detect_system_info", return_value=system_info(True)):
            response = system_check_next(request)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/drive-selection")

    def test_wifi_preview_validates_missing_fields(self):
        request = FakeRequest()

        with patch("app.main.detect_system_info", return_value=system_info(False)):
            response = wifi_preview(
                request,
                wifi_interface="",
                wifi_ssid="Home WiFi",
                wifi_password="secret-password",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Enter the Wi-Fi adapter name.", response.body.decode())

    def test_wifi_preview_masks_password_and_keeps_raw_password_out_of_session(self):
        request = FakeRequest()
        results = [
            {
                "id": "wifi_root_required",
                "title": "Administrator access needed",
                "status": "failed",
                "summary": "Restart the wizard with sudo before applying Wi-Fi settings.",
                "details": [],
            }
        ]

        with patch("app.main.detect_system_info", return_value=system_info(False)):
            with patch("app.main.apply_wifi_setup", return_value=results):
                response = wifi_preview(
                    request,
                    wifi_interface="wlan0",
                    wifi_ssid="Home WiFi",
                    wifi_password="secret-password",
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Administrator access needed", response.body.decode())
        self.assertNotIn("secret-password", response.body.decode())
        self.assertNotIn("secret-password", repr(request.session))

    def test_wifi_apply_success_logs_commands_and_stores_no_password(self):
        request = FakeRequest()

        def fake_apply(state, **kwargs):
            add_log_entry(
                state,
                phase="Wi-Fi Setup",
                command="netplan apply",
                exit_code=0,
                stdout="ok",
                summary="Command completed.",
            )
            return [
                {
                    "id": "wifi_internet",
                    "title": "Check internet connection",
                    "status": "passed",
                    "summary": "Internet connection found after applying Wi-Fi settings.",
                    "details": [],
                }
            ]

        with patch("app.main.detect_system_info", return_value=system_info(False)):
            with patch("app.main.apply_wifi_setup", side_effect=fake_apply):
                response = wifi_preview(
                    request,
                    wifi_interface="wlan0",
                    wifi_ssid="Home WiFi",
                    wifi_password="secret-password",
                )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/system-check")
        self.assertIn("netplan apply", repr(command_log_from_state(request.session["wizard"])))
        self.assertNotIn("secret-password", repr(request.session))

    def test_command_log_no_longer_appears_on_system_check_bottom(self):
        request = FakeRequest()
        add_log_entry(
            request.session["wizard"],
            phase="System Check",
            command="hostname -I",
            exit_code=0,
            stdout="192.168.1.50",
            summary="Command completed.",
        )

        with patch("app.main.detect_system_info", return_value=system_info(False)):
            response = system_check_next(request)

        body = response.body.decode()
        self.assertIn('href="/logs"', body)
        self.assertNotIn("Behind the scenes log", body)
        self.assertNotIn("Command completed.", body)

    def test_clear_log_preserves_wizard_choices(self):
        request = FakeRequest(
            {
                "share_name": "Backups",
            }
        )
        add_log_entry(request.session["wizard"], phase="System Check", command="hostname -I", exit_code=0)

        response = clear_log(request)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(request.session["wizard"]["share_name"], "Backups")
        self.assertEqual(command_log_from_state(request.session["wizard"]), [])

    def test_old_wifi_preview_route_name_still_accepts_real_apply(self):
        request = FakeRequest()
        results = [
            {
                "id": "wifi_root_required",
                "title": "Administrator access needed",
                "status": "failed",
                "summary": "Restart the wizard with sudo before applying Wi-Fi settings.",
                "details": [],
            }
        ]

        with patch("app.main.detect_system_info", return_value=system_info(False)):
            with patch("app.main.apply_wifi_setup", return_value=results):
                response = wifi_preview(
                    request,
                    wifi_interface="wlan0",
                    wifi_ssid="Home WiFi",
                    wifi_password="secret-password",
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Wi-Fi setup stopped before finishing.", response.body.decode())

    def test_wifi_apply_validates_missing_password(self):
        request = FakeRequest()

        with patch("app.main.detect_system_info", return_value=system_info(False)):
            response = wifi_preview(
                request,
                wifi_interface="wlan0",
                wifi_ssid="Home WiFi",
                wifi_password="",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Enter the Wi-Fi password.", response.body.decode())
        self.assertNotIn("secret-password", repr(request.session))

    def test_user_setup_does_not_store_password(self):
        request = FakeRequest()
        response = save_user_setup(request, username="sambauser")

        self.assertEqual(response.status_code, 303)
        self.assertEqual(request.session["wizard"]["username"], "sambauser")
        self.assertNotIn("password", repr(request.session).lower())

    def test_apply_blocks_when_system_actions_report_root_required(self):
        request = FakeRequest(
            {
                "reviewed": True,
                "selected_location": {
                    "type": "server_folder",
                    "path": "/srv/samba/testshare",
                    "name": "Server folder on this computer",
                },
                "share_name": "Backups",
                "username": "sambauser",
            }
        )
        failed_result = [
            {
                "id": "root_required",
                "title": "Administrator access needed",
                "status": "failed",
                "summary": "Restart the wizard with sudo before applying real system changes.",
                "details": [],
            }
        ]

        with patch("app.main.apply_share_setup", return_value=failed_result):
            response = run_apply(
                request,
                samba_password="secret-password",
                confirm_samba_password="secret-password",
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Administrator access needed", response.body.decode())
        self.assertNotIn("secret-password", response.body.decode())
        self.assertNotIn("secret-password", repr(request.session))

    def test_command_log_no_longer_appears_on_apply_bottom(self):
        request = FakeRequest(
            {
                "reviewed": True,
                "selected_location": {
                    "type": "server_folder",
                    "path": "/srv/samba/testshare",
                    "name": "Server folder on this computer",
                },
                "share_name": "Backups",
                "username": "sambauser",
            }
        )
        add_log_entry(
            request.session["wizard"],
            phase="Apply",
            command="apt-get update",
            exit_code=0,
            stdout="ok",
            summary="Command completed.",
        )
        failed_result = [
            {
                "id": "root_required",
                "title": "Administrator access needed",
                "status": "failed",
                "summary": "Restart the wizard with sudo before applying real system changes.",
                "details": [],
            }
        ]

        with patch("app.main.apply_share_setup", return_value=failed_result):
            response = run_apply(
                request,
                samba_password="secret-password",
                confirm_samba_password="secret-password",
            )

        body = response.body.decode()
        self.assertIn('href="/logs"', body)
        self.assertNotIn("Behind the scenes log", body)
        self.assertNotIn("apt-get update", body)

    def test_apply_success_redirects_to_done(self):
        request = FakeRequest(
            {
                "reviewed": True,
                "selected_location": {
                    "type": "server_folder",
                    "path": "/srv/samba/testshare",
                    "name": "Server folder on this computer",
                },
                "share_name": "Backups",
                "username": "sambauser",
            }
        )
        passed_result = [
            {
                "id": "install_samba",
                "title": "Install Samba",
                "status": "passed",
                "summary": "Windows file sharing support is installed.",
                "details": [],
            }
        ]

        with patch("app.main.apply_share_setup", return_value=passed_result):
            response = run_apply(
                request,
                samba_password="secret-password",
                confirm_samba_password="secret-password",
            )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/done")
        self.assertNotIn("secret-password", repr(request.session))

    def test_drive_selection_accepts_real_eligible_partition(self):
        request = FakeRequest()

        with patch("app.main.detect_system_info", return_value=system_info(True)):
            response = save_drive_selection(request, location_id="drive:drive-uuid")

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/share-name")
        self.assertEqual(request.session["wizard"]["selected_location"]["uuid"], "drive-uuid")

    def test_logs_page_renders_existing_entries(self):
        request = FakeRequest()
        add_log_entry(request.session["wizard"], phase="Apply", command="apt-get update", exit_code=0)

        response = logs_page(request)

        body = response.body.decode()
        self.assertIn("Behind the scenes log", body)
        self.assertIn("apt-get update", body)
        self.assertIn("/logs/data", body)

    def test_logs_data_returns_entries_in_order(self):
        request = FakeRequest()
        add_log_entry(request.session["wizard"], phase="First", command="one", exit_code=0)
        add_log_entry(request.session["wizard"], phase="Second", command="two", exit_code=1)

        response = logs_data(request)
        payload = json.loads(response.body.decode())

        self.assertEqual([entry["command"] for entry in payload["entries"]], ["one", "two"])

    def test_drive_selection_explains_wsl_like_ineligible_drives(self):
        request = FakeRequest()
        info = system_info(True)
        info["drives"]["items"] = [
            {
                "label": "WSL Disk",
                "path": "/dev/sdc",
                "name": "sdc",
                "type": "disk",
                "size": "256.0 GB",
                "filesystem": None,
                "uuid": None,
                "mountpoints": [],
            },
            {
                "label": None,
                "path": "/dev/sdc1",
                "name": "sdc1",
                "type": "part",
                "size": "256.0 GB",
                "filesystem": "ext4",
                "uuid": None,
                "mountpoints": ["/"],
            },
        ]

        with patch("app.main.detect_system_info", return_value=info):
            response = drive_selection(request)

        body = response.body.decode()
        self.assertIn("No share-ready drive partitions were found", body)
        self.assertIn("missing UUID", body)
        self.assertIn("not a partition", body)


if __name__ == "__main__":
    unittest.main()
