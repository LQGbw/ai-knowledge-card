from __future__ import annotations

import unittest

from feishu_bot.cards import build_knowledge_card, build_menu_card, build_rolling_card
from feishu_bot.content import Card


def fixture_card() -> Card:
    return Card(
        id=6,
        term="Harness",
        aliases=("Agent Harness",),
        one_line_definition="围绕模型组织工具和执行循环的编排层。",
        why_it_matters="它决定 Agent 能否稳定完成任务。",
        maturity_status="emerging",
        uncertainty_note="行业对它的边界仍有不同划分。",
        confidence="medium",
        sources=(),
    )


class FeishuCardTests(unittest.TestCase):
    def test_menu_has_hints_number_buttons_and_dice(self) -> None:
        card = build_menu_card([fixture_card()])
        self.assertEqual(card["schema"], "2.0")
        rendered = str(card)
        self.assertIn("模型之外的机关", rendered)
        self.assertNotIn("Agent Harness", rendered)
        self.assertIn("'action': 'select'", rendered)
        self.assertIn("'action': 'dice'", rendered)

    def test_rolling_card_shows_selected_face_and_hint(self) -> None:
        card = build_rolling_card(3, fixture_card())
        rendered = str(card)
        self.assertIn("⚂", rendered)
        self.assertIn("第 3 面", rendered)

    def test_knowledge_card_has_favorite_and_next_draw_actions(self) -> None:
        card = build_knowledge_card(fixture_card())
        rendered = str(card)
        self.assertIn("收藏这张", rendered)
        self.assertIn("'card_id': 6", rendered)
        self.assertIn("再掷一次", rendered)
        self.assertIn("查看收藏", rendered)


if __name__ == "__main__":
    unittest.main()
