from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path


MATURITY_LABELS = {
    "stable": "相对稳定",
    "emerging": "正在形成",
    "contested": "仍有争议",
}

CONFIDENCE_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
}

RELATIONS: dict[str, tuple[str, ...]] = {
    "FDE": ("Harness", "Headless"),
    "蒸馏": ("开放权重", "RSI"),
    "开放权重": ("蒸馏", "主权 AI"),
    "Sim-to-Real": ("世界模型", "经验差距"),
    "RSI": ("经验差距", "Harness"),
    "Harness": ("Headless", "Agentic Economy"),
    "经验差距": ("Harness", "RSI"),
    "主权 AI": ("开放权重", "FDE"),
    "奖励黑客": ("Harness", "RSI"),
    "Headless": ("Harness", "Agentic Economy"),
    "Agentic Economy": ("Headless", "Harness"),
    "世界模型": ("Sim-to-Real", "RSI"),
    # 第二批新卡
    "MCP": ("Harness", "Headless"),
    "RAG": ("向量数据库", "嵌入向量"),
    "大模型幻觉": ("RAG", "AI基准测试"),
    "AI对齐": ("奖励黑客", "AI安全"),
    "缩放定律": ("MoE", "推理成本"),
    "MoE": ("缩放定律", "推理成本"),
    "向量数据库": ("RAG", "嵌入向量"),
    "多智能体系统": ("Harness", "Agentic Economy"),
    "AI编程智能体": ("Harness", "AI副驾"),
    "LoRA": ("蒸馏", "Personal Intelligence"),
    "上下文窗口": ("RAG", "嵌入向量"),
    "提示注入": ("AI对齐", "AI安全"),
    "小语言模型": ("蒸馏", "端侧AI"),
    "端侧AI": ("小语言模型", "推理成本"),
    "AI搜索": ("RAG", "大模型幻觉"),
    "数字孪生": ("Sim-to-Real", "世界模型"),
    "AI副驾": ("AI编程智能体", "Harness"),
    "嵌入向量": ("RAG", "向量数据库"),
    "推理成本": ("MoE", "端侧AI"),
    "AI基准测试": ("大模型幻觉", "缩放定律"),
    # 中间批次卡
    "具身智能": ("Sim-to-Real", "物理 AI"),
    "模型硬件标准": ("Headless", "物理 AI"),
    "强化学习": ("RSI", "奖励黑客"),
    "Personal Intelligence": ("LoRA", "蒸馏"),
    "全自动 AI 研究员": ("多智能体系统", "AI编程智能体"),
    "AGI": ("RSI", "AI对齐"),
    "Cybercab": ("具身智能", "物理 AI"),
    "AI 3D": ("生成式AI", "数字孪生"),
    "制造业 OS": ("Headless", "数字孪生"),
    "物理 AI": ("具身智能", "世界模型"),
    "元博弈": ("奖励黑客", "AI基准测试"),
    "AI 动作实时化": ("具身智能", "物理 AI"),
}

