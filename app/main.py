from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.command_log import (
    add_log_entry,
    clear_command_log,
    command_log_id_from_state,
    command_log_from_state,
    logged_command_runner,
    logged_detection_runner,
)
from app.share_targets import (
    drive_diagnostics,
    has_eligible_drive,
    safe_name,
    selected_location_from,
    share_locations,
)
from app.settings import session_secret_key
from app.system_actions import apply_share_setup
from app.system_checks import system_checks_from_info, system_summary as build_system_summary
from app.system_info import detect_internet_connectivity, detect_system_info
from app.wifi_actions import apply_wifi_setup


app = FastAPI(title="Samba Wizard")
app.add_middleware(SessionMiddleware, secret_key=session_secret_key())
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


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


def selected_location(state: dict[str, Any]) -> dict[str, Any] | None:
    location = state.get("selected_location")
    if isinstance(location, dict):
        return location
    return None


def system_checks_for_request(request: Request) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    state = wizard_state(request)
    system_info = detect_system_info(
        command_runner=logged_detection_runner(state),
        internet_detector=lambda: logged_internet_check(state),
    )
    return system_checks_from_info(system_info), system_info


def logged_internet_check(state: dict[str, Any]) -> dict[str, Any]:
    internet = detect_internet_connectivity()
    add_log_entry(
        state,
        phase="System Check",
        command="Python internet connectivity check",
        exit_code=0 if internet.get("connected") else 1,
        summary=internet.get("message") or "Internet check completed.",
    )
    return internet


def unresolved_critical_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        check
        for check in checks
        if check["critical"] and check["status"] == "needs_attention"
    ]


def system_check_state(request: Request) -> dict[str, Any]:
    state = wizard_state(request)
    checks = state.setdefault("system_checks", {})
    if not isinstance(checks, dict):
        checks = {}
    checks.setdefault("wifi", {})
    checks.setdefault("show_wifi", False)
    state["system_checks"] = checks
    request.session["wizard"] = state
    return checks


def system_check_page(
    request: Request,
    error: str | None = None,
    wifi_error: str | None = None,
):
    checks, system_info = system_checks_for_request(request)
    critical_unresolved = unresolved_critical_checks(checks)
    check_state = system_check_state(request)
    wifi_state = check_state.get("wifi", {})
    wifi_results = check_state.get("wifi_results", [])
    show_wifi = bool(check_state.get("show_wifi"))
    internet_connected = bool(system_info.get("internet", {}).get("connected"))

    return templates.TemplateResponse(
        "system_check.html",
        context(
            request,
            "System Check",
            checks=checks,
            critical_unresolved=critical_unresolved,
            system=system_summary(system_info),
            error=error,
            wifi_error=wifi_error,
            wifi_state=wifi_state,
            show_wifi=show_wifi,
            internet_connected=internet_connected,
            wifi_results=wifi_results,
        ),
    )


def system_summary(system_info: dict[str, Any] | None = None) -> dict[str, str]:
    if system_info is None:
        system_info = detect_system_info()
    return build_system_summary(system_info)


def context(request: Request, step: str, **extra: Any) -> dict[str, Any]:
    state = wizard_state(request)
    command_log_id_from_state(state)
    system = extra.pop("system", None) or system_summary()
    base = {
        "request": request,
        "step": step,
        "steps": STEP_ORDER,
        "step_index": STEP_ORDER.index(step) + 1,
        "step_count": len(STEP_ORDER),
        "state": state,
        "system": system,
        "selected_location": selected_location(state),
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
def system_check(request: Request, wifi: str | None = None):
    if wifi == "show":
        check_state = system_check_state(request)
        check_state["show_wifi"] = True
        state = wizard_state(request)
        state["system_checks"] = check_state
        request.session["wizard"] = state
    return system_check_page(request)


@app.post("/system-check")
def system_check_next(request: Request):
    checks, _system_info = system_checks_for_request(request)
    if unresolved_critical_checks(checks):
        return system_check_page(
            request,
            error="Resolve the critical checks before continuing.",
        )
    return redirect("/drive-selection")


@app.post("/system-check/wifi-preview")
def wifi_preview(
    request: Request,
    wifi_interface: str = Form(""),
    wifi_ssid: str = Form(""),
    wifi_password: str = Form(""),
):
    clean_interface = wifi_interface.strip()
    clean_ssid = wifi_ssid.strip()
    check_state = system_check_state(request)
    check_state["show_wifi"] = True
    state = wizard_state(request)
    state["system_checks"] = check_state
    request.session["wizard"] = state

    if not clean_interface:
        return system_check_page(request, wifi_error="Enter the Wi-Fi adapter name.")
    if not clean_ssid:
        return system_check_page(request, wifi_error="Enter the Wi-Fi network name.")
    if not wifi_password:
        return system_check_page(request, wifi_error="Enter the Wi-Fi password.")

    results = apply_wifi_setup(
        state,
        interface=clean_interface,
        ssid=clean_ssid,
        password=wifi_password,
        command_runner=logged_command_runner(state, "Wi-Fi Setup"),
        internet_checker=detect_internet_connectivity,
    )
    check_state["wifi"] = {
        "interface": clean_interface,
        "ssid": clean_ssid,
        "password_provided": True,
    }
    check_state["wifi_results"] = results
    state["system_checks"] = check_state
    request.session["wizard"] = state

    if all(result["status"] == "passed" for result in results):
        return redirect("/system-check")
    return system_check_page(
        request,
        wifi_error="Wi-Fi setup stopped before finishing. Review the failed step below.",
    )


@app.get("/drive-selection")
def drive_selection(request: Request):
    state = wizard_state(request)
    system_info = detect_system_info(command_runner=logged_detection_runner(state))
    return templates.TemplateResponse(
        "drive_selection.html",
        context(
            request,
            "Drive Selection",
            locations=share_locations(system_info),
            drive_diagnostics=drive_diagnostics(system_info),
            has_eligible_drive=has_eligible_drive(system_info),
            system=system_summary(system_info),
            error=None,
        ),
    )


@app.post("/drive-selection")
def save_drive_selection(request: Request, location_id: str = Form("")):
    state = wizard_state(request)
    system_info = detect_system_info(command_runner=logged_detection_runner(state))
    location = selected_location_from(location_id, system_info)
    if location is None:
        return templates.TemplateResponse(
            "drive_selection.html",
            context(
                request,
                "Drive Selection",
                locations=share_locations(system_info),
                drive_diagnostics=drive_diagnostics(system_info),
                has_eligible_drive=has_eligible_drive(system_info),
                system=system_summary(system_info),
                error="Choose a drive or folder to continue.",
            ),
            status_code=400,
        )

    state["location_id"] = location_id
    state["selected_location"] = location
    request.session["wizard"] = state
    return redirect("/share-name")


@app.get("/share-name")
def share_name(request: Request):
    if selected_location(wizard_state(request)) is None:
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
):
    clean_username = username.strip()
    if not clean_username:
        error = "Enter a username for the private share."
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
    state.pop("password_confirmed", None)
    request.session["wizard"] = state
    return redirect("/review")


