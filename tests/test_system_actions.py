import os
import tempfile
import unittest
from pathlib import Path

from app.system_actions import (
    CommandResult,
    apply_share_setup,
    backup_file,
    prepare_drive_mount_settings,
    sanitize_username,
    update_fstab_text,
    update_smb_conf_text,
)


LSBLK_ARGS = (
    "lsblk",
    "--json",
    "--bytes",
    "--output",
    "NAME,KNAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINTS,LABEL,MODEL,UUID",
)


def drive_lsblk_json(
    *,
    path="/dev/sda1",
    uuid="abc-123",
    filesystem="ext4",
    label="Backups",
):
    return f"""
    {{
      "blockdevices": [
        {{
          "name": "sda",
          "path": "/dev/sda",
          "type": "disk",
          "size": 1073741824,
          "fstype": null,
          "mountpoints": null,
          "label": null,
          "model": "Virtual Disk",
          "uuid": null,
          "children": [
            {{
              "name": "sda1",
              "path": "{path}",
              "type": "part",
              "size": 536870912,
              "fstype": "{filesystem}",
              "mountpoints": [],
              "label": "{label}",
              "model": null,
              "uuid": "{uuid}"
            }}
          ]
        }}
      ]
    }}
    """


def findmnt_json(options="rw,relatime"):
    return f"""
    {{
      "filesystems": [
        {{
          "target": "/mnt",
          "source": "/dev/sda1",
          "fstype": "ext4",
          "options": "{options}"
        }}
      ]
    }}
    """