HINTS: dict[str, tuple[str, str]] = {
    "FDE": ("去到现场的人", "谁把 AI 真正装进客户的工作流？"),
    "蒸馏": ("能力的浓缩术", "大模型的本领，怎样装进更小的模型？"),
    "开放权重": ("打开模型的盒子", "参数公开了，就等于完全开源吗？"),
    "Sim-to-Real": ("先在梦里练习", "机器人如何把模拟训练带进现实？"),
    "RSI": ("改进下一版自己", "AI 能否把升级变成连续循环？"),
    "Harness": ("模型之外的机关", "为什么同一个模型放进不同系统，表现差很多？"),
    "经验差距": ("每天都像第一天上班", "Agent 为什么用过之后仍没有真正成长？"),
    "主权 AI": ("把智能握在手里", "企业为什么不愿永远租用别人的模型？"),
    "奖励黑客": ("会钻规则空子的 AI", "拿到高分，为什么仍可能没有完成任务？"),
    "Headless": ("消失的操作界面", "当 Agent 直接调用软件，GUI 还重要吗？"),
    "Agentic Economy": ("当 Agent 开始交易", "智能体之间会形成怎样的新分工？"),
    "世界模型": ("在脑中预演世界", "AI 怎样理解下一刻可能发生什么？"),
    # 第二批新卡
    "MCP": ("AI 的 USB-C 接口", "为什么 AI 接工具还要写插件？"),
    "RAG": ("给 AI 发参考资料", "为什么 AI 回答要先翻文档再说话？"),
    "大模型幻觉": ("一本正经地胡说", "为什么 AI 会编造不存在的事实？"),
    "AI对齐": ("教 AI 做个好人", "怎么确保 AI 越来越强也不跑偏？"),
    "缩放定律": ("越大越强的魔咒", "为什么过去几年大家都在拼命堆算力？"),
    "MoE": ("一个团队，各司其职", "为什么大模型不只是一个超大网络？"),
    "向量数据库": ("AI 的书架", "AI 怎么从百万文档里找到那一句？"),
    "多智能体系统": ("AI 团队作战", "为什么一个 AI 不够，要组个团队？"),
    "AI编程智能体": ("会自己写代码的 AI", "程序员会被 AI 取代吗？"),
    "LoRA": ("给大模型贴便签", "为什么不用重训整个模型就能适配新任务？"),
    "上下文窗口": ("AI 的工作记忆", "为什么 AI 读长文会忘事？"),
    "提示注入": ("骗过 AI 的耳语", "为什么 AI 会被一句悄悄话操控？"),
    "小语言模型": ("够用就好的小 AI", "为什么不是所有场景都需要 GPT-4？"),
    "端侧AI": ("把 AI 揣进口袋", "为什么 AI 不一定要跑在云上？"),
    "AI搜索": ("不再点蓝色链接", "为什么搜索要变天了？"),
    "数字孪生": ("现实世界的模拟器", "为什么工厂要先在虚拟世界试一遍？"),
    "AI副驾": ("AI 当你的副驾", "为什么现在 AI 都是助手而不是司机？"),
    "嵌入向量": ("把文字变成坐标", "计算机怎么知道两段话意思相近？"),
    "推理成本": ("AI 每说一句话的价格", "为什么 AI 产品能不能赚钱看这个？"),
    "AI基准测试": ("AI 的考试成绩单", "为什么 AI 考了高分还是不靠谱？"),
    # 中间批次卡
    "具身智能": ("AI 要有身体了", "为什么 AI 光会聊天还不够？"),
    "模型硬件标准": ("给 AI 一把万能钥匙", "为什么 AI 要操作物理设备还需要标准？"),
    "强化学习": ("做对了给糖吃", "大模型怎么从做题变成会做事？"),
    "Personal Intelligence": ("我的专属小 AI", "为什么小团队也能养自己的模型？"),
    "全自动 AI 研究员": ("AI 自己做科研", "AI 写论文做实验还需要人吗？"),
    "AGI": ("AI 的终极目标", "什么才算真正的通用人工智能？"),
    "Cybercab": ("没有方向盘的出租车", "无人驾驶出租车什么时候来？"),
    "AI 3D": ("AI 帮你造三维", "为什么 AI 做 3D 是新趋势？"),
    "制造业 OS": ("工厂的操作系统", "为什么制造业需要自己的 OS？"),
    "物理 AI": ("AI 走进物理世界", "AI 怎么从屏幕走进真实世界？"),
    "元博弈": ("AI 知道自己被考", "为什么 AI 会在测试时装？"),
    "AI 动作实时化": ("机器人的反应速度", "为什么机器人动作总是慢半拍？"),
}


@dataclass(frozen=True)
class Source:
    podcast_name: str
    episode_title: str
    page_url: str | None
    published_at: str | None


@dataclass(frozen=True)
class Card:
    id: int
    term: str
    aliases: tuple[str, ...]
    one_line_definition: str
    why_it_matters: str
    maturity_status: str
    uncertainty_note: str
    confidence: str
    sources: tuple[Source, ...]