@app.get("/review")
def review(request: Request):
    state = wizard_state(request)
    if selected_location(state) is None:
        return redirect("/drive-selection")
    if not state.get("share_name"):
        return redirect("/share-name")
    if not state.get("username"):
        return redirect("/user-setup")

    return templates.TemplateResponse("review.html", context(request, "Review"))


@app.post("/review")
def confirm_review(request: Request):
    state = wizard_state(request)
    state["reviewed"] = True
    state.pop("apply_results", None)
    request.session["wizard"] = state
    return redirect("/apply")


@app.get("/apply")
def apply_setup(request: Request):
    if not wizard_state(request).get("reviewed"):
        return redirect("/review")
    return templates.TemplateResponse(
        "apply.html",
        context(request, "Apply", results=wizard_state(request).get("apply_results", []), error=None),
    )


@app.post("/apply")
def run_apply(
    request: Request,
    samba_password: str = Form(""),
    confirm_samba_password: str = Form(""),
):
    state = wizard_state(request)
    if not state.get("reviewed"):
        return redirect("/review")
    if not samba_password:
        return templates.TemplateResponse(
            "apply.html",
            context(request, "Apply", results=state.get("apply_results", []), error="Enter the Windows share password."),
            status_code=400,
        )
    if samba_password != confirm_samba_password:
        return templates.TemplateResponse(
            "apply.html",
            context(request, "Apply", results=state.get("apply_results", []), error="The passwords do not match."),
            status_code=400,
        )

    location = selected_location(state)
    if location is None or not state.get("share_name") or not state.get("username"):
        return redirect("/review")

    results = apply_share_setup(
        location=location,
        share_name=state["share_name"],
        username=state["username"],
        password=samba_password,
        command_runner=logged_command_runner(state, "Apply"),
    )
    state["selected_location"] = location
    state["apply_results"] = results
    state["applied"] = all(result["status"] == "passed" for result in results)
    request.session["wizard"] = state

    if state["applied"]:
        return redirect("/done")
    return templates.TemplateResponse(
        "apply.html",
        context(request, "Apply", results=results, error="Setup stopped before finishing. Review the failed step below."),
        status_code=400,
    )


@app.post("/command-log/clear")
def clear_log(request: Request):
    state = wizard_state(request)
    clear_command_log(state)
    request.session["wizard"] = state
    referer = request.headers.get("referer") if hasattr(request, "headers") else None
    return redirect(referer or "/system-check")


@app.get("/logs")
def logs_page(request: Request):
    state = wizard_state(request)
    return templates.TemplateResponse(
        "logs.html",
        {
            "request": request,
            "command_log": command_log_from_state(state),
        },
    )


@app.get("/logs/data")
def logs_data(request: Request):
    state = wizard_state(request)
    return JSONResponse({"entries": command_log_from_state(state)})


@app.get("/done")
def done(request: Request):
    state = wizard_state(request)
    if not state.get("applied"):
        return redirect("/apply")
    share_name = safe_name(state.get("share_name") or "Backups")
    system = system_summary()
    windows_path = f"\\\\{system['ip_address']}\\{share_name}"
    return templates.TemplateResponse(
        "done.html",
        context(request, "Done", windows_path=windows_path),
    )
