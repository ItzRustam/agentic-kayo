"""Unit tests for all tools and the tool registry."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.tools.files import (
    create_file,
    delete_file,
    edit_file,
    list_files,
    read_file,
    search_files,
)
from src.tools.open_website import open_website
from src.tools.python_execution import run_python_code, run_python_file
from src.tools.registry import ToolRegistry, default_registry
from src.tools.send_mail import prepare_mail_preview
from src.tools.utilities import calculate, get_current_datetime


class TestUtilities(unittest.TestCase):
    def test_calculate_valid_expressions(self):
        cases = [
            ("2 + 2", 4),
            ("(10 - 3) * 4", 28),
            ("15 / 3", 5.0),
            ("17 // 3", 5),
            ("10 % 3", 1),
            ("2 ** 5", 32),
            ("-5 + 10", 5),
        ]
        for expr, expected in cases:
            res = calculate(expr)
            self.assertTrue(res["ok"], f"Failed on {expr}: {res.get('error')}")
            self.assertEqual(res["result"]["value"], expected)

    def test_calculate_division_by_zero(self):
        res = calculate("5 / 0")
        self.assertFalse(res["ok"])
        self.assertIn("Division by zero", res["error"])

    def test_calculate_security_rejections(self):
        bad_expressions = [
            "__import__('os').system('ls')",
            "open('/etc/passwd').read()",
            "eval('2 + 2')",
            "x = 5",
            "[x for x in range(10)]",
            "2 ** 10000",  # huge exponent
        ]
        for expr in bad_expressions:
            res = calculate(expr)
            self.assertFalse(res["ok"], f"Should have rejected '{expr}'")

    def test_get_current_datetime(self):
        res = get_current_datetime()
        self.assertTrue(res["ok"])
        self.assertIn("readable", res["result"])
        self.assertIn("iso", res["result"])
        self.assertIn("timezone", res["result"])


class TestOpenWebsite(unittest.TestCase):
    def test_valid_urls(self):
        valid = ["https://example.com", "http://docs.python.org/3/library"]
        for u in valid:
            res = open_website(u)
            self.assertTrue(res["ok"], f"Expected ok for {u}: {res.get('error')}")
            self.assertEqual(res["result"]["url"], u)

    def test_invalid_and_unsafe_urls(self):
        invalid = [
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:text/plain;base64,SGVsbG8=",
            "ftp://example.com",
            "https://user:password@example.com",
            "",
            "not a url",
        ]
        for u in invalid:
            res = open_website(u)
            self.assertFalse(res["ok"], f"Should have rejected: {u}")


class TestFileTools(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ws = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_read_file(self):
        res = create_file("hello.txt", "Hello World!", workspace_root=self.ws)
        self.assertTrue(res["ok"], res.get("error"))

        read_res = read_file("hello.txt", workspace_root=self.ws)
        self.assertTrue(read_res["ok"])
        self.assertEqual(read_res["result"]["content"], "Hello World!")

    def test_prevent_accidental_overwrite(self):
        create_file("test.txt", "initial", workspace_root=self.ws)
        # Without overwrite=True, must fail
        res2 = create_file("test.txt", "new content", overwrite=False, workspace_root=self.ws)
        self.assertFalse(res2["ok"])

        # With overwrite=True, succeeds
        res3 = create_file("test.txt", "new content", overwrite=True, workspace_root=self.ws)
        self.assertTrue(res3["ok"])

    def test_path_traversal_prevention(self):
        bad_paths = [
            "../secret.txt",
            "../../etc/passwd",
            "/etc/passwd",
            ".env",
            ".git/config",
        ]
        for p in bad_paths:
            res = create_file(p, "data", workspace_root=self.ws)
            self.assertFalse(res["ok"], f"Expected failure for path traversal '{p}'")

    def test_edit_file_exact_and_ambiguous(self):
        create_file("code.py", "a = 1\nb = 2\na = 1\n", workspace_root=self.ws)

        # Ambiguous match (appears twice)
        amb_res = edit_file("code.py", "a = 1", "a = 99", workspace_root=self.ws)
        self.assertFalse(amb_res["ok"])
        self.assertIn("Ambiguous", amb_res["error"])

        # Unambiguous match
        ok_res = edit_file("code.py", "b = 2", "b = 42", workspace_root=self.ws)
        self.assertTrue(ok_res["ok"])
        self.assertIn("+b = 42", ok_res["result"]["diff"])

    def test_list_and_search_files(self):
        create_file("dir1/sample.txt", "searching for needle in haystack", workspace_root=self.ws)
        create_file("dir2/other.txt", "nothing here", workspace_root=self.ws)

        listed = list_files("dir1", workspace_root=self.ws)
        self.assertTrue(listed["ok"])
        self.assertEqual(listed["result"]["count"], 1)

        searched = search_files("needle", workspace_root=self.ws)
        self.assertTrue(searched["ok"])
        self.assertEqual(len(searched["result"]["matches"]), 1)
        self.assertEqual(searched["result"]["matches"][0]["path"], "dir1/sample.txt")

    def test_delete_file(self):
        create_file("to_delete.txt", "temporary", workspace_root=self.ws)
        del_res = delete_file("to_delete.txt", workspace_root=self.ws)
        self.assertTrue(del_res["ok"])
        self.assertFalse((self.ws / "to_delete.txt").exists())


class TestPythonExecution(unittest.TestCase):
    def test_run_python_code_simple(self):
        code = "print(123 + 456)"
        res = run_python_code(code)
        self.assertTrue(res["ok"], res.get("error"))
        self.assertIn("579", res["result"]["stdout"])
        self.assertEqual(res["result"]["exit_code"], 0)

    def test_run_python_code_syntax_error(self):
        code = "def broken(:"
        res = run_python_code(code)
        self.assertTrue(res["ok"])
        self.assertNotEqual(res["result"]["exit_code"], 0)
        self.assertIn("SyntaxError", res["result"]["stderr"])


class TestRegistryAndConfirmation(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()

    def test_all_14_tools_registered(self):
        specs = self.registry.list_tool_specs()
        names = {s.name for s in specs}
        expected = {
            "web_search",
            "search_wikipedia",
            "open_website",
            "create_file",
            "read_file",
            "edit_file",
            "list_files",
            "search_files",
            "delete_file",
            "run_python_code",
            "run_python_file",
            "calculate",
            "get_current_datetime",
            "send_mail",
        }
        self.assertEqual(names, expected)

    def test_confirmation_required_for_gated_tools(self):
        # delete_file should require confirmation
        del_attempt = self.registry.dispatch("delete_file", {"path": "some.txt"}, bypass_confirmation=False)
        self.assertFalse(del_attempt["ok"])
        self.assertTrue(del_attempt.get("requires_confirmation"))

        # run_python_code should require confirmation
        run_attempt = self.registry.dispatch("run_python_code", {"code": "print(1)"}, bypass_confirmation=False)
        self.assertFalse(run_attempt["ok"])
        self.assertTrue(run_attempt.get("requires_confirmation"))

        # calculate does not require confirmation
        calc_attempt = self.registry.dispatch("calculate", {"expression": "10 * 5"})
        self.assertTrue(calc_attempt["ok"])
        self.assertEqual(calc_attempt["result"]["value"], 50)


if __name__ == "__main__":
    unittest.main()
