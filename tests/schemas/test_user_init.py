# tests/schemas/test_user_init.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from pydantic import ValidationError

from app.schemas.user_init import UserInitRequest, UserInitResponse


class TestUserInitRequest(unittest.TestCase):
    def test_accepts_master_password(self):
        data = UserInitRequest(master_password="Master-passphrase1")
        self.assertEqual(data.master_password, "Master-passphrase1")

    def test_rejects_extra_fields(self):
        with self.assertRaises(ValidationError):
            UserInitRequest(
                master_password="Master-passphrase1",
                extra="nope",
            )

    def test_requires_master_password(self):
        with self.assertRaises(ValidationError):
            UserInitRequest()


class TestUserInitResponse(unittest.TestCase):
    def test_accepts_credentials(self):
        data = UserInitResponse(
            user_id=1,
            username="root",
            access_key_id="AKIAEXAMPLE000001",
            secret_access_key="secret-value",
        )
        self.assertEqual(data.user_id, 1)
        self.assertEqual(data.username, "root")
        self.assertEqual(data.access_key_id, "AKIAEXAMPLE000001")
        self.assertEqual(data.secret_access_key, "secret-value")
