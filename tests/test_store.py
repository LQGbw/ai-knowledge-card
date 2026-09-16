import tempfile
import unittest
from pathlib import Path

from podcast_collector.models import CardDraft, Episode, Podcast
from podcast_collector.store import Store


class StoreTests(unittest.TestCase):
    def test_episode_is_new_then_unchanged_then_updated(self) -> None:
        podcast = Podcast(
            id="example",
            name="Example",
            platform_url="https://example.com",
            feed_url="https://example.com/feed.xml",
        )
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "test.sqlite3")
            try:
                store.upsert_podcast(podcast)
                first = Episode(guid="one", title="First", show_notes="Original")
                self.assertEqual(store.upsert_episode(podcast.id, first), "new")
                self.assertEqual(store.upsert_episode(podcast.id, first), "unchanged")
                changed = Episode(guid="one", title="First", show_notes="Updated")
                self.assertEqual(store.upsert_episode(podcast.id, changed), "updated")
            finally:
                store.close()

    def test_card_requires_and_preserves_episode_source(self) -> None:
        podcast = Podcast(
            id="example",
            name="Example",
            platform_url="https://example.com",
            feed_url="https://example.com/feed.xml",
        )
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "test.sqlite3")
            try:
                store.upsert_podcast(podcast)
                store.upsert_episode(podcast.id, Episode(guid="one", title="Harness"))
                episode_id = store.connection.execute("SELECT id FROM episodes").fetchone()[0]
                card = CardDraft(
                    term="Harness",
                    aliases=[],
                    one_line_definition="智能体编排层",
                    why_it_matters="控制多步执行",
                    maturity_status="emerging",
                    uncertainty_note="定义仍在变化",
                    confidence="medium",
                    source_episode_ids=[episode_id],
                )
                card_id = store.save_card_draft(card, "test-model", "test-prompt")
                source_count = store.connection.execute(
                    "SELECT COUNT(*) FROM card_sources WHERE card_id=?", (card_id,)
                ).fetchone()[0]
                self.assertEqual(source_count, 1)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
