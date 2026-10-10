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

# 概念图标映射，用于卡片视觉点缀
TERM_ICONS = {
    "FDE": "🏭",
    "蒸馏": "🧪",
    "开放权重": "📦",
    "Sim-to-Real": "🎮",
    "RSI": "🔄",
    "Harness": "⚙️",
    "经验差距": "📉",
    "主权 AI": "🏛️",
    "奖励黑客": "🎯",
    "Headless": "👻",
    "Agentic Economy": "💱",
    "世界模型": "🌍",
}


def build_menu_card(
    cards: list[Card],
    *,
    show_subscribe_hint: bool = False,
) -> dict[str, Any]:
    """今日卡组主卡片：导读 + 六面暗示 + 操作区 + 可选订阅提示。"""
    elements: list[dict[str, Any]] = []

    # —— 今日导读 ——
    elements.append(_markdown(_daily_brief(cards)))
    elements.append({"tag": "hr"})

    # —— 六张概念卡片（编号标题 + teaser + 翻开按钮，用分割线隔开）——
    elements.append(_markdown("**六张卡面已洗好，选一张翻开** 🎴"))
    for index, card in enumerate(cards, 1):
        title, teaser = topic_hint(card)
        icon = TERM_ICONS.get(card.term, "💡")
        if index > 1:
            elements.append({"tag": "hr"})
        elements.extend(
            _concept_card(
                index=index,
                icon=icon,
                title=title,
                teaser=teaser,
                action={"action": "select", "index": index},
            )
        )

    # —— 主操作区 ——
    elements.append({"tag": "hr"})
    elements.append(
        _button_row(
            [
                _button(
                    "🎲 让骰子替我选",
                    {"action": "dice"},
                    style="primary",
                ),
                _button("★ 我的收藏", {"action": "favorites"}),
            ]
        )
    )

    # —— 订阅提示（体验 N 次后显示）——
    if show_subscribe_hint:
        elements.append({"tag": "hr"})
        elements.append(
            _markdown(
                "<font color='grey'>💡 觉得有用？订阅每日推送，"
                "每天早上自动收到今日卡组，不用手动查。</font>"
            )
        )
        elements.append(
            _button_row(
                [_button("📩 订阅每日推送", {"action": "subscribe"}, style="primary")]
            )
        )

    return _card(
        title="今日 AI 六面骰",
        subtitle=date.today().strftime("%m 月 %d 日 · 每日更新"),
        template="purple",
        elements=elements,
    )


def build_rolling_card(face: int, card: Card) -> dict[str, Any]:
    """骰子滚动中的过渡卡片。"""
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


def build_knowledge_card(
    card: Card,
    *,
    favorite: bool = False,
    viewed_terms: set[str] | None = None,
) -> dict[str, Any]:
    """概念详情卡片：定义 + 深挖 + 相关概念（优先推荐没看过的）+ 来源 + 操作。"""
    aliases = " / ".join(card.aliases)
    icon = TERM_ICONS.get(card.term, "💡")
    viewed = viewed_terms or set()

    elements: list[dict[str, Any]] = []

    # —— 一句话定义（突出显示）——
    elements.append(
        _markdown(
            f"<font color='grey'>一句话定义</font>\n"
            f"**{card.one_line_definition}**"
        )
    )
    elements.append({"tag": "hr"})

    # —— 为什么值得知道 ——
    elements.append(
        _markdown(f"**🔍 为什么值得知道**\n{card.why_it_matters}")
    )

    # —— 认识边界 ——
    elements.append(
        _markdown(f"**⚖️ 认识边界**\n{card.uncertainty_note}")
    )

    # —— 状态标签 ——
    elements.append(
        _markdown(
            f"<font color='grey'>"
            f"术语状态：{MATURITY_LABELS.get(card.maturity_status, card.maturity_status)}"
            f"　·　"
            f"解释信心：{CONFIDENCE_LABELS.get(card.confidence, card.confidence)}"
            f"</font>"
        )
    )

    # —— 相关概念（优先推荐没看过的，都看过了就显示全部）——
    relations = RELATIONS.get(card.term, ())
    if relations:
        unseen = [r for r in relations if r not in viewed]
        show_relations = unseen if unseen else list(relations)
        elements.append({"tag": "hr"})
        if unseen:
            elements.append(_markdown("**🔗 接着认识**（你还没看过的）"))
        else:
            elements.append(_markdown("**🔗 接着认识**（这些你都看过啦）"))
        rel_buttons = [
            _button(
                f"{TERM_ICONS.get(r, '💡')} {r}",
                {"action": "jump", "term": r},
            )
            for r in show_relations
        ]
        # 相关概念按钮每行最多2个
        for i in range(0, len(rel_buttons), 2):
            elements.append(_button_row(rel_buttons[i : i + 2]))

    # —— 来源 ——
    elements.append({"tag": "hr"})
    if card.sources:
        elements.append(_markdown("**🎧 从哪里来**"))
        for source in card.sources[:3]:
            label = f"{source.podcast_name}｜{source.episode_title}"
            if source.page_url:
                elements.append(_markdown(f"- [{label}]({source.page_url})"))
            else:
                elements.append(_markdown(f"- {label}"))
    else:
        elements.append(_markdown("**🎧 从哪里来**  暂未绑定可展示的来源。"))

    # —— 操作区 ——
    elements.append({"tag": "hr"})
    favorite_label = "★ 已收藏" if favorite else "☆ 收藏这张"
    favorite_action = "unfavorite" if favorite else "favorite"
    elements.append(
        _button_row(
            [
                _button(
                    favorite_label,
                    {"action": favorite_action, "card_id": card.id},
                    style="primary" if not favorite else "default",
                ),
                _button("🎲 再掷一次", {"action": "dice"}),
            ]
        )
    )
    elements.append(
        _button_row(
            [
                _button("★ 查看收藏", {"action": "favorites"}),
                _button("返回今日话题", {"action": "menu"}),
            ]
        )
    )

    return _card(
        title=f"{icon} {card.term}",
        subtitle=aliases or "AI 概念卡",
        template="indigo" if not favorite else "green",
        elements=elements,
    )


