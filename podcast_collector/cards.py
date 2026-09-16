from __future__ import annotations

import json
import os
from html.parser import HTMLParser
from typing import Iterable, Mapping

from .models import CardDraft


PROMPT_VERSION = "cards-from-metadata-v1"
DEFAULT_MODEL = "gpt-5.4-mini"
MATURITY_STATUSES = {"emerging", "contested", "converging", "stable", "marketing", "unknown"}
CONFIDENCE_LEVELS = {"low", "medium", "high"}


CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "one_line_definition": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "maturity_status": {
                        "type": "string",
                        "enum": sorted(MATURITY_STATUSES),
                    },
                    "uncertainty_note": {"type": "string"},
                    "confidence": {"type": "string", "enum": sorted(CONFIDENCE_LEVELS)},
                    "source_episode_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": [
                    "term",
                    "aliases",
                    "one_line_definition",
                    "why_it_matters",
                    "maturity_status",
                    "uncertainty_note",
                    "confidence",
                    "source_episode_ids",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["cards"],
    "additionalProperties": False,
}


INSTRUCTIONS = """你是 AI 概念卡的研究编辑。请从播客单集的标题和简介中提取值得产品和职场人了解的 AI 概念。

约束：
1. 只能依据提供的标题和简介，不使用音频内容，也不补充材料外的历史、数字或来源。
2. term 必须原样出现在所引用的材料中；公司名、人名和单纯产品名通常不应成为概念卡。
3. 证据不足以清楚解释的词跳过，不要猜测。
4. 一句话解释使用普通人能懂的中文，不超过 60 个汉字。
5. why_it_matters 说明它为何值得当前用户关注，不超过 100 个汉字。
6. 定义存在分歧时使用 contested，并在 uncertainty_note 中写清分歧；无法判断成熟度时使用 unknown。
7. source_episode_ids 只能使用材料中给出的 episode_id。
8. 所有结果都是 draft，不要用肯定语气掩盖材料的不确定性。
"""


def build_input(episodes: Iterable[Mapping[str, object]], max_description_chars: int = 2400) -> str:
    materials = []
    for episode in episodes:
        description = strip_html(str(episode["show_notes"] or ""))[:max_description_chars]
        materials.append(
            {
                "episode_id": int(episode["id"]),
                "podcast": str(episode["podcast_name"]),
                "authority": str(episode["authority"]),
                "title": str(episode["title"]),
                "description": description,
                "source_url": str(episode["page_url"] or ""),
            }
        )
    return json.dumps({"source_materials": materials}, ensure_ascii=False)


def generate_card_drafts(
    episodes: list[Mapping[str, object]],
    max_cards: int,
    model: str | None = None,
) -> tuple[list[CardDraft], str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI SDK is not installed; run: python3 -m pip install -e .") from exc

    selected_model = model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=selected_model,
        instructions=INSTRUCTIONS + f"\n最多生成 {max_cards} 张卡。",
        input=build_input(episodes),
        reasoning={"effort": "low"},
        text={
            "format": {
                "type": "json_schema",
                "name": "knowledge_card_drafts",
                "strict": True,
                "schema": CARD_SCHEMA,
            }
        },
        max_output_tokens=8000,
        store=False,
    )
    raw = json.loads(response.output_text)
    drafts = parse_card_drafts(raw)[:max_cards]
    return validate_evidence(drafts, episodes), selected_model


def parse_card_drafts(payload: Mapping[str, object]) -> list[CardDraft]:
    cards = payload.get("cards")
    if not isinstance(cards, list):
        raise ValueError("Card payload must contain a cards array")
    drafts = []
    for item in cards:
        if not isinstance(item, dict):
            raise ValueError("Each card must be an object")
        maturity = str(item["maturity_status"])
        confidence = str(item["confidence"])
        if maturity not in MATURITY_STATUSES:
            raise ValueError(f"Invalid maturity status: {maturity}")
        if confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"Invalid confidence: {confidence}")
        drafts.append(
            CardDraft(
                term=str(item["term"]).strip(),
                aliases=[str(alias).strip() for alias in item["aliases"]],
                one_line_definition=str(item["one_line_definition"]).strip(),
                why_it_matters=str(item["why_it_matters"]).strip(),
                maturity_status=maturity,
                uncertainty_note=str(item["uncertainty_note"]).strip(),
                confidence=confidence,
                source_episode_ids=[int(value) for value in item["source_episode_ids"]],
            )
        )
    return drafts


def validate_evidence(
    drafts: Iterable[CardDraft], episodes: Iterable[Mapping[str, object]]
) -> list[CardDraft]:
    episode_text = {
        int(episode["id"]): f"{episode['title']} {strip_html(str(episode['show_notes'] or ''))}".casefold()
        for episode in episodes
    }
    accepted = []
    for draft in drafts:
        source_ids = [episode_id for episode_id in draft.source_episode_ids if episode_id in episode_text]
        if not source_ids:
            continue
        terms = [draft.term, *draft.aliases]
        if not any(
            term.casefold() in episode_text[episode_id]
            for term in terms
            if term
            for episode_id in source_ids
        ):
            continue
        accepted.append(
            CardDraft(
                term=draft.term,
                aliases=draft.aliases,
                one_line_definition=draft.one_line_definition,
                why_it_matters=draft.why_it_matters,
                maturity_status=draft.maturity_status,
                uncertainty_note=draft.uncertainty_note,
                confidence=draft.confidence,
                source_episode_ids=source_ids,
            )
        )
    return accepted


def strip_html(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return parser.text()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)
