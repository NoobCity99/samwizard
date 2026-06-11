import unittest

from app.command_log import (
    LOG_ID_KEY,
    MAX_LOG_ENTRIES,
    MASKED_STDIN,
    add_log_entry,
    clear_command_log,
    command_log_id_from_state,
    command_log_from_state,
    logged_command_runner,
)
from app.system_actions import CommandResult


class CommandLogTests(unittest.TestCase):
    def test_add_log_entry_truncates_and_trims(self):
        state = {}
        for index in range(MAX_LOG_ENTRIES + 5):
            add_log_entry(
                state,
                phase="Test",
                command=["cmd", str(index)],
                exit_code=0,
                stdout="x" * 3000,
                summary="ok",
            )

        log = command_log_from_state(state)
        self.assertEqual(len(log), MAX_LOG_ENTRIES)
        self.assertEqual(log[0]["command"], "cmd 5")
        self.assertIn("output truncated", log[-1]["stdout"])
        self.assertIn(LOG_ID_KEY, state)
        self.assertNotIn("command_log", state)

    def test_clear_command_log_preserves_other_state(self):
        state = {"share_name": "Backups"}
        add_log_entry(state, phase="Test", command="note", exit_code=None)

        clear_command_log(state)

        self.assertEqual(command_log_from_state(state), [])
        self.assertEqual(state["share_name"], "Backups")

    def test_command_log_id_is_reused(self):
        state = {}
        first = command_log_id_from_state(state)
        second = command_log_id_from_state(state)

        self.assertEqual(first, second)
        self.assertEqual(state[LOG_ID_KEY], first)

    def test_old_cookie_log_is_migrated_out_of_session(self):
        state = {"command_log": [{"command": "hostname -I"}]}

        log = command_log_from_state(state)

        self.assertEqual(log[0]["command"], "hostname -I")
        self.assertIn(LOG_ID_KEY, state)
        self.assertNotIn("command_log", state)

    def test_logged_command_runner_masks_secret_stdin(self):
        state = {}

        def base_runner(args, input_text=None, env=None):
            return CommandResult(args=args, returncode=0, stdout="done", stderr="")

        runner = logged_command_runner(state, "Apply", base_runner=base_runner)
        result = runner(["smbpasswd", "-a", "-s", "sambauser"], "secret\nsecret\n", None)

        log = command_log_from_state(state)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(log[0]["stdin"], MASKED_STDIN)
        self.assertEqual(log[0]["summary"], "Starting command...")
        self.assertIsNone(log[0]["exit_code"])
        self.assertEqual(log[1]["stdin"], MASKED_STDIN)
        self.assertNotIn("secret", repr(state))
        self.assertNotIn("secret", repr(log))
        self.assertEqual(log[1]["stdout"], "done")

    def test_logged_command_runner_marks_timeout(self):
        state = {}

        def base_runner(args, input_text=None, env=None):
            return CommandResult(args=args, returncode=124, stderr="timed out", timed_out=True)

        runner = logged_command_runner(state, "Apply", base_runner=base_runner)
        result = runner(["mount", "/mnt/backups"], None, None)

        log = command_log_from_state(state)
        self.assertTrue(result.timed_out)
        self.assertEqual(log[0]["summary"], "Starting command...")
        self.assertEqual(log[1]["summary"], "Command timed out.")
        self.assertIn("timed out", log[1]["stderr"])


if __name__ == "__main__":
    unittest.main()