def build_favorites_card(cards: list[Card]) -> dict[str, Any]:
    """收藏夹卡片。"""
    if cards:
        lines = [
            f"**{index}. {TERM_ICONS.get(card.term, '💡')} {card.term}**　"
            f"<font color='grey'>{card.one_line_definition}</font>"
            for index, card in enumerate(cards, 1)
        ]
        text = "\n\n".join(lines)
    else:
        text = "收藏盒还是空的。抽到喜欢的概念后，点一下「收藏这张」。"
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


def build_welcome_card(*, subscribed: bool = False) -> dict[str, Any]:
    """欢迎卡片：引导用户订阅每日推送。"""
    if subscribed:
        elements = [
            _markdown(
                "**你已经订阅了每日推送** 🎉\n\n"
                "每天早上我会主动把今日 AI 概念六面骰推送给你。\n\n"
                "现在就可以看看今天的卡组 👇"
            ),
            {"tag": "hr"},
            _button("🎲 查看今日卡组", {"action": "menu"}, style="primary"),
            _button("📤 退订每日推送", {"action": "unsubscribe"}),
        ]
    else:
        elements = [
            _markdown(
                "**欢迎来到 AI 概念骰子** 🎲\n\n"
                "每天六张 AI 概念卡，从精选播客中提炼值得了解的新词。\n\n"
                "订阅后，每天早上我会主动把今日卡组推送给你，"
                "点一点按钮就能抽卡、收藏、分享。"
            ),
            {"tag": "hr"},
            _markdown("**你将获得：**"),
            _markdown(
                "📅 每日主动推送，不用手动查询\n"
                "🎲 六面骰随机抽取，每天不重样\n"
                "⭐ 收藏喜欢的概念，建立知识盒\n"
                "📋 一键分享纯文本，转发给朋友"
            ),
            {"tag": "hr"},
            _button("📩 订阅每日推送", {"action": "subscribe"}, style="primary"),
            _button("🎲 先看看今日卡组", {"action": "menu"}),
        ]
    return _card(
        title="AI 概念骰子",
        subtitle="每日六张 · 读懂 AI 新词",
        template="purple",
        elements=elements,
    )


def build_unsubscribe_card() -> dict[str, Any]:
    """退订确认卡片。"""
    return _card(
        title="已退订",
        subtitle="期待再次相遇",
        template="grey",
        elements=[
            _markdown(
                "你已取消每日推送。\n\n"
                "以后想再订阅，随时给我发消息，我会把订阅卡片发给你。"
            ),
            {"tag": "hr"},
            _button("📩 重新订阅", {"action": "subscribe"}, style="primary"),
        ],
    )


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _daily_brief(cards: list[Card]) -> str:
    """根据今日6张卡生成一段导读文字。"""
    titles = [topic_hint(c)[0] for c in cards]
    # 取前3个标题作为今日方向
    directions = "、".join(titles[:3])
    count = len(cards)
    return (
        f"**📰 今日导读**\n"
        f"今天的 {count} 个概念围绕「{directions}」等方向展开。"
        f"先读六条暗示，凭直觉选一个数字，或者让骰子替你决定。"
    )


def _concept_card(
    *,
    index: int,
    icon: str,
    title: str,
    teaser: str,
    action: dict[str, Any],
) -> list[dict[str, Any]]:
    """两列布局：左列文字（标题+teaser），右列按钮水平垂直居中。"""
    button = _button("🎲 翻开这张", action, style="primary")
    # 右列内再套三列布局，实现按钮水平居中
    centered_button_in_column = {
        "tag": "column_set",
        "flex_mode": "none",
        "background_style": "default",
        "columns": [
            {"tag": "column", "width": "weighted", "weight": 1, "elements": []},
            {"tag": "column", "width": "auto", "vertical_align": "center", "elements": [button]},
            {"tag": "column", "width": "weighted", "weight": 1, "elements": []},
        ],
    }
    row = {
        "tag": "column_set",
        "flex_mode": "none",
        "background_style": "default",
        "columns": [
            {
                "tag": "column",
                "width": "weighted",
                "weight": 2,
                "vertical_align": "center",
                "elements": [
                    _markdown(f"**{index}. {icon} {title}**"),
                    _markdown(f"<font color='grey'>{teaser}</font>"),
                ],
            },
            {
                "tag": "column",
                "width": "weighted",
                "weight": 1,
                "vertical_align": "center",
                "elements": [centered_button_in_column],
            },
        ],
    }
    return [row]


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
