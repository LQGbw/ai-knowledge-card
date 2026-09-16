from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from feishu_bot.bot import _selected_number
from feishu_bot.content import CardCatalog, format_card, format_menu
from podcast_collector.models import CardDraft, Episode, Podcast
from podcast_collector.store import Store


class FeishuContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "cards.sqlite3"
        self.store = Store(self.database)
        self.store.upsert_podcast(
            Podcast(
                id="test-show",
                name="测试播客",
                platform_url="https://example.com/show",
                feed_url="https://example.com/feed.xml",
            )
        )
        self.store.upsert_episode(
            "test-show",
            Episode(
                guid="episode-1",
                title="Harness 如何影响 AI 产品",
                page_url="https://example.com/episode-1",
                published_at="2026-09-01T00:00:00Z",
                show_notes="讨论 Harness 和 Agent 产品的关系。",
            ),
        )
        episode_id = self.store.connection.execute(
            "SELECT id FROM episodes WHERE guid='episode-1'"
        ).fetchone()["id"]
        self.store.save_card_draft(
            CardDraft(
                term="Harness",
                aliases=["Agent Harness"],
                one_line_definition="围绕模型组织工具和执行循环的编排层。",
                why_it_matters="它决定一个 Agent 能否稳定完成任务。",
                maturity_status="emerging",
                uncertainty_note="行业对其边界仍有不同划分。",
                confidence="medium",
                source_episode_ids=[episode_id],
            ),
            model="fixture",
            prompt_version="test",
        )

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_daily_cards_are_stable_for_same_day_and_chat(self) -> None:
        catalog = CardCatalog(self.database)
        first = catalog.daily_cards("chat-a", date(2026, 9, 14))
        second = catalog.daily_cards("chat-a", date(2026, 9, 14))
        self.assertEqual([card.id for card in first], [card.id for card in second])

    def test_card_includes_evidence_and_learning_context(self) -> None:
        card = CardCatalog(self.database).all_cards()[0]
        rendered = format_card(card)
        self.assertIn("Harness", rendered)
        self.assertIn("认识边界", rendered)
        self.assertIn("测试播客｜Harness 如何影响 AI 产品", rendered)
        self.assertIn("https://example.com/episode-1", rendered)
        self.assertIn("Headless", rendered)

    def test_menu_uses_topic_hint_without_revealing_term(self) -> None:
        cards = CardCatalog(self.database).all_cards()
        rendered = format_menu(cards)
        self.assertIn("今天的 AI 六面骰", rendered)
        self.assertIn("模型之外的机关", rendered)
        self.assertNotIn("Harness", rendered)

    def test_number_parser_accepts_chinese_and_digit_forms(self) -> None:
        self.assertEqual(_selected_number("3"), 3)
        self.assertEqual(_selected_number("选六号"), 6)
        self.assertIsNone(_selected_number("7"))


if __name__ == "__main__":
    unittest.main()