class FakeRunner:
    def __init__(self, failures=None, responses=None):
        self.calls = []
        self.failures = failures or {}
        self.responses = responses or {}

    def __call__(self, args, input_text=None, env=None):
        self.calls.append((args, input_text, env))
        key = tuple(args)
        if key in self.failures:
            return self.failures[key]
        if key in self.responses:
            return self.responses[key]
        if args[:2] == ["id", "-u"]:
            return CommandResult(args=args, returncode=0, stdout="1001\n")
        if args[:2] == ["id", "-g"]:
            return CommandResult(args=args, returncode=0, stdout="1001\n")
        if args[:1] == ["findmnt"]:
            return CommandResult(args=args, returncode=0, stdout=findmnt_json())
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
        first = update_smb_conf_text(
            "[global]\n", "Backups", "/srv/samba/testshare", "sambauser")
        self.assertIn("[Backups]", first)
        self.assertIn("path = /srv/samba/testshare", first)

        second = update_smb_conf_text(
            first, "Backups", "/srv/samba/newpath", "otheruser")

        self.assertEqual(second.count("BEGIN SAMBA WIZARD SHARE Backups"), 1)
        self.assertIn("path = /srv/samba/newpath", second)
        self.assertNotIn("path = /srv/samba/testshare", second)

    def test_update_smb_conf_can_create_read_only_share(self):
        updated = update_smb_conf_text(
            "",
            "Backups",
            "/srv/samba/drives/Backups",
            "sambauser",
            read_only=True,
        )

        self.assertIn("read only = yes", updated)

    def test_update_fstab_adds_and_replaces_managed_entry(self):
        location = {
            "uuid": "abc-123",
            "mount_path": "/srv/samba/drives/Backups",
            "filesystem": "ext4",
        }
        first = update_fstab_text("", location)
        self.assertIn(
            "UUID=abc-123 /srv/samba/drives/Backups ext4 defaults,rw,nofail 0 2", first)

        location["mount_path"] = "/srv/samba/drives/NewBackups"
        second = update_fstab_text(first, location)

        self.assertEqual(second.count("BEGIN SAMBA WIZARD MOUNT abc-123"), 1)
        self.assertIn("/srv/samba/drives/NewBackups", second)
        self.assertNotIn("/srv/samba/drives/Backups ext4", second)

    def test_update_fstab_uses_filesystem_specific_mount_options(self):
        ext4_read_only = update_fstab_text(
            "",
            {
                "uuid": "ext4-uuid",
                "mount_path": "/srv/samba/drives/Linux",
                "filesystem": "ext4",
                "mount_access": "read_only",
            },
        )
        self.assertIn(
            "UUID=ext4-uuid /srv/samba/drives/Linux ext4 defaults,ro,nofail 0 2",
            ext4_read_only,
        )

        ntfs_read_write = update_fstab_text(
            "",
            {
                "uuid": "ntfs-uuid",
                "mount_path": "/srv/samba/drives/Windows",
                "filesystem": "ntfs",
                "mount_fstype": "ntfs-3g",
                "mount_options": "rw,nofail,uid=1001,gid=1001,umask=007",
                "fsck_pass": "0",
            },
        )
        self.assertIn(
            "UUID=ntfs-uuid /srv/samba/drives/Windows ntfs-3g rw,nofail,uid=1001,gid=1001,umask=007 0 0",
            ntfs_read_write,
        )

        exfat_read_write = update_fstab_text(
            "",
            {
                "uuid": "exfat-uuid",
                "mount_path": "/srv/samba/drives/Exfat",
                "filesystem": "exfat",
                "mount_fstype": "exfat",
                "mount_options": "rw,nofail,uid=1001,gid=1001,umask=007",
                "fsck_pass": "0",
            },
        )
        self.assertIn(
            "UUID=exfat-uuid /srv/samba/drives/Exfat exfat rw,nofail,uid=1001,gid=1001,umask=007 0 0",
            exfat_read_write,
        )

    def test_prepare_drive_mount_settings_uses_private_user_for_ntfs(self):
        location = {
            "type": "drive",
            "uuid": "ntfs-uuid",
            "filesystem": "ntfs",
            "mount_path": "/srv/samba/drives/Windows",
            "mount_access": "read_write",
        }
        result = prepare_drive_mount_settings(location, "sambauser", FakeRunner())

        self.assertEqual(result.status, "passed")
        self.assertEqual(location["mount_fstype"], "ntfs-3g")
        self.assertEqual(location["mount_options"], "rw,nofail,uid=1001,gid=1001,umask=007")
        self.assertEqual(location["fsck_pass"], "0")

    def test_update_fstab_removes_stale_managed_entry_for_same_mount_path(self):
        mount_path = "/srv/samba/drives/Backups"
        old_location = {
            "uuid": "old-uuid",
            "mount_path": mount_path,
            "filesystem": "ntfs",
        }
        original = update_fstab_text(
            "/dev/root / ext4 defaults 0 1\n", old_location)

        updated = update_fstab_text(
            original,
            {
                "uuid": "new-uuid",
                "mount_path": mount_path,
                "filesystem": "ext4",
            },
        )

        self.assertIn("/dev/root / ext4 defaults 0 1", updated)
        self.assertIn(
            "UUID=new-uuid /srv/samba/drives/Backups ext4 defaults,rw,nofail 0 2", updated)
        self.assertNotIn("UUID=old-uuid", updated)
        self.assertEqual(updated.count("BEGIN SAMBA WIZARD MOUNT"), 1)

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
            {
                "type": "drive",
                "path": "/dev/sda1",
                "uuid": "abc-123",
                "filesystem": "ext4",
                "mount_path": "/srv/samba/drives/Backups",
            },
            "Backups",
            "sambauser",
            "secret-password",
            command_runner=FakeRunner(),
            root_checker=lambda: False,
        )

        self.assertEqual(results[0]["id"], "root_required")
        self.assertEqual(results[0]["status"], "failed")

    def test_apply_share_setup_rejects_server_folder_without_leaking_password(self):
        runner = FakeRunner()
        results = apply_share_setup(
            {"type": "server_folder", "path": "/srv/samba/testshare"},
            "Backups",
            "sambauser",
            "secret-password",
            command_runner=runner,
            root_checker=lambda: True,
        )

        self.assertEqual(results[0]["id"], "drive_required")
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(runner.calls, [])
        self.assertNotIn("secret-password", repr(results))

    def test_apply_share_setup_stops_on_failed_drive_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            mount_path = f"{directory}/mnt"
            lsblk_result = CommandResult(
                args=list(LSBLK_ARGS),
                returncode=0,
                stdout=drive_lsblk_json(path="/dev/sda1", uuid="abc-123"),
            )
            runner = FakeRunner(
                responses={LSBLK_ARGS: lsblk_result},
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
                    "path": "/dev/sda1",
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
        self.assertNotIn(["testparm", "-s"], [call[0]
                         for call in runner.calls])

    def test_apply_share_setup_refreshes_drive_uuid_before_fstab_mount_and_verify(self):
        with tempfile.TemporaryDirectory() as directory:
            mount_path = f"{directory}/mnt"
            fstab_path = Path(directory) / "fstab"
            fstab_path.write_text(
                update_fstab_text(
                    "",
                    {
                        "uuid": "old-uuid",
                        "filesystem": "ntfs",
                        "mount_path": mount_path,
                    },
                ),
                encoding="utf-8",
            )
            lsblk_result = CommandResult(
                args=list(LSBLK_ARGS),
                returncode=0,
                stdout=drive_lsblk_json(
                    path="/dev/sda1", uuid="new-uuid", filesystem="ext4"),
            )
            runner = FakeRunner(responses={LSBLK_ARGS: lsblk_result})
            location = {
                "type": "drive",
                "path": "/dev/sda1",
                "uuid": "old-uuid",
                "filesystem": "ntfs",
                "mount_path": mount_path,
                "mount_access": "read_write",
            }

            results = apply_share_setup(
                location,
                "Backups",
                "sambauser",
                "secret-password",
                command_runner=runner,
                root_checker=lambda: True,
                smb_conf_path=Path(directory) / "smb.conf",
                fstab_path=fstab_path,
            )
            fstab_content = fstab_path.read_text(encoding="utf-8")

        calls = [call[0] for call in runner.calls]
        findmnt_call = [
            "findmnt",
            "--json",
            "--mountpoint",
            mount_path,
            "--output",
            "TARGET,SOURCE,FSTYPE,OPTIONS",
        ]
        write_probe_call = [
            "runuser",
            "-u",
            "sambauser",
            "--",
            "touch",
        ]

        self.assertTrue(
            all(result["status"] == "passed" for result in results))
        self.assertEqual(location["uuid"], "new-uuid")
        self.assertEqual(location["filesystem"], "ext4")
        self.assertEqual(location["resolved_path"], mount_path)
        self.assertIn("UUID=new-uuid", fstab_content)
        self.assertNotIn("UUID=old-uuid", fstab_content)
        self.assertIn(
            "Drive UUID refreshed from old-uuid to new-uuid before writing fstab.", repr(results))
        self.assertLess(calls.index(
            ["systemctl", "daemon-reload"]), calls.index(["mount", mount_path]))
        self.assertLess(calls.index(
            ["mount", mount_path]), calls.index(findmnt_call))
        self.assertFalse(any(call == ["mkdir", "-p", f"{mount_path}/Backups"] for call in calls))
        self.assertTrue(any(call[:5] == write_probe_call for call in calls))

    def test_apply_share_setup_add_drive_mode_reuses_existing_samba_user(self):
        with tempfile.TemporaryDirectory() as directory:
            mount_path = f"{directory}/mnt"
            smb_conf_path = Path(directory) / "smb.conf"
            fstab_path = Path(directory) / "fstab"
            lsblk_result = CommandResult(
                args=list(LSBLK_ARGS),
                returncode=0,
                stdout=drive_lsblk_json(path="/dev/sda1", uuid="abc-123"),
            )
            runner = FakeRunner(
                responses={
                    LSBLK_ARGS: lsblk_result,
                    ("pdbedit", "-L"): CommandResult(
                        args=["pdbedit", "-L"],
                        returncode=0,
                        stdout="sambauser:1001:Samba User\n",
                    ),
                    ("smbd", "--version"): CommandResult(
                        args=["smbd", "--version"],
                        returncode=0,
                        stdout="Version 4.21.0-Ubuntu\n",
                    ),
                }
            )

            results = apply_share_setup(
                {
                    "type": "drive",
                    "path": "/dev/sda1",
                    "uuid": "abc-123",
                    "filesystem": "ext4",
                    "mount_path": mount_path,
                    "mount_access": "read_write",
                },
                "Backups",
                "sambauser",
                None,
                create_user=False,
                command_runner=runner,
                root_checker=lambda: True,
                smb_conf_path=smb_conf_path,
                fstab_path=fstab_path,
            )
            smb_conf = smb_conf_path.read_text(encoding="utf-8")

        calls = [call[0] for call in runner.calls]
        self.assertTrue(all(result["status"] == "passed" for result in results))
        self.assertEqual(results[0]["id"], "verify_samba")
        self.assertEqual(results[1]["id"], "existing_samba_user")
        self.assertIn(f"path = {mount_path}", smb_conf)
        self.assertNotIn(["useradd", "--create-home", "--shell", "/usr/sbin/nologin", "sambauser"], calls)
        self.assertFalse(any(call[:1] == ["smbpasswd"] for call in calls))
        self.assertIn(["testparm", "-s"], calls)

    def test_apply_share_setup_fails_when_read_write_drive_mounts_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            mount_path = f"{directory}/mnt"
            findmnt_call = (
                "findmnt",
                "--json",
                "--mountpoint",
                mount_path,
                "--output",
                "TARGET,SOURCE,FSTYPE,OPTIONS",
            )
            lsblk_result = CommandResult(
                args=list(LSBLK_ARGS),
                returncode=0,
                stdout=drive_lsblk_json(path="/dev/sda1", uuid="abc-123"),
            )
            runner = FakeRunner(
                responses={
                    LSBLK_ARGS: lsblk_result,
                    findmnt_call: CommandResult(
                        args=list(findmnt_call),
                        returncode=0,
                        stdout=findmnt_json("ro,relatime"),
                    ),
                },
            )
            results = apply_share_setup(
                {
                    "type": "drive",
                    "path": "/dev/sda1",
                    "uuid": "abc-123",
                    "filesystem": "ext4",
                    "mount_path": mount_path,
                    "mount_access": "read_write",
                },
                "Backups",
                "sambauser",
                "secret-password",
                command_runner=runner,
                root_checker=lambda: True,
                smb_conf_path=Path(directory) / "smb.conf",
                fstab_path=Path(directory) / "fstab",
            )

        calls = [call[0] for call in runner.calls]
        self.assertEqual(results[-1]["id"], "prepare_target")
        self.assertEqual(results[-1]["status"], "failed")
        self.assertIn("mounted the drive read-only", results[-1]["summary"])
        self.assertFalse(any(call[:5] == ["runuser", "-u", "sambauser", "--", "touch"] for call in calls))

    def test_apply_share_setup_fails_when_drive_write_probe_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            mount_path = f"{directory}/mnt"
            lsblk_result = CommandResult(
                args=list(LSBLK_ARGS),
                returncode=0,
                stdout=drive_lsblk_json(path="/dev/sda1", uuid="abc-123"),
            )
            runner = FakeRunner(
                responses={LSBLK_ARGS: lsblk_result},
                failures={
                    (
                        "runuser",
                        "-u",
                        "sambauser",
                        "--",
                        "touch",
                        f"{mount_path}/.samwizard-write-test-{os.getpid()}",
                    ): CommandResult(
                        args=[
                            "runuser",
                            "-u",
                            "sambauser",
                            "--",
                            "touch",
                            f"{mount_path}/.samwizard-write-test-{os.getpid()}",
                        ],
                        returncode=1,
                        stderr="permission denied",
                    )
                },
            )
            results = apply_share_setup(
                {
                    "type": "drive",
                    "path": "/dev/sda1",
                    "uuid": "abc-123",
                    "filesystem": "ext4",
                    "mount_path": mount_path,
                    "mount_access": "read_write",
                },
                "Backups",
                "sambauser",
                "secret-password",
                command_runner=runner,
                root_checker=lambda: True,
                smb_conf_path=Path(directory) / "smb.conf",
                fstab_path=Path(directory) / "fstab",
            )

        self.assertEqual(results[-1]["id"], "drive_write_probe")
        self.assertEqual(results[-1]["status"], "failed")
        self.assertIn("could not write", results[-1]["summary"])

    def test_apply_share_setup_read_only_drive_skips_write_changes_and_sets_samba_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            mount_path = f"{directory}/mnt"
            smb_conf_path = Path(directory) / "smb.conf"
            fstab_path = Path(directory) / "fstab"
            findmnt_call = (
                "findmnt",
                "--json",
                "--mountpoint",
                mount_path,
                "--output",
                "TARGET,SOURCE,FSTYPE,OPTIONS",
            )
            lsblk_result = CommandResult(
                args=list(LSBLK_ARGS),
                returncode=0,
                stdout=drive_lsblk_json(path="/dev/sda1", uuid="abc-123"),
            )
            runner = FakeRunner(
                responses={
                    LSBLK_ARGS: lsblk_result,
                    findmnt_call: CommandResult(
                        args=list(findmnt_call),
                        returncode=0,
                        stdout=findmnt_json("ro,relatime"),
                    ),
                },
            )
            results = apply_share_setup(
                {
                    "type": "drive",
                    "path": "/dev/sda1",
                    "uuid": "abc-123",
                    "filesystem": "ext4",
                    "mount_path": mount_path,
                    "mount_access": "read_only",
                },
                "Backups",
                "sambauser",
                "secret-password",
                command_runner=runner,
                root_checker=lambda: True,
                smb_conf_path=smb_conf_path,
                fstab_path=fstab_path,
            )
            smb_conf = smb_conf_path.read_text(encoding="utf-8")
            fstab = fstab_path.read_text(encoding="utf-8")

        calls = [call[0] for call in runner.calls]
        self.assertTrue(all(result["status"] == "passed" for result in results))
        self.assertIn("read only = yes", smb_conf)
        self.assertIn(f"path = {mount_path}", smb_conf)
        self.assertIn("defaults,ro,nofail", fstab)
        self.assertFalse(any(call[:1] == ["runuser"] for call in calls))
        self.assertFalse(any(call == ["mkdir", "-p", f"{mount_path}/Backups"] for call in calls))
        self.assertFalse(any(call[:1] == ["chmod"] and call[-1] == mount_path for call in calls))

    def test_apply_share_setup_stops_when_drive_mount_verification_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            mount_path = f"{directory}/mnt"
            findmnt_call = (
                "findmnt",
                "--json",
                "--mountpoint",
                mount_path,
                "--output",
                "TARGET,SOURCE,FSTYPE,OPTIONS",
            )
            lsblk_result = CommandResult(
                args=list(LSBLK_ARGS),
                returncode=0,
                stdout=drive_lsblk_json(path="/dev/sda1", uuid="abc-123"),
            )
            runner = FakeRunner(
                responses={LSBLK_ARGS: lsblk_result},
                failures={
                    findmnt_call: CommandResult(
                        args=list(findmnt_call),
                        returncode=1,
                        stderr="not mounted",
                    )
                },
            )
            results = apply_share_setup(
                {
                    "type": "drive",
                    "path": "/dev/sda1",
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

        calls = [call[0] for call in runner.calls]
        self.assertEqual(results[-1]["id"], "prepare_target")
        self.assertEqual(results[-1]["status"], "failed")
        self.assertIn("could not be verified", results[-1]["summary"])
        self.assertIn(["id", "-u", "sambauser"], calls)
        self.assertNotIn(["testparm", "-s"], calls)


if __name__ == "__main__":
    unittest.main()
