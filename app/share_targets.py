from __future__ import annotations

import re
from typing import Any


SERVER_FOLDER_ID = "server_folder"
SERVER_FOLDER_PATH = "/srv/samba/testshare"
DRIVE_MOUNT_ROOT = "/srv/samba/drives"


def safe_name(value: str, default: str = "share") -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-_")
    return clean or default


def share_locations(system_info: dict[str, Any]) -> list[dict[str, Any]]:
    locations = [
        {
            "id": SERVER_FOLDER_ID,
            "type": "server_folder",
            "name": "Server folder on this computer",
            "description": f"Creates a private folder at {SERVER_FOLDER_PATH}",
            "path": SERVER_FOLDER_PATH,
        }
    ]

    for drive in system_info.get("drives", {}).get("items", []):
        if not _is_eligible_partition(drive):
            continue
        uuid = drive["uuid"]
        label = drive.get("label") or drive.get("model") or drive.get("name") or uuid
        mount_name = safe_name(label, default=uuid)
        mountpoints = drive.get("mountpoints") or []
        mount_status = (
            f"currently mounted at {', '.join(mountpoints)}"
            if mountpoints
            else "not currently mounted"
        )
        filesystem = drive.get("filesystem") or "unknown filesystem"
        size = drive.get("size") or "unknown size"
        locations.append(
            {
                "id": f"drive:{uuid}",
                "type": "drive",
                "name": f"{label} drive",
                "description": f"{size}, {filesystem}, {mount_status}",
                "path": drive.get("path"),
                "uuid": uuid,
                "filesystem": filesystem,
                "mount_path": f"{DRIVE_MOUNT_ROOT}/{mount_name}",
                "mountpoints": mountpoints,
                "size": size,
                "label": label,
            }
        )

    return locations


def drive_diagnostics(system_info: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics = []
    for drive in system_info.get("drives", {}).get("items", []):
        reasons = ineligible_reasons(drive)
        mountpoints = drive.get("mountpoints") or []
        diagnostics.append(
            {
                "name": drive.get("label")
                or drive.get("model")
                or drive.get("name")
                or drive.get("path")
                or "Detected storage",
                "path": drive.get("path") or "Unavailable",
                "type": drive.get("type") or "unknown",
                "size": drive.get("size") or "unknown size",
                "filesystem": drive.get("filesystem") or "missing",
                "uuid": drive.get("uuid") or "missing",
                "mountpoints": ", ".join(mountpoints) if mountpoints else "not mounted",
                "eligible": not reasons,
                "reason": "Ready to share" if not reasons else ", ".join(reasons),
            }
        )
    return diagnostics


def has_eligible_drive(system_info: dict[str, Any]) -> bool:
    return any(
        location.get("type") == "drive"
        for location in share_locations(system_info)
    )


def selected_location_from(
    location_id: str | None,
    system_info: dict[str, Any],
) -> dict[str, Any] | None:
    return next(
        (item for item in share_locations(system_info) if item["id"] == location_id),
        None,
    )


def _is_eligible_partition(drive: dict[str, Any]) -> bool:
    return not ineligible_reasons(drive)


def ineligible_reasons(drive: dict[str, Any]) -> list[str]:
    reasons = []
    if drive.get("type") != "part":
        reasons.append("not a partition")
    if not drive.get("uuid"):
        reasons.append("missing UUID")
    if not drive.get("filesystem"):
        reasons.append("missing filesystem")
    return reasons
