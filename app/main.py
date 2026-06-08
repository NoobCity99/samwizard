from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware


app = FastAPI(title="Samba Wizard")
app.add_middleware(SessionMiddleware, secret_key="samba-wizard-milestone-1-dev")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


MOCK_SYSTEM = {
    "hostname": "home-fileserver",
    "ip_address": "192.168.1.50",
    "ubuntu_version": "Ubuntu Server 24.04 LTS",
}

MOCK_SYSTEM_CHECKS = [
    {
        "id": "hostname",
        "title": "Server name",
        "value": MOCK_SYSTEM["hostname"],
        "status": "passed",
        "summary": "This server has a friendly name on the network.",
        "critical": False,
        "commands": [],
        "logs": ["Server name found: home-fileserver"],
    },
    {
        "id": "local_ip",
        "title": "Local address",
        "value": MOCK_SYSTEM["ip_address"],
        "status": "passed",
        "summary": "The wizard can show a local address for browser access.",
        "critical": True,
        "commands": [],
        "logs": ["Local network address found: 192.168.1.50"],
    },
    {
        "id": "ubuntu_version",
        "title": "System version",
        "value": MOCK_SYSTEM["ubuntu_version"],
        "status": "passed",
        "summary": "This mock is targeting a supported Ubuntu Server release.",
        "critical": False,
        "commands": [],
        "logs": ["Ubuntu Server version looks compatible."],
    },
    {
        "id": "storage_visibility",
        "title": "Drive and folder visibility",
        "value": "3 mock locations found",
        "status": "passed",
        "summary": "The wizard has sample locations available for the clickable flow.",
        "critical": True,
        "commands": [],
        "logs": ["Mock storage scan found Backups Drive, Media Drive, and Home Folder."],
    },
    {
        "id": "internet_connectivity",
        "title": "Internet connectivity",
        "value": "Ethernet detected",
        "status": "passed",
        "summary": "The server has a wired connection for downloads and updates.",
        "critical": True,
        "commands": [
            "ip link show",
            "sudo netplan generate",
            "sudo netplan apply",
            "ping -c 3 ubuntu.com",
        ],
        "logs": [
            "Mock Wi-Fi configuration generated.",
            "Mock network settings applied.",
            "Mock internet check passed.",
        ],
    },
]

MOCK_LOCATIONS = [
    {
        "id": "backups_drive",
        "name": "Backups Drive",
        "description": "1.8 TB available, already connected",
        "path": "/mnt/backups",
    },
    {
        "id": "media_drive",
        "name": "Media Drive",
        "description": "820 GB available, already connected",
        "path": "/mnt/media",
    },
    {
        "id": "home_folder",
        "name": "Home Folder",
        "description": "Use a folder on the main server drive",
        "path": "/home/samba-share",
    },
]

STEP_ORDER = [
    "Welcome",
    "System Check",
    "Drive Selection",
    "Share Name",
    "User Setup",
    "Review",
    "Apply",
    "Done",
]


def wizard_state(request: Request) -> dict[str, Any]:
    state = request.session.setdefault("wizard", {})
    if not isinstance(state, dict):
        state = {}
        request.session["wizard"] = state
    return state


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def selected_location(location_id: str | None) -> dict[str, str] | None:
    return next((item for item in MOCK_LOCATIONS if item["id"] == location_id), None)


def system_check_state(request: Request) -> dict[str, Any]:
    state = wizard_state(request)
    checks = state.setdefault("system_checks", {})
    if not isinstance(checks, dict):
        checks = {}
    checks.setdefault("resolved", [])
    checks.setdefault("logs", {})
    checks.setdefault("wifi", {})
    checks.setdefault("ethernet_detected", True)
    state["system_checks"] = checks
    request.session["wizard"] = state
    return checks


def system_check_definition(check_id: str) -> dict[str, Any] | None:
    return next((check for check in MOCK_SYSTEM_CHECKS if check["id"] == check_id), None)


