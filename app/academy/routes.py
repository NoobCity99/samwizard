from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.academy.progress import (
    AcademyProgressError,
    complete_skill,
    load_or_create_progress,
    open_skill,
    reset_progress,
    serialize_state,
)
from app.academy.tree import load_tree


router = APIRouter(prefix="/academy", tags=["academy"])
templates = Jinja2Templates(directory="app/templates")
STATIC_DIR = Path("app/static")
ACADEMY_ASSET_DIR = STATIC_DIR / "assets" / "academy"


def academy_assets() -> dict[str, dict[str, str | bool]]:
    banner_filename = "academy_banner.png"
    return {
        "banner": {
            "filename": banner_filename,
            "ratio": "1920x631",
            "src": f"/assets/academy/{banner_filename}",
            "exists": (ACADEMY_ASSET_DIR / banner_filename).is_file(),
        }
    }


def academy_state() -> dict[str, Any]:
    tree = load_tree()
    progress = load_or_create_progress(tree)
    return serialize_state(tree, progress)


@router.get("")
def academy_page(request: Request):
    return templates.TemplateResponse(
        "academy.html",
        {
            "request": request,
            "assets": academy_assets(),
        },
    )


@router.get("/api/state")
def get_academy_state():
    return JSONResponse(academy_state())


@router.post("/api/skills/{skill_id}/open")
def open_academy_skill(skill_id: str):
    tree = load_tree()
    try:
        progress = open_skill(tree, skill_id)
    except AcademyProgressError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(serialize_state(tree, progress))


@router.post("/api/skills/{skill_id}/complete")
def complete_academy_skill(skill_id: str):
    tree = load_tree()
    try:
        progress = complete_skill(tree, skill_id)
    except AcademyProgressError as exc:
        message = str(exc)
        status_code = 403 if "prerequisite" in message else 404
        raise HTTPException(status_code=status_code, detail=message) from exc
    return JSONResponse(serialize_state(tree, progress))


@router.post("/api/progress/reset")
def reset_academy_progress(payload: dict[str, str] | None = Body(default=None)):
    tree = load_tree()
    try:
        progress = reset_progress(tree, (payload or {}).get("confirm", ""))
    except AcademyProgressError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(serialize_state(tree, progress))
