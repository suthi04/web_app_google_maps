import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from device_identity import is_valid_token, new_token, owner_id_from_token


class TestDeviceIdentity(unittest.TestCase):
    def test_generated_token_is_valid_and_owner_id_is_stable(self):
        token = new_token()
        self.assertTrue(is_valid_token(token))
        self.assertEqual(owner_id_from_token(token), owner_id_from_token(token))
        self.assertTrue(owner_id_from_token(token).startswith("device:"))

    def test_different_tokens_have_different_owner_ids(self):
        self.assertNotEqual(
            owner_id_from_token("a" * 64), owner_id_from_token("b" * 64)
        )

    def test_invalid_tokens_are_rejected(self):
        for token in (None, "", "short", "z" * 64, "a" * 65):
            with self.subTest(token=token):
                self.assertFalse(is_valid_token(token))
                with self.assertRaises(ValueError):
                    owner_id_from_token(token)


if __name__ == "__main__":
    unittest.main()
