import unittest

from app.share_targets import (
    SERVER_FOLDER_ID,
    drive_diagnostics,
    has_eligible_drive,
    safe_name,
    share_locations,
)


class ShareTargetTests(unittest.TestCase):
    def test_safe_name_limits_to_simple_path_characters(self):
        self.assertEqual(safe_name("Family Photos!"), "Family-Photos")
        self.assertEqual(safe_name(""), "share")

    def test_share_locations_include_server_folder_and_eligible_partitions(self):
        system_info = {
            "drives": {
                "items": [
                    {
                        "type": "disk",
                        "uuid": "disk-uuid",
                        "filesystem": "ext4",
                    },
                    {
                        "type": "part",
                        "uuid": "part-uuid",
                        "filesystem": "ext4",
                        "label": "Backup Drive",
                        "path": "/dev/sdb1",
                        "size": "1.0 TB",
                        "mountpoints": [],
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

        self.assertEqual(locations[0]["id"], SERVER_FOLDER_ID)
        self.assertEqual(len(locations), 2)
        self.assertEqual(locations[1]["id"], "drive:part-uuid")
        self.assertEqual(locations[1]["mount_path"], "/srv/samba/drives/Backup-Drive")

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
        self.assertEqual(diagnostics[1]["reason"], "missing UUID")


if __name__ == "__main__":
    unittest.main()