class CardCatalog:
    def __init__(self, database: Path) -> None:
        self.database = database.resolve()
        if not self.database.is_file():
            raise FileNotFoundError(f"找不到知识卡数据库：{self.database}")

    def all_cards(self) -> list[Card]:
        connection = sqlite3.connect(
            f"file:{self.database.as_posix()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        try:
            rows = list(
                connection.execute(
                    """
                    SELECT id, term, aliases_json, one_line_definition,
                           why_it_matters, maturity_status, uncertainty_note,
                           confidence
                    FROM knowledge_cards
                    WHERE status = 'published'
                    ORDER BY id
                    """
                )
            )
            cards: list[Card] = []
            for row in rows:
                source_rows = list(
                    connection.execute(
                        """
                        SELECT p.name AS podcast_name, e.title AS episode_title,
                               e.page_url, e.published_at
                        FROM card_sources cs
                        JOIN episodes e ON e.id=cs.episode_id
                        JOIN podcasts p ON p.id=e.podcast_id
                        WHERE cs.card_id=?
                        ORDER BY COALESCE(e.published_at, e.discovered_at) DESC
                        """,
                        (row["id"],),
                    )
                )
                cards.append(
                    Card(
                        id=row["id"],
                        term=row["term"],
                        aliases=tuple(json.loads(row["aliases_json"])),
                        one_line_definition=row["one_line_definition"],
                        why_it_matters=row["why_it_matters"],
                        maturity_status=row["maturity_status"],
                        uncertainty_note=row["uncertainty_note"],
                        confidence=row["confidence"],
                        sources=tuple(
                            Source(
                                podcast_name=source["podcast_name"],
                                episode_title=source["episode_title"],
                                page_url=source["page_url"],
                                published_at=source["published_at"],
                            )
                            for source in source_rows
                        ),
                    )
                )
            return cards
        finally:
            connection.close()

    def daily_cards(
        self,
        conversation_key: str,
        on_date: date | None = None,
        limit: int = 6,
    ) -> list[Card]:
        cards = self.all_cards()
        if not cards:
            return []
        day = on_date or date.today()
        seed = f"{day.isoformat()}:{conversation_key}"
        return sorted(
            cards,
            key=lambda card: hashlib.sha256(
                f"{seed}:{card.id}".encode("utf-8")
            ).digest(),
        )[:limit]

    def card_by_id(self, card_id: int) -> Card | None:
        return next((card for card in self.all_cards() if card.id == card_id), None)


def format_menu(cards: list[Card]) -> str:
    if not cards:
        return "今天还没有可抽取的知识卡。先运行知识卡导入后再来试试。"
    lines = ["🎲 **今天的 AI 六面骰**", "", "看一眼暗示，凭直觉选；也可以让骰子决定：", ""]
    for index, card in enumerate(cards, 1):
        title, teaser = topic_hint(card)
        lines.append(f"**{index} · {title}**　{teaser}")
    lines.extend(["", "直接回复 1 到 6，或回复「骰子」随机抽一个。"])
    return "\n".join(lines)


def format_card(card: Card) -> str:
    aliases = " / ".join(card.aliases)
    title = f"🎴 **{card.term}**"
    if aliases:
        title += f"  ·  {aliases}"

    lines = [
        title,
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
        lines.extend(["", "**接着认识**  " + "　·　".join(relations)])

    if card.sources:
        lines.extend(["", "**从哪里来**"])
        for source in card.sources[:3]:
            label = f"{source.podcast_name}｜{source.episode_title}"
            if source.page_url:
                lines.append(f"- [{label}]({source.page_url})")
            else:
                lines.append(f"- {label}")
    else:
        lines.extend(["", "**从哪里来**  这张卡暂未绑定可展示的来源。"])

    lines.extend(
        [
            "",
            "回复「收藏」留在自己的知识盒；回复「换一个」继续抽。",
        ]
    )
    return "\n".join(lines)


def topic_hint(card: Card) -> tuple[str, str]:
    return HINTS.get(
        card.term,
        ("一枚未命名的线索", "一个正在改变 AI 工作方式的新概念。"),
    )
