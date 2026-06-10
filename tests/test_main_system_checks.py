import unittest

from app.system_checks import system_checks_from_info, system_summary


def sample_info():
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
                    "label": "rootfs",
                    "model": None,
                    "path": "/dev/sda1",
                    "name": "sda1",
                    "type": "part",
                    "size": "512.0 MB",
                    "mountpoints": ["/"],
                }
            ],
            "message": None,
        },
        "mounts": {
            "available": True,
            "items": [
                {
                    "target": "/",
                    "source": "/dev/sda1",
                    "fstype": "ext4",
                }
            ],
            "message": None,
        },
        "internet": {
            "available": True,
            "connected": True,
            "status": "connected",
            "message": "Internet connection found.",
            "details": ["DNS lookup found 1 address candidate(s) for ubuntu.com."],
            "source": "DNS lookup and HTTPS connection to ubuntu.com:443",
        },
    }


class MainSystemCheckTests(unittest.TestCase):
    def test_system_checks_include_real_detection_cards(self):
        checks = system_checks_from_info(sample_info())
        check_ids = {check["id"] for check in checks}

        self.assertEqual(
            check_ids,
            {
                "hostname",
                "local_ips",
                "os_version",
                "internet_connectivity",
                "samba_installed",
                "drives",
                "mounts",
            },
        )

    def test_samba_not_found_is_not_a_blocking_critical_check(self):
        checks = system_checks_from_info(sample_info())
        samba_check = next(check for check in checks if check["id"] == "samba_installed")

        self.assertEqual(samba_check["status"], "needs_attention")
        self.assertEqual(samba_check["status_label"], "Not found")
        self.assertFalse(samba_check["critical"])
        self.assertEqual(samba_check["actions"], [])

    def test_samba_installed_card_links_to_system_summary(self):
        info = sample_info()
        info["samba"] = {
            "available": True,
            "installed": True,
            "status": "found",
            "version": "Version 4.21.0-Ubuntu",
            "evidence": ["smbd responded: Version 4.21.0-Ubuntu"],
            "message": "Samba appears to be installed.",
            "users": [{"name": "sambauser"}],
            "user_count": 1,
            "shares": [{"name": "Backups", "path": "/srv/samba/drives/Backups"}],
            "active_sessions": [],
            "service_status": "active",
            "setup_mode": "add_drive",
            "setup_message": "Samba is installed with one existing user.",
        }

        checks = system_checks_from_info(info)
        samba_check = next(check for check in checks if check["id"] == "samba_installed")

        self.assertEqual(samba_check["actions"][0]["href"], "/samba-system")
        self.assertIn("Configured Samba users: 1.", samba_check["details"])

    def test_internet_connected_is_not_blocking(self):
        checks = system_checks_from_info(sample_info())
        internet_check = next(check for check in checks if check["id"] == "internet_connectivity")

        self.assertEqual(internet_check["status"], "passed")
        self.assertEqual(internet_check["status_label"], "Connected")
        self.assertFalse(internet_check["critical"])

    def test_internet_missing_is_blocking(self):
        info = sample_info()
        info["internet"] = {
            "available": False,
            "connected": False,
            "status": "not_connected",
            "message": "No internet connection was found. Connect ethernet first, then check again.",
            "details": ["DNS lookup failed for ubuntu.com: temporary DNS failure"],
            "source": "DNS lookup and HTTPS connection to ubuntu.com:443",
        }

        checks = system_checks_from_info(info)
        internet_check = next(check for check in checks if check["id"] == "internet_connectivity")

        self.assertEqual(internet_check["status"], "needs_attention")
        self.assertEqual(internet_check["status_label"], "Needs attention")
        self.assertTrue(internet_check["critical"])

    def test_system_summary_uses_first_detected_ip(self):
        summary = system_summary(sample_info())

        self.assertEqual(summary["hostname"], "fileserver")
        self.assertEqual(summary["ip_address"], "192.168.1.50")
        self.assertEqual(summary["ubuntu_version"], "Ubuntu 26.04 LTS")


if __name__ == "__main__":
    unittest.main()
