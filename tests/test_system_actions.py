import tempfile
import unittest
from pathlib import Path

from app.system_actions import (
    CommandResult,
    apply_share_setup,
    backup_file,
    sanitize_username,
    update_fstab_text,
    update_smb_conf_text,
)


class FakeRunner:
    def __init__(self, failures=None):
        self.calls = []
        self.failures = failures or {}

    def __call__(self, args, input_text=None, env=None):
        self.calls.append((args, input_text, env))
        key = tuple(args)
        if key in self.failures:
            return self.failures[key]
        if args[:2] == ["systemctl", "is-active"]:
            return CommandResult(args=args, returncode=1, stderr="systemd unavailable")
        if args[:2] == ["service", "smbd"]:
            return CommandResult(args=args, returncode=0, stdout="smbd is running")
        return CommandResult(args=args, returncode=0, stdout="ok")


class SystemActionTests(unittest.TestCase):
    def test_sanitize_username_uses_safe_lowercase_name(self):
        self.assertEqual(sanitize_username("Samba User!"), "samba-user")
        self.assertEqual(sanitize_username(""), "sambauser")

    def test_update_smb_conf_adds_and_replaces_managed_block(self):
        first = update_smb_conf_text("[global]\n", "Backups", "/srv/samba/testshare", "sambauser")
        self.assertIn("[Backups]", first)
        self.assertIn("path = /srv/samba/testshare", first)

        second = update_smb_conf_text(first, "Backups", "/srv/samba/newpath", "otheruser")

        self.assertEqual(second.count("BEGIN SAMBA WIZARD SHARE Backups"), 1)
        self.assertIn("path = /srv/samba/newpath", second)
        self.assertNotIn("path = /srv/samba/testshare", second)

    def test_update_fstab_adds_and_replaces_managed_entry(self):
        location = {
            "uuid": "abc-123",
            "mount_path": "/srv/samba/drives/Backups",
            "filesystem": "ext4",
        }
        first = update_fstab_text("", location)
        self.assertIn("UUID=abc-123 /srv/samba/drives/Backups ext4 defaults,nofail 0 2", first)

        location["mount_path"] = "/srv/samba/drives/NewBackups"
        second = update_fstab_text(first, location)

        self.assertEqual(second.count("BEGIN SAMBA WIZARD MOUNT abc-123"), 1)
        self.assertIn("/srv/samba/drives/NewBackups", second)
        self.assertNotIn("/srv/samba/drives/Backups ext4", second)

    def test_backup_file_creates_timestamped_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "smb.conf"
            path.write_text("original", encoding="utf-8")

            backup = backup_file(path)

            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_text(encoding="utf-8"), "original")

    def test_apply_share_setup_blocks_when_not_root(self):
        results = apply_share_setup(
            {"type": "server_folder", "path": "/srv/samba/testshare"},
            "Backups",
            "sambauser",
            "secret-password",
            command_runner=FakeRunner(),
            root_checker=lambda: False,
        )

        self.assertEqual(results[0]["id"], "root_required")
        self.assertEqual(results[0]["status"], "failed")

    def test_apply_share_setup_runs_simple_folder_steps_without_leaking_password(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = FakeRunner()
            results = apply_share_setup(
                {"type": "server_folder", "path": f"{directory}/share"},
                "Backups",
                "sambauser",
                "secret-password",
                command_runner=runner,
                root_checker=lambda: True,
                smb_conf_path=Path(directory) / "smb.conf",
                fstab_path=Path(directory) / "fstab",
            )

        self.assertTrue(all(result["status"] == "passed" for result in results))
        self.assertIn(["apt-get", "update"], [call[0] for call in runner.calls])
        self.assertIn(["smbpasswd", "-a", "-s", "sambauser"], [call[0] for call in runner.calls])
        self.assertNotIn("secret-password", repr(results))

    def test_apply_share_setup_stops_on_failed_drive_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            mount_path = f"{directory}/mnt"
            runner = FakeRunner(
                failures={
                    ("mount", mount_path): CommandResult(
                        args=["mount", mount_path],
                        returncode=1,
                        stderr="mount failed",
                    )
                }
            )
            results = apply_share_setup(
                {
                    "type": "drive",
                    "uuid": "abc-123",
                    "filesystem": "ext4",
                    "mount_path": mount_path,
                },
                "Backups",
                "sambauser",
                "secret-password",
                command_runner=runner,
                root_checker=lambda: True,
                smb_conf_path=Path(directory) / "smb.conf",
                fstab_path=Path(directory) / "fstab",
            )

        self.assertEqual(results[-1]["id"], "prepare_target")
        self.assertEqual(results[-1]["status"], "failed")
        self.assertNotIn(["testparm", "-s"], [call[0] for call in runner.calls])


if __name__ == "__main__":
    unittest.main()
