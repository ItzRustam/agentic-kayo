"""Tests for user profile storage."""

import json
import tempfile
import unittest
from pathlib import Path
from src.storage.user_info import (
    load_user_info,
    save_user_info,
    update_profile_sender,
    SAFE_DEFAULT_USER_INFO,
)


class TestUserProfile(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.profile_path = Path(self.temp_dir.name) / "user_info.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_missing_file_returns_default(self):
        data = load_user_info(self.profile_path)
        self.assertEqual(data, SAFE_DEFAULT_USER_INFO)

    def test_load_malformed_json_returns_default(self):
        self.profile_path.write_text("{invalid json", encoding="utf-8")
        data = load_user_info(self.profile_path)
        self.assertEqual(data, SAFE_DEFAULT_USER_INFO)

    def test_save_and_load_profile(self):
        to_save = {
            "profile": {"name": "Alice", "email": "alice@example.com"},
            "preferences": ["dark_mode"],
            "context": {"role": "developer"},
        }
        save_user_info(to_save, self.profile_path)
        loaded = load_user_info(self.profile_path)
        self.assertEqual(loaded["profile"]["name"], "Alice")
        self.assertEqual(loaded["profile"]["email"], "alice@example.com")
        self.assertEqual(loaded["preferences"], ["dark_mode"])

    def test_strip_secrets_on_save(self):
        leaked = {
            "profile": {"name": "Bob", "email": "bob@example.com", "password": "supersecret"},
            "mail_password": "mypassword",
            "api_key": "12345",
        }
        save_user_info(leaked, self.profile_path)
        loaded = load_user_info(self.profile_path)
        self.assertNotIn("password", loaded["profile"])
        self.assertNotIn("mail_password", loaded)
        self.assertNotIn("api_key", loaded)

    def test_update_profile_sender(self):
        update_profile_sender("Charlie", "charlie@example.com", self.profile_path)
        loaded = load_user_info(self.profile_path)
        self.assertEqual(loaded["profile"]["name"], "Charlie")
        self.assertEqual(loaded["profile"]["email"], "charlie@example.com")


if __name__ == "__main__":
    unittest.main()
