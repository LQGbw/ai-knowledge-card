import unittest

from podcast_collector.cards import build_input, parse_card_drafts, strip_html, validate_evidence


class CardGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.episodes = [
            {
                "id": 7,
                "podcast_name": "Example",
                "authority": "expert_interview",
                "title": "为什么 Agent Harness 很重要",
                "show_notes": "<p>Harness 是模型、工具与上下文之间的编排层。</p>",
                "page_url": "https://example.com/7",
            }
        ]

    def test_strips_html_and_builds_source_materials(self) -> None:
        self.assertEqual(strip_html("<p>Hello <strong>world</strong></p>"), "Hello world")
        prompt = build_input(self.episodes)
        self.assertIn('"episode_id": 7', prompt)
        self.assertNotIn("<p>", prompt)

    def test_rejects_card_without_term_evidence(self) -> None:
        payload = {
            "cards": [
                {
                    "term": "RAG",
                    "aliases": [],
                    "one_line_definition": "检索增强生成",
                    "why_it_matters": "补充外部知识",
                    "maturity_status": "stable",
                    "uncertainty_note": "材料有限",
                    "confidence": "low",
                    "source_episode_ids": [7],
                }
            ]
        }
        drafts = parse_card_drafts(payload)
        self.assertEqual(validate_evidence(drafts, self.episodes), [])

    def test_accepts_card_with_term_and_valid_source(self) -> None:
        payload = {
            "cards": [
                {
                    "term": "Harness",
                    "aliases": ["Agent Harness"],
                    "one_line_definition": "连接模型、工具和上下文的智能体编排层",
                    "why_it_matters": "决定智能体如何循环执行任务",
                    "maturity_status": "emerging",
                    "uncertainty_note": "不同团队的边界可能不同",
                    "confidence": "medium",
                    "source_episode_ids": [7, 999],
                }
            ]
        }
        accepted = validate_evidence(parse_card_drafts(payload), self.episodes)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].source_episode_ids, [7])


if __name__ == "__main__":
    unittest.main()
