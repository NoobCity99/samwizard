import unittest

from app.share_targets import (
    drive_diagnostics,
    has_eligible_drive,
    safe_name,
    share_locations,
)


class ShareTargetTests(unittest.TestCase):
    def test_safe_name_limits_to_simple_path_characters(self):
        self.assertEqual(safe_name("Family Photos!"), "Family-Photos")
        self.assertEqual(safe_name(""), "share")

    def test_share_locations_include_only_eligible_non_os_partitions(self):
        system_info = {
            "drives": {
                "items": [
                    {
                        "name": "sda",
                        "path": "/dev/sda",
                        "type": "disk",
                        "uuid": "disk-uuid",
                        "filesystem": "ext4",
                    },
                    {
                        "type": "part",
                        "uuid": "root-uuid",
                        "filesystem": "ext4",
                        "label": "rootfs",
                        "path": "/dev/sda1",
                        "size": "100.0 GB",
                        "mountpoints": ["/"],
                        "parent_disk_path": "/dev/sda",
                        "parent_disk_name": "sda",
                    },
                    {
                        "type": "part",
                        "uuid": "home-uuid",
                        "filesystem": "ext4",
                        "label": "home",
                        "path": "/dev/sda2",
                        "size": "400.0 GB",
                        "mountpoints": [],
                        "parent_disk_path": "/dev/sda",
                        "parent_disk_name": "sda",
                    },
                    {
                        "type": "part",
                        "uuid": "part-uuid",
                        "filesystem": "ext4",
                        "label": "Backup Drive",
                        "path": "/dev/sdb1",
                        "size": "1.0 TB",
                        "mountpoints": [],
                        "parent_disk_path": "/dev/sdb",
                        "parent_disk_name": "sdb",
                    },
                    {
                        "type": "part",
                        "uuid": "",
                        "filesystem": "ext4",
                    },
                ]
            }
        }

        locations = share_locations(system_info)

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0]["id"], "drive:part-uuid")
        self.assertEqual(locations[0]["mount_path"], "/srv/samba/drives/Backup-Drive")
        self.assertEqual(locations[0]["mount_access"], "read_write")

    def test_drive_diagnostics_explain_ineligible_devices(self):
        system_info = {
            "drives": {
                "items": [
                    {
                        "name": "sda",
                        "path": "/dev/sda",
                        "type": "disk",
                        "size": "1.0 TB",
                        "filesystem": None,
                        "uuid": None,
                        "mountpoints": [],
                    },
                    {
                        "name": "sda1",
                        "path": "/dev/sda1",
                        "type": "part",
                        "size": "1.0 TB",
                        "filesystem": "ext4",
                        "uuid": None,
                        "mountpoints": ["/"],
                    },
                ]
            }
        }

        diagnostics = drive_diagnostics(system_info)

        self.assertFalse(has_eligible_drive(system_info))
        self.assertEqual(diagnostics[0]["reason"], "not a partition, missing UUID, missing filesystem")
        self.assertEqual(diagnostics[1]["reason"], "part of the server OS drive, missing UUID")

    def test_apfs_partition_is_reported_as_unsupported(self):
        system_info = {
            "drives": {
                "items": [
                    {
                        "name": "sdb1",
                        "path": "/dev/sdb1",
                        "type": "part",
                        "size": "1.0 TB",
                        "filesystem": "apfs",
                        "uuid": "apfs-uuid",
                        "mountpoints": [],
                    }
                ]
            }
        }

        self.assertFalse(has_eligible_drive(system_info))
        self.assertEqual(
            drive_diagnostics(system_info)[0]["reason"],
            "APFS is not supported by this wizard",
        )


if __name__ == "__main__":
    unittest.main()
