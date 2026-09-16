from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from feishu_bot.state import BotStateStore


class BotStateStoreTests(unittest.TestCase):
    def test_favorites_are_idempotent_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.sqlite3"
            store = BotStateStore(path)
            self.assertTrue(store.add_favorite("user-a", 6))
            self.assertFalse(store.add_favorite("user-a", 6))
            self.assertTrue(store.is_favorite("user-a", 6))
            self.assertEqual(store.favorite_ids("user-a"), [6])

            reopened = BotStateStore(path)
            self.assertTrue(reopened.is_favorite("user-a", 6))
            self.assertTrue(reopened.remove_favorite("user-a", 6))
            self.assertFalse(reopened.is_favorite("user-a", 6))

    def test_last_reveal_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = BotStateStore(Path(temp_dir) / "state.sqlite3")
            store.remember_reveal("user-a", 3)
            store.remember_reveal("user-a", 8)
            self.assertEqual(store.last_reveal("user-a"), 8)


if __name__ == "__main__":
    unittest.main()