def system_checks_for_request(request: Request) -> list[dict[str, Any]]:
    check_state = system_check_state(request)
    resolved = set(check_state.get("resolved", []))
    logs = check_state.get("logs", {})
    ethernet_detected = bool(check_state.get("ethernet_detected", True))
    checks = []

    for definition in MOCK_SYSTEM_CHECKS:
        check = definition.copy()
        if check["id"] == "internet_connectivity" and not ethernet_detected:
            check["value"] = "Ethernet not detected"
            check["status"] = "needs_attention"
            check["summary"] = "Try plugging in ethernet first. If that is not available, use the Wi-Fi guide below."
        if check["id"] in resolved:
            check["status"] = "resolved"
            check["value"] = "Resolved in mock mode"
            check["summary"] = "The wizard previewed the fix and marked this check ready."
        check["logs"] = logs.get(check["id"], check["logs"] if check["status"] == "passed" else [])
        checks.append(check)

    return checks


def unresolved_critical_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        check
        for check in checks
        if check["critical"] and check["status"] == "needs_attention"
    ]


def append_resolved_check(request: Request, check_id: str) -> None:
    check_state = system_check_state(request)
    resolved = check_state.setdefault("resolved", [])
    if check_id not in resolved:
        resolved.append(check_id)

    definition = system_check_definition(check_id)
    if definition is not None:
        logs = check_state.setdefault("logs", {})
        logs[check_id] = definition["logs"]

    state = wizard_state(request)
    state["system_checks"] = check_state
    request.session["wizard"] = state


def wifi_netplan_preview(interface: str, ssid: str, password_provided: bool) -> str:
    password = "********" if password_provided else ""
    return "\n".join(
        [
            "network:",
            "  version: 2",
            "  renderer: networkd",
            "  wifis:",
            f"    {interface}:",
            "      dhcp4: true",
            "      access-points:",
            f'        "{ssid}":',
            f'          password: "{password}"',
        ]
    )


def system_check_page(
    request: Request,
    error: str | None = None,
    wifi_error: str | None = None,
):
    checks = system_checks_for_request(request)
    critical_unresolved = unresolved_critical_checks(checks)
    check_state = system_check_state(request)
    wifi_state = check_state.get("wifi", {})
    ethernet_detected = bool(check_state.get("ethernet_detected", True))
    netplan_preview = None

    if wifi_state.get("interface") and wifi_state.get("ssid"):
        netplan_preview = wifi_netplan_preview(
            wifi_state["interface"],
            wifi_state["ssid"],
            bool(wifi_state.get("password_provided")),
        )

    return templates.TemplateResponse(
        "system_check.html",
        context(
            request,
            "System Check",
            checks=checks,
            critical_unresolved=critical_unresolved,
            wifi_state=wifi_state,
            ethernet_detected=ethernet_detected,
            netplan_preview=netplan_preview,
            error=error,
            wifi_error=wifi_error,
        ),
    )


def context(request: Request, step: str, **extra: Any) -> dict[str, Any]:
    state = wizard_state(request)
    base = {
        "request": request,
        "step": step,
        "steps": STEP_ORDER,
        "step_index": STEP_ORDER.index(step) + 1,
        "step_count": len(STEP_ORDER),
        "state": state,
        "system": MOCK_SYSTEM,
        "selected_location": selected_location(state.get("location_id")),
    }
    base.update(extra)
    return base


@app.get("/")
def welcome(request: Request):
    return templates.TemplateResponse("welcome.html", context(request, "Welcome"))


@app.post("/start")
def start(request: Request):
    request.session["wizard"] = {}
    return redirect("/system-check")


@app.get("/system-check")
def system_check(request: Request, ethernet: str | None = None):
    if ethernet in {"detected", "missing"}:
        check_state = system_check_state(request)
        check_state["ethernet_detected"] = ethernet == "detected"
        if ethernet == "detected":
            check_state["wifi"] = {}
            check_state["resolved"] = [
                check_id
                for check_id in check_state.get("resolved", [])
                if check_id != "internet_connectivity"
            ]
            check_state.get("logs", {}).pop("internet_connectivity", None)
        state = wizard_state(request)
        state["system_checks"] = check_state
        request.session["wizard"] = state
    return system_check_page(request)


@app.post("/system-check")
def system_check_next(request: Request):
    checks = system_checks_for_request(request)
    if unresolved_critical_checks(checks):
        return system_check_page(
            request,
            error="Resolve the critical checks before continuing.",
        )
    return redirect("/drive-selection")




