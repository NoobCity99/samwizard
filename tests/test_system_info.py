import tempfile
import unittest
from pathlib import Path

from app.system_info import (
    CommandResult,
    detect_drives,
    detect_internet_connectivity,
    detect_local_ips,
    detect_mounts,
    detect_os_release,
    detect_samba,
    detect_system_info,
    parse_os_release,
    parse_proc_mounts,
)


def runner_for(outputs):
    def run(args):
        value = outputs.get(tuple(args))
        if value is None:
            return None
        return CommandResult(args=args, returncode=value[0], stdout=value[1], stderr=value[2])

    return run


class SystemInfoTests(unittest.TestCase):
    def test_detect_internet_connectivity_succeeds_with_dns_and_https(self):
        class FakeConnection:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        connection = FakeConnection()

        def resolver(host, port, family, socktype, proto):
            return [(family, socktype, proto, "", ("93.184.216.34", port))]

        def connector(sockaddr, timeout):
            self.assertEqual(sockaddr, ("93.184.216.34", 443))
            self.assertEqual(timeout, 3.0)
            return connection

        result = detect_internet_connectivity(
            dns_resolver=resolver,
            socket_connector=connector,
        )

        self.assertTrue(result["available"])
        self.assertTrue(result["connected"])
        self.assertEqual(result["status"], "connected")
        self.assertTrue(connection.closed)

    def test_detect_internet_connectivity_reports_dns_failure(self):
        def resolver(host, port, family, socktype, proto):
            raise OSError("temporary DNS failure")

        result = detect_internet_connectivity(dns_resolver=resolver)

        self.assertFalse(result["available"])
        self.assertFalse(result["connected"])
        self.assertEqual(result["status"], "not_connected")
        self.assertIn("DNS lookup failed", result["details"][0])

    def test_detect_internet_connectivity_reports_tcp_failure(self):
        def resolver(host, port, family, socktype, proto):
            return [(family, socktype, proto, "", ("93.184.216.34", port))]

        def connector(sockaddr, timeout):
            raise TimeoutError("timed out")

        result = detect_internet_connectivity(
            dns_resolver=resolver,
            socket_connector=connector,
        )

        self.assertFalse(result["available"])
        self.assertFalse(result["connected"])
        self.assertIn("HTTPS connection failed", result["details"][-1])

    def test_detect_internet_connectivity_handles_unexpected_socket_error(self):
        def resolver(host, port, family, socktype, proto):
            return [(family, socktype, proto, "", ("93.184.216.34", port))]

        def connector(sockaddr, timeout):
            raise RuntimeError("socket layer broke")

        result = detect_internet_connectivity(
            dns_resolver=resolver,
            socket_connector=connector,
        )

        self.assertFalse(result["available"])
        self.assertFalse(result["connected"])
        self.assertEqual(result["status"], "not_connected")

    def test_parse_os_release_handles_quoted_values(self):
        parsed = parse_os_release(
            '''
            NAME="Ubuntu"
            VERSION="26.04 LTS"
            ID=ubuntu
            PRETTY_NAME="Ubuntu 26.04 LTS"
            '''
        )

        self.assertEqual(parsed["NAME"], "Ubuntu")
        self.assertEqual(parsed["VERSION"], "26.04 LTS")
        self.assertEqual(parsed["ID"], "ubuntu")
        self.assertEqual(parsed["PRETTY_NAME"], "Ubuntu 26.04 LTS")

    def test_detect_os_release_returns_unavailable_when_file_missing(self):
        result = detect_os_release("/tmp/samba-wizard-missing-os-release")

        self.assertFalse(result["available"])
        self.assertEqual(result["pretty_name"], None)

    def test_detect_local_ips_uses_hostname_output_and_filters_loopback(self):
        result = detect_local_ips(
            runner_for(
                {
                    ("hostname", "-I"): (
                        0,
                        "127.0.0.1 172.25.90.10 192.168.1.20 fe80::1\n",
                        "",
                    )
                }
            )
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["items"], ["172.25.90.10", "192.168.1.20"])

    def test_detect_samba_uses_version_command(self):
        result = detect_samba(
            runner_for({("smbd", "--version"): (0, "Version 4.21.0-Ubuntu\n", "")})
        )

        self.assertTrue(result["installed"])
        self.assertEqual(result["version"], "Version 4.21.0-Ubuntu")

    def test_detect_samba_uses_dpkg_fallback(self):
        result = detect_samba(
            runner_for(
                {
                    (
                        "dpkg-query",
                        "-W",
                        "-f=${binary:Package}\t${Version}\t${Status}\n",
                        "samba",
                        "smbd",
                        "samba-common-bin",
                    ): (
                        0,
                        "samba\t2:4.21.0+dfsg-1ubuntu1\tinstall ok installed\n",
                        "",
                    )
                }
            )
        )

        self.assertTrue(result["installed"])
        self.assertEqual(result["version"], "2:4.21.0+dfsg-1ubuntu1")

    def test_detect_samba_reports_not_found_without_changes(self):
        result = detect_samba(runner_for({}))

        self.assertTrue(result["available"])
        self.assertFalse(result["installed"])
        self.assertIn("Nothing was installed or changed", result["message"])

    def test_detect_drives_parses_lsblk_json(self):
        lsblk_json = """
        {
          "blockdevices": [
            {
              "name": "sda",
              "path": "/dev/sda",
              "type": "disk",
              "size": 1073741824,
              "fstype": null,
              "mountpoints": null,
              "label": null,
              "model": "Virtual Disk",
              "children": [
                {
                  "name": "sda1",
                  "path": "/dev/sda1",
                  "type": "part",
                  "size": 536870912,
                  "fstype": "ext4",
                  "mountpoints": ["/"],
                  "label": "rootfs",
                  "model": null
                }
              ]
            }
          ]
        }
        """
        result = detect_drives(
            runner_for(
                {
                    (
                        "lsblk",
                        "--json",
                        "--bytes",
                        "--output",
                        "NAME,KNAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINTS,LABEL,MODEL,UUID",
                    ): (0, lsblk_json, "")
                }
            )
        )

        self.assertTrue(result["available"])
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["size"], "1.0 GB")
        self.assertEqual(result["items"][1]["mountpoints"], ["/"])

    def test_detect_mounts_parses_findmnt_json(self):
        findmnt_json = """
        {
          "filesystems": [
            {
              "target": "/",
              "source": "/dev/sda1",
              "fstype": "ext4",
              "options": "rw,relatime",
              "children": [
                {
                  "target": "/mnt/backups",
                  "source": "/dev/sdb1",
                  "fstype": "ext4",
                  "options": "rw"
                }
              ]
            }
          ]
        }
        """
        result = detect_mounts(
            runner_for(
                {
                    (
                        "findmnt",
                        "--json",
                        "--output",
                        "TARGET,SOURCE,FSTYPE,OPTIONS",
                    ): (0, findmnt_json, "")
                }
            )
        )

        self.assertTrue(result["available"])
        self.assertEqual([item["target"] for item in result["items"]], ["/", "/mnt/backups"])

    def test_parse_proc_mounts_decodes_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mounts"
            path.write_text(
                "/dev/sdb1 /mnt/My\\040Drive ext4 rw,relatime 0 0\n",
                encoding="utf-8",
            )

            result = parse_proc_mounts(path)

        self.assertEqual(result[0]["target"], "/mnt/My Drive")
        self.assertEqual(result[0]["source"], "/dev/sdb1")

    def test_detect_mounts_falls_back_to_proc_mounts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mounts"
            path.write_text("/dev/sda1 / ext4 rw 0 0\n", encoding="utf-8")

            result = detect_mounts(runner_for({}), path)

        self.assertTrue(result["available"])
        self.assertEqual(result["source"], str(path))

    def test_detect_system_info_is_safe_when_linux_tools_are_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_os_release = Path(directory) / "os-release"
            missing_mounts = Path(directory) / "mounts"

            result = detect_system_info(
                command_runner=runner_for({}),
                os_release_path=missing_os_release,
                proc_mounts_path=missing_mounts,
                internet_detector=lambda: {
                    "available": False,
                    "connected": False,
                    "status": "not_connected",
                    "message": "No internet connection was found.",
                    "details": [],
                    "source": "test",
                },
            )

        self.assertIn("hostname", result)
        self.assertFalse(result["os"]["available"])
        self.assertFalse(result["drives"]["available"])
        self.assertFalse(result["mounts"]["available"])
        self.assertIn("internet", result)


if __name__ == "__main__":
    unittest.main()
