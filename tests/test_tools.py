import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nook.tools import (
    ExplainErrorTool,
    OrganizeFilesTool,
    RunCommandTool,
    parse_action_input,
)


class RunCommandToolTests(unittest.TestCase):
    def test_destructive_command_requires_confirmation_before_execution(self):
        tool = RunCommandTool(".")
        with patch("nook.tools.subprocess.run") as run:
            result = tool.run({"command": "rm -rf /tmp/nook-test"})

        self.assertTrue(result.requires_confirmation)
        run.assert_not_called()

    def test_confirmed_destructive_command_executes(self):
        tool = RunCommandTool(".")
        completed = subprocess.CompletedProcess("rm", 0, stdout="", stderr="")
        with patch("nook.tools.subprocess.run", return_value=completed) as run:
            result = tool.run({"command": "rm -f test-file"}, confirmed=True)

        self.assertTrue(result.success)
        run.assert_called_once()

    def test_rejects_non_boolean_background_value(self):
        result = RunCommandTool(".").run({"command": "echo hi", "background": "yes"})

        self.assertFalse(result.success)
        self.assertIn("background", result.output)

    def test_api_keys_are_not_inherited_by_shell_commands(self):
        completed = subprocess.CompletedProcess("echo hi", 0, stdout="hi", stderr="")
        tool = RunCommandTool(".")
        with patch.dict(
            os.environ,
            {"META_API_KEY": "test-meta-key", "MODEL_API_KEY": "legacy-key"},
        ):
            with patch("nook.tools.subprocess.run", return_value=completed) as run:
                tool.run({"command": "echo hi"})

        child_environment = run.call_args.kwargs["env"]
        self.assertNotIn("META_API_KEY", child_environment)
        self.assertNotIn("MODEL_API_KEY", child_environment)


class OrganizeFilesToolTests(unittest.TestCase):
    def test_first_call_is_a_dry_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir, "notes.txt")
            source.write_text("notes", encoding="utf-8")

            result = OrganizeFilesTool(temp_dir).run({"path": temp_dir})

            self.assertTrue(result.requires_confirmation)
            self.assertTrue(source.exists())
            self.assertIn("notes.txt -> Documents/notes.txt", result.output)

    def test_files_move_only_after_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir, "photo.png")
            target = Path(temp_dir, "Images", "photo.png")
            source.write_bytes(b"image")
            tool = OrganizeFilesTool(temp_dir)

            preview = tool.run({"path": temp_dir})
            result = tool.run({"path": temp_dir}, confirmed=True)

            self.assertTrue(preview.requires_confirmation)
            self.assertFalse(source.exists())
            self.assertEqual(target.read_bytes(), b"image")
            self.assertTrue(result.success)

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir, "photo.png")
            target = Path(temp_dir, "Images", "photo.png")
            target.parent.mkdir()
            source.write_bytes(b"new")
            target.write_bytes(b"existing")

            result = OrganizeFilesTool(temp_dir).run({"path": temp_dir}, confirmed=True)

            self.assertFalse(result.success)
            self.assertTrue(source.exists())
            self.assertEqual(target.read_bytes(), b"existing")


class OtherToolTests(unittest.TestCase):
    def test_explain_error_gives_offline_python_fix(self):
        result = ExplainErrorTool().run(
            {"error": "ModuleNotFoundError: No module named 'yaml'"},
        )

        self.assertTrue(result.success)
        self.assertIn("pip install yaml", result.output)

    def test_action_input_accepts_python_literal_dict(self):
        self.assertEqual(parse_action_input("{'path': '/tmp'}"), {"path": "/tmp"})

    def test_action_input_rejects_non_object(self):
        with self.assertRaises(ValueError):
            parse_action_input("rm -rf /")


if __name__ == "__main__":
    unittest.main()
