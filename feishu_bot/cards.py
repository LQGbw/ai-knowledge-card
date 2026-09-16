from __future__ import annotations

from datetime import date
from typing import Any

from .content import (
    CONFIDENCE_LABELS,
    MATURITY_LABELS,
    RELATIONS,
    Card,
    topic_hint,
)


DICE_FACES = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}


def build_menu_card(cards: list[Card]) -> dict[str, Any]:
    elements: list[dict[str, Any]] = [
        _markdown("先读六条暗示。凭直觉选一个数字，或者让骰子替你决定。"),
        {"tag": "hr"},
    ]
    for index, card in enumerate(cards, 1):
        title, teaser = topic_hint(card)
        elements.append(
            _markdown(f"**{index} · {title}**\n<font color='grey'>{teaser}</font>")
        )

    number_buttons = [
        _button(str(index), {"action": "select", "index": index})
        for index in range(1, len(cards) + 1)
    ]
    if number_buttons:
        midpoint = min(3, len(number_buttons))
        elements.append(_button_row(number_buttons[:midpoint]))
        if number_buttons[midpoint:]:
            elements.append(_button_row(number_buttons[midpoint:]))
    elements.extend(
        [
            _button(
                "🎲 让骰子替我选",
                {"action": "dice"},
                style="primary",
            ),
            _button("★ 我的收藏", {"action": "favorites"}),
        ]
    )
    return _card(
        title="今日 AI 六面骰",
        subtitle=date.today().strftime("%m 月 %d 日"),
        template="purple",
        elements=elements,
    )


def build_rolling_card(face: int, card: Card) -> dict[str, Any]:
    title, teaser = topic_hint(card)
    return _card(
        title="骰子正在滚动",
        subtitle=f"第 {face} 面",
        template="indigo",
        elements=[
            _markdown(f"# {DICE_FACES.get(face, '🎲')}"),
            _markdown(f"**{title}**\n<font color='grey'>{teaser}</font>"),
            _markdown("让线索慢慢翻面……"),
        ],
    )


def build_knowledge_card(card: Card, *, favorite: bool = False) -> dict[str, Any]:
    title, teaser = topic_hint(card)
    aliases = " / ".join(card.aliases)
    subtitle = aliases or title
    content = [
        f"<font color='grey'>线索：{title} · {teaser}</font>",
        "",
        card.one_line_definition,
        "",
        f"**为什么值得知道**  {card.why_it_matters}",
        "",
        f"**认识边界**  {card.uncertainty_note}",
        "",
        (
            f"**术语状态**  {MATURITY_LABELS.get(card.maturity_status, card.maturity_status)}"
            f"　·　**解释信心**  {CONFIDENCE_LABELS.get(card.confidence, card.confidence)}"
        ),
    ]

    relations = RELATIONS.get(card.term, ())
    if relations:
        content.extend(["", "**接着认识**  " + "　·　".join(relations)])

    if card.sources:
        content.extend(["", "**从哪里来**"])
        for source in card.sources[:3]:
            label = f"{source.podcast_name}｜{source.episode_title}"
            if source.page_url:
                content.append(f"- [{label}]({source.page_url})")
            else:
                content.append(f"- {label}")
    else:
        content.extend(["", "**从哪里来**  暂未绑定可展示的来源。"])

    favorite_label = "★ 已收藏" if favorite else "☆ 收藏这张"
    favorite_action = "unfavorite" if favorite else "favorite"
    elements = [
        _markdown("\n".join(content)),
        {"tag": "hr"},
        _button_row(
            [
                _button(
                    favorite_label,
                    {"action": favorite_action, "card_id": card.id},
                    style="primary" if not favorite else "default",
                ),
                _button("🎲 再掷一次", {"action": "dice"}),
            ]
        ),
        _button_row(
            [
                _button("★ 查看收藏", {"action": "favorites"}),
                _button("返回今日话题", {"action": "menu"}),
            ]
        ),
    ]
    return _card(
        title=f"抽到：{card.term}",
        subtitle=subtitle,
        template="indigo" if not favorite else "green",
        elements=elements,
    )


def build_favorites_card(cards: list[Card]) -> dict[str, Any]:
    if cards:
        lines = [
            f"**{index}. {card.term}**　{card.one_line_definition}"
            for index, card in enumerate(cards, 1)
        ]
        text = "\n\n".join(lines)
    else:
        text = "收藏盒还是空的。抽到喜欢的概念后，点一下“收藏这张”。"
    return _card(
        title="我的 AI 知识盒",
        subtitle=f"已收藏 {len(cards)} 个概念",
        template="green",
        elements=[
            _markdown(text),
            {"tag": "hr"},
            _button("继续抽取", {"action": "menu"}, style="primary"),
        ],
    )


def _card(
    *,
    title: str,
    subtitle: str,
    template: str,
    elements: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": "2.0",
        "config": {},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "subtitle": {"tag": "plain_text", "content": subtitle},
            "template": template,
        },
        "body": {"elements": elements},
    }


def _markdown(content: str) -> dict[str, Any]:
    return {"tag": "markdown", "content": content}


def _button(
    label: str,
    value: dict[str, Any],
    *,
    style: str = "default",
) -> dict[str, Any]:
    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": label},
        "type": style,
        "behaviors": [{"type": "callback", "value": value}],
    }


def _button_row(buttons: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "tag": "column_set",
        "columns": [
            {"tag": "column", "width": "weighted", "weight": 1, "elements": [button]}
            for button in buttons
        ],
    }
