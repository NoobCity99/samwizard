import json
import os
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import patch

if find_spec("fastapi") is None:
    raise unittest.SkipTest("FastAPI is not installed in this Python environment.")

from fastapi import HTTPException

from app.academy.progress import (
    AcademyProgressError,
    complete_skill,
    initial_progress,
    load_progress,
    reset_progress,
    save_progress,
)
from app.academy.routes import (
    academy_page,
    complete_academy_skill,
    get_academy_state,
    open_academy_skill,
    reset_academy_progress,
)
from app.academy.tree import TreeValidationError, load_tree, starting_skill_ids, validate_tree


class FakeRequest:
    headers = {}

    def url_for(self, name, **path_params):
        if name == "static":
            return f"/static{path_params.get('path', '')}"
        return f"/{name}"


def temp_tree_path(payload):
    path = Path(tempfile.mkdtemp()) / "tree.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def minimal_tree():
    return {
        "id": "test_tree",
        "title": "Test Tree",
        "skills": [
            {
                "id": "start",
                "title": "Start",
                "summary": "Start here.",
                "map": {"row": 0, "col": 0},
                "starts_unlocked": True,
                "unlocks": ["next"],
                "lesson": {"intro": [], "commands": [], "exercise": "Try it."},
            },
            {
                "id": "next",
                "title": "Next",
                "summary": "Follow-up.",
                "map": {"row": 1, "col": 0},
                "starts_unlocked": False,
                "unlocks": [],
                "lesson": {"intro": [], "commands": [], "exercise": "Try it."},
            },
        ],
    }


class AcademyTreeTests(unittest.TestCase):
    def test_default_tree_loads_with_three_starter_skills(self):
        tree = load_tree()

        self.assertEqual(tree["id"], "ubuntu_cli_basics")
        self.assertEqual(len(tree["skills"]), 12)
        self.assertNotIn("graduation", {skill["id"] for skill in tree["skills"]})
        self.assertEqual(
            starting_skill_ids(tree),
            ["ubuntu-server", "terminal-basics", "server-identity"],
        )

    def test_default_tree_has_static_honeycomb_slots(self):
        tree = load_tree()
        layout_by_id = {skill["id"]: skill["layout"] for skill in tree["skills"]}

        self.assertEqual(layout_by_id["ubuntu-server"]["slot"], "top-left")
        self.assertEqual(layout_by_id["terminal-basics"]["slot"], "top-center")
        self.assertEqual(layout_by_id["server-identity"]["slot"], "top-right")
        self.assertEqual(layout_by_id["linux-filesystem"]["slot"], "upper-left")
        self.assertEqual(layout_by_id["networking-basics"]["slot"], "upper-right")
        self.assertEqual(layout_by_id["drives-and-mounts"]["slot"], "far-left")
        self.assertEqual(layout_by_id["tailscale-basics"]["slot"], "far-right")
        self.assertEqual(layout_by_id["samba-basics"]["slot"], "bottom-center")

    def test_duplicate_skill_ids_are_rejected(self):
        tree = minimal_tree()
        duplicate = dict(tree["skills"][0])
        tree["skills"].append(duplicate)

        with self.assertRaises(TreeValidationError):
            validate_tree(tree)

    def test_invalid_layout_metadata_is_rejected(self):
        tree = minimal_tree()
        tree["skills"][0]["layout"] = {"rank": -1, "lane": 0}

        with self.assertRaises(TreeValidationError):
            validate_tree(tree)

    def test_invalid_layout_slot_is_rejected(self):
        tree = minimal_tree()
        tree["skills"][0]["layout"] = {"slot": "unknown-slot"}

        with self.assertRaises(TreeValidationError):
            validate_tree(tree)

    def test_missing_unlock_targets_are_rejected(self):
        tree = minimal_tree()
        tree["skills"][0]["unlocks"] = ["missing-skill"]

        with self.assertRaises(TreeValidationError):
            validate_tree(tree)