@app.post("/system-check/wifi")
def resolve_wifi(
    request: Request,
    wifi_interface: str = Form(""),
    wifi_ssid: str = Form(""),
    wifi_password: str = Form(""),
):
    clean_interface = wifi_interface.strip()
    clean_ssid = wifi_ssid.strip()

    if not clean_interface:
        return system_check_page(request, wifi_error="Enter the Wi-Fi adapter name.")
    if not clean_ssid:
        return system_check_page(request, wifi_error="Enter the Wi-Fi network name.")
    if not wifi_password:
        return system_check_page(request, wifi_error="Enter the Wi-Fi password.")

    check_state = system_check_state(request)
    check_state["wifi"] = {
        "interface": clean_interface,
        "ssid": clean_ssid,
        "password_provided": True,
    }
    state = wizard_state(request)
    state["system_checks"] = check_state
    request.session["wizard"] = state

    append_resolved_check(request, "internet_connectivity")
    return redirect("/system-check")


@app.get("/drive-selection")
def drive_selection(request: Request):
    return templates.TemplateResponse(
        "drive_selection.html",
        context(request, "Drive Selection", locations=MOCK_LOCATIONS, error=None),
    )


@app.post("/drive-selection")
def save_drive_selection(request: Request, location_id: str = Form("")):
    if selected_location(location_id) is None:
        return templates.TemplateResponse(
            "drive_selection.html",
            context(
                request,
                "Drive Selection",
                locations=MOCK_LOCATIONS,
                error="Choose a drive or folder to continue.",
            ),
            status_code=400,
        )

    state = wizard_state(request)
    state["location_id"] = location_id
    request.session["wizard"] = state
    return redirect("/share-name")


@app.get("/share-name")
def share_name(request: Request):
    if selected_location(wizard_state(request).get("location_id")) is None:
        return redirect("/drive-selection")
    return templates.TemplateResponse(
        "share_name.html",
        context(request, "Share Name", error=None),
    )


@app.post("/share-name")
def save_share_name(request: Request, share_name: str = Form("")):
    clean_name = share_name.strip()
    if not clean_name:
        return templates.TemplateResponse(
            "share_name.html",
            context(request, "Share Name", error="Enter a name for the Windows share."),
            status_code=400,
        )

    state = wizard_state(request)
    state["share_name"] = clean_name
    request.session["wizard"] = state
    return redirect("/user-setup")


@app.get("/user-setup")
def user_setup(request: Request):
    if not wizard_state(request).get("share_name"):
        return redirect("/share-name")
    return templates.TemplateResponse(
        "user_setup.html",
        context(request, "User Setup", error=None),
    )


@app.post("/user-setup")
def save_user_setup(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    confirm_password: str = Form(""),
):
    clean_username = username.strip()
    if not clean_username:
        error = "Enter a username for the private share."
    elif not password:
        error = "Enter a password for this share."
    elif password != confirm_password:
        error = "The passwords do not match."
    else:
        error = None

    if error:
        return templates.TemplateResponse(
            "user_setup.html",
            context(request, "User Setup", error=error),
            status_code=400,
        )

    state = wizard_state(request)
    state["username"] = clean_username
    state["password_confirmed"] = True
    request.session["wizard"] = state
    return redirect("/review")


@app.get("/review")
def review(request: Request):
    state = wizard_state(request)
    if selected_location(state.get("location_id")) is None:
        return redirect("/drive-selection")
    if not state.get("share_name"):
        return redirect("/share-name")
    if not state.get("username"):
        return redirect("/user-setup")

    return templates.TemplateResponse("review.html", context(request, "Review"))


@app.post("/review")
def confirm_review(request: Request):
    state = wizard_state(request)
    state["applied"] = True
    request.session["wizard"] = state
    return redirect("/apply")


@app.get("/apply")
def apply_mock(request: Request):
    if not wizard_state(request).get("applied"):
        return redirect("/review")
    statuses = [
        "Preparing Windows file sharing settings...",
        "Checking the selected folder...",
        "Creating the private share preview...",
        "Preparing connection instructions...",
    ]
    return templates.TemplateResponse(
        "apply.html",
        context(request, "Apply", statuses=statuses),
    )


@app.post("/apply")
def finish_apply():
    return redirect("/done")


@app.get("/done")
def done(request: Request):
    state = wizard_state(request)
    share_name = state.get("share_name") or "Backups"
    windows_path = f"\\\\{MOCK_SYSTEM['ip_address']}\\{share_name}"
    return templates.TemplateResponse(
        "done.html",
        context(request, "Done", windows_path=windows_path),
    )
