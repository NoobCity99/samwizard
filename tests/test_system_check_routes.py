import json
import time
import unittest
from importlib.util import find_spec
from unittest.mock import patch

if find_spec("fastapi") is None:
    raise unittest.SkipTest("FastAPI is not installed in this Python environment.")

from app.command_log import add_log_entry, command_log_from_state
from app.main import (
    apply_progress,
    apply_status,
    apply_setup,
    clear_log,
    done,
    drive_selection,
    logs_data,
    logs_page,
    review,
    run_apply,
    samba_system,
    save_drive_selection,
    save_share_name,
    save_user_setup,
    system_check_next,
    user_setup,
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


def selected_drive_state(**extra):
    state = {
        "type": "drive",
        "path": "/dev/sdb1",
        "uuid": "drive-uuid",
        "filesystem": "ext4",
        "mount_path": "/srv/samba/drives/Backup-Drive",
        "name": "Backup Drive",
        "mount_access": "read_write",
    }
    state.update(extra)
    return state


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


def samba_info(*, users=None):
    info = system_info(True)
    users = users or []
    if users:
        setup_mode = "add_drive" if len(users) == 1 else "unsupported_existing_samba"
        setup_message = (
            f"Samba is installed with one existing user, {users[0]['name']}."
            if len(users) == 1
            else "Samba is installed with multiple users."
        )
    else:
        setup_mode = "initial_setup"
        setup_message = "Samba appears to be installed, but no Samba users were found."
    info["samba"] = {
        "available": True,
        "installed": True,
        "status": "found",
        "version": "Version 4.21.0-Ubuntu",
        "evidence": ["smbd responded: Version 4.21.0-Ubuntu"],
        "message": setup_message,
        "users": users,
        "user_count": len(users),
        "shares": [{"name": "Backups", "path": "/srv/samba/drives/Backups"}],
        "active_sessions": [],
        "service_status": "active",
        "setup_mode": setup_mode,
        "setup_message": setup_message,
    }
    return info


def wait_for_apply_status(request, expected_status=None):
    payload = {}
    for _index in range(50):
        response = apply_status(request)
        payload = json.loads(response.body.decode())
        if payload.get("status") not in {"pending", "running"}:
            break
        time.sleep(0.01)
    if expected_status:
        assert payload.get("status") == expected_status, payload
    return payload


class SystemCheckRouteTests(unittest.TestCase):
    def test_system_check_post_blocks_when_internet_is_missing(self):
        request = FakeRequest()

        with patch("app.main.detect_system_info", return_value=system_info(False)):
            response = system_check_next(request)

        self.assertEqual(response.status_code, 200)
        body = response.body.decode()
        self.assertIn("Resolve the critical checks before continuing.", body)
        self.assertIn("OK, I connected ethernet", body)
        self.assertIn("Use a real Ubuntu Server system for full setup testing.", body)
        self.assertNotIn("safe for this milestone", body)

    def test_system_check_post_continues_when_internet_is_connected(self):
        request = FakeRequest()

        with patch("app.main.detect_system_info", return_value=system_info(True)):
            response = system_check_next(request)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/drive-selection")
        self.assertEqual(request.session["wizard"]["samba_setup_mode"], "initial_setup")

    def test_system_check_post_uses_single_existing_samba_user_for_add_drive_mode(self):
        request = FakeRequest()

        with patch("app.main.detect_system_info", return_value=samba_info(users=[{"name": "sambauser"}])):
            response = system_check_next(request)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/drive-selection")
        self.assertEqual(request.session["wizard"]["samba_setup_mode"], "add_drive")
        self.assertEqual(request.session["wizard"]["username"], "sambauser")
        self.assertEqual(request.session["wizard"]["existing_samba_user"], "sambauser")

    def test_system_check_post_stops_when_multiple_samba_users_exist(self):
        request = FakeRequest()

        with patch(
            "app.main.detect_system_info",
            return_value=samba_info(users=[{"name": "sambauser"}, {"name": "otheruser"}]),
        ):
            response = system_check_next(request)

        self.assertEqual(response.status_code, 200)
        body = response.body.decode()
        self.assertIn("multiple users", body)
        self.assertIn('href="/samba-system"', body)
        self.assertEqual(request.session["wizard"]["samba_setup_mode"], "unsupported_existing_samba")

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

    def test_add_drive_flow_skips_user_setup_after_share_name(self):
        request = FakeRequest(
            {
                "samba_setup_mode": "add_drive",
                "username": "sambauser",
                "selected_location": selected_drive_state(),
            }
        )

        response = save_share_name(request, share_name="Media")

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/review")

        response = user_setup(request)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/review")

    def test_apply_blocks_when_system_actions_report_root_required(self):
        request = FakeRequest(
            {
                "reviewed": True,
                "selected_location": selected_drive_state(),
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
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers["location"], "/apply/progress")
            wait_for_apply_status(request, "failed")

        response = apply_setup(request)
        self.assertEqual(response.status_code, 200)
        body = response.body.decode()
        self.assertIn("Administrator access needed", body)
        self.assertNotIn("installer milestone", body)
        self.assertNotIn("Real setup requires", body)
        self.assertNotIn("secret-password", response.body.decode())
        self.assertNotIn("secret-password", repr(request.session))

    def test_command_log_no_longer_appears_on_apply_bottom(self):
        request = FakeRequest(
            {
                "reviewed": True,
                "selected_location": selected_drive_state(),
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
            self.assertEqual(response.status_code, 303)
            wait_for_apply_status(request, "failed")

        response = apply_setup(request)
        body = response.body.decode()
        self.assertIn('href="/logs"', body)
        self.assertNotIn("Behind the scenes log", body)
        self.assertNotIn("apt-get update", body)
        self.assertNotIn("installer milestone", body)

    def test_apply_post_starts_job_and_progress_redirects_to_done(self):
        request = FakeRequest(
            {
                "reviewed": True,
                "selected_location": selected_drive_state(),
                "share_name": "Backups",
                "username": "sambauser",
                "system_summary": {
                    "hostname": "fileserver",
                    "ip_address": "192.168.1.50",
                    "ubuntu_version": "Ubuntu 26.04 LTS",
                },
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
            self.assertEqual(response.headers["location"], "/apply/progress")
            self.assertIn("apply_job_id", request.session["wizard"])
            self.assertNotIn("secret-password", repr(request.session))

            progress = apply_progress(request)
            self.assertEqual(progress.status_code, 200)
            self.assertIn("Apply is running", progress.body.decode())

            status = wait_for_apply_status(request, "succeeded")

        self.assertEqual(status["redirect"], "/done")
        done_response = done(request)
        self.assertEqual(done_response.status_code, 200)
        body = done_response.body.decode()
        self.assertIn("\\\\192.168.1.50\\Backups", body)
        self.assertIn('aria-label="Copy Windows path"', body)
        self.assertIn("navigator.clipboard.writeText", body)
        self.assertIn("SamWizard", body)

    def test_add_drive_apply_accepts_no_password(self):
        request = FakeRequest(
            {
                "samba_setup_mode": "add_drive",
                "reviewed": True,
                "selected_location": selected_drive_state(),
                "share_name": "Backups",
                "username": "sambauser",
            }
        )
        passed_result = [
            {
                "id": "verify_samba",
                "title": "Check existing Samba",
                "status": "passed",
                "summary": "Existing Samba installation is ready.",
                "details": [],
            }
        ]

        with patch("app.main.apply_share_setup", return_value=passed_result) as apply_mock:
            response = run_apply(request)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers["location"], "/apply/progress")
            wait_for_apply_status(request, "succeeded")

        kwargs = apply_mock.call_args.kwargs
        self.assertIsNone(kwargs["password"])
        self.assertFalse(kwargs["create_user"])

    def test_add_drive_apply_page_hides_password_fields(self):
        request = FakeRequest(
            {
                "samba_setup_mode": "add_drive",
                "reviewed": True,
                "selected_location": selected_drive_state(),
                "share_name": "Backups",
                "username": "sambauser",
            }
        )

        response = apply_setup(request)

        body = response.body.decode()
        self.assertIn("Add this drive", body)
        self.assertNotIn("Windows share password", body)

    def test_apply_status_reports_running_and_latest_command(self):
        request = FakeRequest({"apply_job_id": "job-1"})
        add_log_entry(
            request.session["wizard"],
            phase="Apply",
            command=["mount", "/srv/samba/drives/Backup"],
            exit_code=None,
            summary="Starting command...",
        )
        running_job = {
            "id": "job-1",
            "status": "running",
            "results": [],
            "error": None,
            "selected_location": {},
            "updated_at": "2026-06-10T12:00:00+00:00",
        }

        with patch("app.main.get_apply_job", return_value=running_job):
            response = apply_status(request)

        payload = json.loads(response.body.decode())
        self.assertEqual(payload["status"], "running")
        self.assertIn("mount /srv/samba/drives/Backup", payload["latest_entry"]["command"])
        self.assertEqual(payload["latest_entry"]["summary"], "Starting command...")

    def test_done_uses_cached_system_summary_without_full_detection(self):
        request = FakeRequest(
            {
                "applied": True,
                "share_name": "Backups",
                "username": "sambauser",
                "system_summary": {
                    "hostname": "fileserver",
                    "ip_address": "192.168.1.50",
                    "ubuntu_version": "Ubuntu 26.04 LTS",
                },
            }
        )

        with patch("app.main.detect_system_info", side_effect=AssertionError("should not run")):
            response = done(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("\\\\192.168.1.50\\Backups", response.body.decode())

    def test_done_reconciles_completed_apply_job_when_session_not_marked_applied(self):
        request = FakeRequest(
            {
                "reviewed": True,
                "apply_job_id": "job-1",
                "applied": False,
                "share_name": "Backups",
                "username": "sambauser",
                "system_summary": {
                    "hostname": "fileserver",
                    "ip_address": "192.168.1.50",
                    "ubuntu_version": "Ubuntu 26.04 LTS",
                },
            }
        )
        completed_job = {
            "id": "job-1",
            "status": "succeeded",
            "results": [
                {
                    "id": "restart_samba",
                    "title": "Restart Windows file sharing",
                    "status": "passed",
                    "summary": "Windows file sharing restarted.",
                    "details": [],
                }
            ],
            "error": None,
            "selected_location": selected_drive_state(),
            "updated_at": "2026-06-10T12:00:00+00:00",
        }

        with patch("app.main.get_apply_job", return_value=completed_job):
            response = done(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(request.session["wizard"]["applied"])
        self.assertEqual(request.session["wizard"]["apply_status"], "succeeded")
        self.assertIn("\\\\192.168.1.50\\Backups", response.body.decode())

    def test_apply_page_redirects_to_done_when_job_finished_after_polling(self):
        request = FakeRequest(
            {
                "reviewed": True,
                "apply_job_id": "job-1",
                "applied": False,
                "selected_location": selected_drive_state(),
                "share_name": "Backups",
                "username": "sambauser",
            }
        )
        completed_job = {
            "id": "job-1",
            "status": "succeeded",
            "results": [],
            "error": None,
            "selected_location": selected_drive_state(),
            "updated_at": "2026-06-10T12:00:00+00:00",
        }

        with patch("app.main.get_apply_job", return_value=completed_job):
            response = apply_setup(request)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/done")

    def test_apply_exception_becomes_failed_status(self):
        request = FakeRequest(
            {
                "reviewed": True,
                "selected_location": selected_drive_state(),
                "share_name": "Backups",
                "username": "sambauser",
            }
        )

        with patch("app.main.apply_share_setup", side_effect=RuntimeError("boom")):
            response = run_apply(
                request,
                samba_password="secret-password",
                confirm_samba_password="secret-password",
            )
            self.assertEqual(response.status_code, 303)
            status = wait_for_apply_status(request, "failed")

        self.assertEqual(status["failure_url"], "/apply")
        self.assertIn("unexpected error", repr(status["results"]))
        self.assertNotIn("secret-password", repr(request.session))

    def test_stale_server_folder_session_redirects_to_drive_selection(self):
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

        response = run_apply(
            request,
            samba_password="secret-password",
            confirm_samba_password="secret-password",
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/drive-selection")

    def test_drive_selection_accepts_real_eligible_partition(self):
        request = FakeRequest()

        with patch("app.main.detect_system_info", return_value=system_info(True)):
            response = save_drive_selection(request, location_id="drive:drive-uuid")

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/share-name")
        self.assertEqual(request.session["wizard"]["selected_location"]["uuid"], "drive-uuid")
        self.assertEqual(request.session["wizard"]["mount_access"], "read_write")
        self.assertEqual(request.session["wizard"]["selected_location"]["mount_access"], "read_write")

    def test_drive_selection_saves_read_only_access_for_drive(self):
        request = FakeRequest()

        with patch("app.main.detect_system_info", return_value=system_info(True)):
            response = save_drive_selection(
                request,
                location_id="drive:drive-uuid",
                mount_access="read_only",
            )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(request.session["wizard"]["mount_access"], "read_only")
        self.assertEqual(request.session["wizard"]["selected_location"]["mount_access"], "read_only")

    def test_drive_selection_blocks_read_write_hfs_drive(self):
        request = FakeRequest()
        info = system_info(True)
        info["drives"]["items"][0]["filesystem"] = "hfsplus"

        with patch("app.main.detect_system_info", return_value=info):
            response = save_drive_selection(
                request,
                location_id="drive:drive-uuid",
                mount_access="read_write",
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Mac HFS drives can only be shared read-only", response.body.decode())

    def test_review_displays_drive_access(self):
        request = FakeRequest(
            {
                "selected_location": {
                    "type": "drive",
                    "name": "Backup Drive",
                    "mount_path": "/srv/samba/drives/Backup-Drive",
                    "mount_access": "read_only",
                },
                "share_name": "Backups",
                "username": "sambauser",
            }
        )

        response = review(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Drive access", response.body.decode())
        self.assertIn("Read-only", response.body.decode())

    def test_review_displays_existing_samba_password_message(self):
        request = FakeRequest(
            {
                "samba_setup_mode": "add_drive",
                "selected_location": selected_drive_state(),
                "share_name": "Backups",
                "username": "sambauser",
            }
        )

        response = review(request)

        body = response.body.decode()
        self.assertIn("Existing Samba password stays unchanged", body)
        self.assertIn('href="/share-name"', body)

    def test_samba_system_page_shows_plain_summary(self):
        request = FakeRequest()

        with patch("app.main.detect_system_info", return_value=samba_info(users=[{"name": "sambauser"}])):
            response = samba_system(request)

        body = response.body.decode()
        self.assertIn("Your Samba system", body)
        self.assertIn("sambauser", body)
        self.assertIn("Backups", body)
        self.assertNotIn("pdbedit -L", body)

    def test_logs_page_renders_existing_entries(self):
        request = FakeRequest()
        add_log_entry(request.session["wizard"], phase="Apply", command="apt-get update", exit_code=0)

        response = logs_page(request)

        body = response.body.decode()
        self.assertIn("Behind the scenes log", body)
        self.assertIn("Behind the scenes log - SamWizard", body)
        self.assertIn('<p class="eyebrow">SamWizard</p>', body)
        self.assertNotIn("Samba Wizard", body)
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
        self.assertIn("No share-ready external or additional drive was found", body)
        self.assertNotIn("Server folder on this computer", body)
        self.assertNotIn("Continue</button>", body)
        self.assertIn("missing UUID", body)
        self.assertIn("not a partition", body)
        self.assertIn("part of the server OS drive", body)


if __name__ == "__main__":
    unittest.main()
