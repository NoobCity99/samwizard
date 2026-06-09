from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.share_targets import SERVER_FOLDER_PATH, safe_name


SMB_CONF_PATH = Path("/etc/samba/smb.conf")
FSTAB_PATH = Path("/etc/fstab")


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class OperationResult:
    id: str
    title: str
    status: str
    summary: str
    details: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
            "details": self.details,
        }


CommandRunner = Callable[[list[str], str | None, dict[str, str] | None], CommandResult]


def run_command(
    args: list[str],
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    command_env = os.environ.copy()
    if env:
        command_env.update(env)
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            check=False,
            env=command_env,
            input=input_text,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(args=args, returncode=1, stderr=str(exc))
    return CommandResult(
        args=args,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def is_root() -> bool:
    geteuid = getattr(os, "geteuid", None)
    return bool(callable(geteuid) and geteuid() == 0)


def apply_share_setup(
    location: dict[str, Any],
    share_name: str,
    username: str,
    password: str,
    *,
    command_runner: CommandRunner = run_command,
    root_checker: Callable[[], bool] = is_root,
    smb_conf_path: Path = SMB_CONF_PATH,
    fstab_path: Path = FSTAB_PATH,
) -> list[dict[str, Any]]:
    results: list[OperationResult] = []

    if not root_checker():
        return [
            failed(
                "root_required",
                "Administrator access needed",
                "Restart the wizard with sudo before applying real system changes.",
                ["Example: sudo .venv-wsl/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080"],
            ).as_dict()
        ]

    for step in (
        lambda: install_samba(command_runner),
        lambda: prepare_share_target(location, share_name, command_runner, fstab_path),
        lambda: ensure_samba_user(username, password, command_runner),
        lambda: set_share_owner(location, username, command_runner),
        lambda: configure_samba_share(location, share_name, username, smb_conf_path),
        lambda: validate_samba_config(command_runner),
        lambda: reload_samba(command_runner),
    ):
        result = step()
        results.append(result)
        if result.status == "failed":
            break

    return [result.as_dict() for result in results]


def install_samba(command_runner: CommandRunner = run_command) -> OperationResult:
    steps = [
        (
            "Updating the package list",
            ["apt-get", "update"],
            None,
            {"DEBIAN_FRONTEND": "noninteractive"},
        ),
        (
            "Installing Windows file sharing support",
            ["apt-get", "install", "-y", "samba"],
            None,
            {"DEBIAN_FRONTEND": "noninteractive"},
        ),
        ("Checking Samba version", ["smbd", "--version"], None, None),
    ]
    details: list[str] = []
    for label, args, input_text, env in steps:
        result = command_runner(args, input_text, env)
        details.append(_command_detail(label, result))
        if result.returncode != 0:
            return failed("install_samba", "Install Samba", f"{label} failed.", details)

    service = _service_status(command_runner)
    details.extend(service.details)
    if service.status == "failed":
        return service
    return passed(
        "install_samba",
        "Install Samba",
        "Windows file sharing support is installed.",
        details,
    )


def prepare_share_target(
    location: dict[str, Any],
    share_name: str,
    command_runner: CommandRunner = run_command,
    fstab_path: Path = FSTAB_PATH,
) -> OperationResult:
    if location.get("type") == "drive":
        mount_path = Path(location["mount_path"])
        fstab_result = update_fstab_for_drive(fstab_path, location)
        if fstab_result.status == "failed":
            return fstab_result
        mkdir_mount = command_runner(["mkdir", "-p", str(mount_path)], None, None)
        if mkdir_mount.returncode != 0:
            return failed("prepare_target", "Prepare shared folder", "The drive mount folder could not be created.", [_command_detail("Create drive mount folder", mkdir_mount)])
        mount_result = command_runner(["mount", str(mount_path)], None, None)
        if mount_result.returncode != 0:
            return failed("prepare_target", "Prepare shared folder", "The selected drive could not be mounted.", fstab_result.details + [_command_detail("Mount selected drive", mount_result)])
        target_path = mount_path / safe_name(share_name)
        details = fstab_result.details + [_command_detail("Mount selected drive", mount_result)]
    else:
        target_path = Path(location.get("path") or SERVER_FOLDER_PATH)
        details = [f"Using server folder: {target_path}"]

    mkdir_result = command_runner(["mkdir", "-p", str(target_path)], None, None)
    if mkdir_result.returncode != 0:
        return failed("prepare_target", "Prepare shared folder", "The shared folder could not be created.", details + [_command_detail("Create shared folder", mkdir_result)])

    chmod_result = command_runner(["chmod", "0770", str(target_path)], None, None)
    if chmod_result.returncode != 0:
        return failed("prepare_target", "Prepare shared folder", "The shared folder permissions could not be set.", details + [_command_detail("Set folder permissions", chmod_result)])

    location["resolved_path"] = str(target_path)
    return passed(
        "prepare_target",
        "Prepare shared folder",
        "The shared folder is ready.",
        details + [_command_detail("Create shared folder", mkdir_result), _command_detail("Set folder permissions", chmod_result)],
    )


def ensure_samba_user(
    username: str,
    password: str,
    command_runner: CommandRunner = run_command,
) -> OperationResult:
    safe_username = sanitize_username(username)
    details: list[str] = []
    id_result = command_runner(["id", "-u", safe_username], None, None)
    if id_result.returncode != 0:
        useradd_result = command_runner(
            ["useradd", "--create-home", "--shell", "/usr/sbin/nologin", safe_username],
            None,
            None,
        )
        details.append(_command_detail("Create private share user", useradd_result))
        if useradd_result.returncode != 0:
            return failed("samba_user", "Create private access", "The private share user could not be created.", details)
    else:
        details.append("Private share user already exists.")

    password_input = f"{password}\n{password}\n"
    smbpasswd_result = command_runner(["smbpasswd", "-a", "-s", safe_username], password_input, None)
    details.append(_command_detail("Set Samba password", smbpasswd_result))
    if smbpasswd_result.returncode != 0:
        return failed("samba_user", "Create private access", "The Samba password could not be set.", details)

    return passed("samba_user", "Create private access", "Private Windows sign-in is ready.", details)


def set_share_owner(
    location: dict[str, Any],
    username: str,
    command_runner: CommandRunner = run_command,
) -> OperationResult:
    target_path = location.get("resolved_path") or location.get("path") or SERVER_FOLDER_PATH
    safe_username = sanitize_username(username)
    result = command_runner(["chown", f"{safe_username}:{safe_username}", target_path], None, None)
    if result.returncode != 0:
        return failed(
            "folder_owner",
            "Lock folder to private user",
            "The shared folder owner could not be set.",
            [_command_detail("Set folder owner", result)],
        )
    return passed(
        "folder_owner",
        "Lock folder to private user",
        "The shared folder is limited to the private user.",
        [_command_detail("Set folder owner", result)],
    )


def configure_samba_share(
    location: dict[str, Any],
    share_name: str,
    username: str,
    smb_conf_path: Path = SMB_CONF_PATH,
) -> OperationResult:
    target_path = location.get("resolved_path") or location.get("path") or SERVER_FOLDER_PATH
    try:
        original = smb_conf_path.read_text(encoding="utf-8") if smb_conf_path.exists() else ""
        updated = update_smb_conf_text(original, share_name, target_path, sanitize_username(username))
        if updated != original:
            backup_file(smb_conf_path)
            smb_conf_path.parent.mkdir(parents=True, exist_ok=True)
            smb_conf_path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        return failed("samba_config", "Configure Windows sharing", "The Samba configuration could not be updated.", [str(exc)])

    return passed(
        "samba_config",
        "Configure Windows sharing",
        "The Windows share was added to Samba.",
        [f"Share name: {safe_name(share_name)}", f"Folder: {target_path}"],
    )


def validate_samba_config(command_runner: CommandRunner = run_command) -> OperationResult:
    result = command_runner(["testparm", "-s"], None, None)
    if result.returncode != 0:
        return failed("validate_samba", "Check sharing settings", "Samba rejected the configuration.", [_command_detail("Validate Samba configuration", result)])
    return passed("validate_samba", "Check sharing settings", "Samba accepted the configuration.", [_command_detail("Validate Samba configuration", result)])


def reload_samba(command_runner: CommandRunner = run_command) -> OperationResult:
    details: list[str] = []
    for args in (["systemctl", "restart", "smbd"], ["service", "smbd", "restart"]):
        result = command_runner(args, None, None)
        details.append(_command_detail("Restart Windows file sharing", result))
        if result.returncode == 0:
            return passed("restart_samba", "Restart Windows file sharing", "Windows file sharing restarted.", details)
    return failed("restart_samba", "Restart Windows file sharing", "Samba could not be restarted automatically.", details)


def update_smb_conf_text(
    original: str,
    share_name: str,
    path: str,
    username: str,
) -> str:
    share = safe_name(share_name)
    start = f"# BEGIN SAMBA WIZARD SHARE {share}"
    end = f"# END SAMBA WIZARD SHARE {share}"
    block = "\n".join(
        [
            start,
            f"[{share}]",
            f"   path = {path}",
            f"   valid users = {username}",
            "   read only = no",
            "   browsable = yes",
            "   create mask = 0660",
            "   directory mask = 0770",
            end,
            "",
        ]
    )
    return replace_managed_block(original, start, end, block)


def update_fstab_text(original: str, location: dict[str, Any]) -> str:
    uuid = location["uuid"]
    mount_path = location["mount_path"]
    filesystem = location["filesystem"]
    start = f"# BEGIN SAMBA WIZARD MOUNT {uuid}"
    end = f"# END SAMBA WIZARD MOUNT {uuid}"
    block = "\n".join(
        [
            start,
            f"UUID={uuid} {mount_path} {filesystem} defaults,nofail 0 2",
            end,
            "",
        ]
    )
    return replace_managed_block(original, start, end, block)


def update_fstab_for_drive(fstab_path: Path, location: dict[str, Any]) -> OperationResult:
    if not location.get("uuid") or not location.get("filesystem") or not location.get("mount_path"):
        return failed("fstab", "Prepare selected drive", "The selected drive is missing UUID, filesystem, or mount path details.", [])
    try:
        original = fstab_path.read_text(encoding="utf-8") if fstab_path.exists() else ""
        updated = update_fstab_text(original, location)
        if updated != original:
            backup_file(fstab_path)
            fstab_path.parent.mkdir(parents=True, exist_ok=True)
            fstab_path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        return failed("fstab", "Prepare selected drive", "The drive mount settings could not be updated.", [str(exc)])
    return passed("fstab", "Prepare selected drive", "The selected drive has a persistent mount entry.", [f"Mount folder: {location['mount_path']}"])


def replace_managed_block(original: str, start: str, end: str, block: str) -> str:
    if start in original and end in original:
        before, rest = original.split(start, 1)
        _old, after = rest.split(end, 1)
        return before.rstrip() + "\n\n" + block + after.lstrip("\n")
    separator = "\n\n" if original.strip() else ""
    return original.rstrip() + separator + block


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = path.with_name(f"{path.name}.samba-wizard.{stamp}.bak")
    shutil.copy2(path, backup)
    return backup


def sanitize_username(username: str) -> str:
    return safe_name(username.lower(), default="sambauser")


def passed(id: str, title: str, summary: str, details: list[str]) -> OperationResult:
    return OperationResult(id=id, title=title, status="passed", summary=summary, details=details)


def failed(id: str, title: str, summary: str, details: list[str]) -> OperationResult:
    return OperationResult(id=id, title=title, status="failed", summary=summary, details=details)


def _service_status(command_runner: CommandRunner) -> OperationResult:
    details: list[str] = []
    systemctl = command_runner(["systemctl", "is-active", "smbd"], None, None)
    details.append(_command_detail("Check Samba service", systemctl))
    if systemctl.returncode == 0:
        return passed("samba_service", "Check Samba service", "Samba service is active.", details)

    service = command_runner(["service", "smbd", "status"], None, None)
    details.append(_command_detail("Check Samba service fallback", service))
    if service.returncode == 0:
        return passed("samba_service", "Check Samba service", "Samba service responded.", details)

    return passed(
        "samba_service",
        "Check Samba service",
        "Samba is installed. Service status could not be confirmed in this environment.",
        details,
    )


def _command_detail(label: str, result: CommandResult) -> str:
    command = " ".join(result.args)
    output = (result.stdout or result.stderr or "").strip()
    if output:
        first_line = output.splitlines()[0]
        return f"{label}: `{command}` exited {result.returncode}. {first_line}"
    return f"{label}: `{command}` exited {result.returncode}."