class AcademyProgressTests(unittest.TestCase):
    def test_complete_skill_unlocks_direct_children(self):
        tree = minimal_tree()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "academy-progress.json"

            progress = complete_skill(tree, "start", path)

            self.assertEqual(progress["completed_skill_ids"], ["start"])
            self.assertEqual(progress["unlocked_skill_ids"], ["start", "next"])

    def test_locked_skill_completion_is_rejected(self):
        tree = minimal_tree()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "academy-progress.json"

            with self.assertRaises(AcademyProgressError):
                complete_skill(tree, "next", path)

    def test_missing_and_corrupt_progress_falls_back_to_initial_state(self):
        tree = minimal_tree()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "academy-progress.json"

            missing = load_progress(tree, path)
            self.assertEqual(missing["unlocked_skill_ids"], ["start"])

            path.write_text("not json", encoding="utf-8")
            corrupt = load_progress(tree, path)
            self.assertEqual(corrupt["completed_skill_ids"], [])
            self.assertEqual(corrupt["unlocked_skill_ids"], ["start"])

    def test_save_progress_writes_complete_json_file(self):
        tree = minimal_tree()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "academy-progress.json"
            progress = initial_progress(tree)

            save_progress(progress, path)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), progress)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_reset_progress_requires_confirmation(self):
        tree = minimal_tree()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "academy-progress.json"

            with self.assertRaises(AcademyProgressError):
                reset_progress(tree, "reset", path)

            progress = reset_progress(tree, "RESET", path)
            self.assertEqual(progress["completed_skill_ids"], [])
            self.assertEqual(progress["unlocked_skill_ids"], ["start"])


class AcademyRouteTests(unittest.TestCase):
    def test_academy_page_renders_banner_slot_and_workspace(self):
        response = academy_page(FakeRequest())
        body = " ".join(response.body.decode().split())

        self.assertEqual(response.status_code, 200)
        self.assertIn("SamWizard Academy", body)
        self.assertIn("academy_banner.png", body)
        self.assertIn("academy-workspace", body)
        self.assertIn("academy-map-logo", body)
        self.assertIn("layoutStaticHoneycomb", body)
        self.assertIn("bridgeLine", body)

    def test_state_endpoint_returns_tree_and_creates_progress_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"SAMWIZARD_STATE_DIR": directory}, clear=False):
                response = get_academy_state()
                payload = json.loads(response.body.decode())

            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["tree"]["id"], "ubuntu_cli_basics")
            self.assertEqual(
                payload["progress"]["unlocked_skill_ids"],
                ["ubuntu-server", "terminal-basics", "server-identity"],
            )
            ubuntu_server = next(skill for skill in payload["skills"] if skill["id"] == "ubuntu-server")
            self.assertEqual(ubuntu_server["layout"], {"slot": "top-left", "group": "basics"})
            self.assertTrue((Path(directory) / "academy-progress.json").exists())

    def test_open_and_complete_endpoints_update_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"SAMWIZARD_STATE_DIR": directory}, clear=False):
                open_response = open_academy_skill("ubuntu-server")
                complete_response = complete_academy_skill("ubuntu-server")
                payload = json.loads(complete_response.body.decode())

            self.assertEqual(open_response.status_code, 200)
            self.assertEqual(complete_response.status_code, 200)
            self.assertIn("ubuntu-server", payload["progress"]["completed_skill_ids"])
            self.assertIn("linux-filesystem", payload["progress"]["unlocked_skill_ids"])

    def test_top_row_completion_unlocks_static_children(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"SAMWIZARD_STATE_DIR": directory}, clear=False):
                terminal_response = complete_academy_skill("terminal-basics")
                terminal_payload = json.loads(terminal_response.body.decode())
                server_response = complete_academy_skill("server-identity")
                server_payload = json.loads(server_response.body.decode())

        self.assertIn("navigation-basics", terminal_payload["progress"]["unlocked_skill_ids"])
        self.assertIn("reading-output", terminal_payload["progress"]["unlocked_skill_ids"])
        self.assertIn("networking-basics", server_payload["progress"]["unlocked_skill_ids"])

    def test_complete_endpoint_rejects_locked_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"SAMWIZARD_STATE_DIR": directory}, clear=False):
                with self.assertRaises(HTTPException) as caught:
                    complete_academy_skill("linux-filesystem")

        self.assertEqual(caught.exception.status_code, 403)

    def test_reset_endpoint_requires_reset_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"SAMWIZARD_STATE_DIR": directory}, clear=False):
                with self.assertRaises(HTTPException) as caught:
                    reset_academy_progress({"confirm": "NO"})
                response = reset_academy_progress({"confirm": "RESET"})
                payload = json.loads(response.body.decode())

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(payload["progress"]["completed_skill_ids"], [])


if __name__ == "__main__":
    unittest.main()
