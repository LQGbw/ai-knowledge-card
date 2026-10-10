from __future__ import annotations

import asyncio
import os
import random
import re
from pathlib import Path

import truststore
from dotenv import load_dotenv
from lark_channel import FeishuChannel, LogLevel, SecurityConfig

from .cards import (
    build_favorites_card,
    build_knowledge_card,
    build_menu_card,
    build_rolling_card,
    build_unsubscribe_card,
    build_welcome_card,
)
from .content import Card, CardCatalog, format_card, format_menu
from .state import BotStateStore


MENU_COMMANDS = {"开始", "菜单", "抽卡", "今日卡组", "今天的卡", "六个"}
DRAW_COMMANDS = {"抽一个", "骰子", "掷骰子", "换一个", "再来一个", "随机"}
HELP_COMMANDS = {"帮助", "help", "?", "？"}
FAVORITE_COMMANDS = {"收藏", "收藏这张", "喜欢"}
UNFAVORITE_COMMANDS = {"取消收藏", "不再收藏"}
FAVORITES_COMMANDS = {"我的收藏", "收藏夹", "知识盒"}


def run() -> None:
    # Python.org builds on macOS do not always see certificates trusted by the
    # system Keychain. Use the native trust store before opening HTTPS or WSS.
    truststore.inject_into_ssl()
    load_dotenv()
    app_id = os.getenv("LARK_APP_ID", "").strip()
    app_secret = os.getenv("LARK_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        raise SystemExit(
            "还缺飞书应用凭证。请把 .env.example 复制为 .env，"
            "再填写 LARK_APP_ID 和 LARK_APP_SECRET。"
        )

    database = Path(os.getenv("PODCAST_DATABASE", "data/podcasts.sqlite3"))
    catalog = CardCatalog(database)
    if not catalog.all_cards():
        raise SystemExit("数据库里还没有知识卡，请先导入卡片。")
    state_database = Path(
        os.getenv("FEISHU_STATE_DATABASE", "data/feishu_bot.sqlite3")
    )
    state = BotStateStore(state_database)

    allowed_chat_id = os.getenv("FEISHU_ALLOWED_CHAT_ID", "").strip()
    channel = FeishuChannel(
        app_id=app_id,
        app_secret=app_secret,
        log_level=LogLevel.WARNING,
        security=SecurityConfig(mode="audit"),
    )

    async def reveal(
        *,
        chat_id: str,
        user_id: str,
        cards: list[Card],
        face: int,
    ) -> None:
        card = cards[face - 1]
        state.remember_reveal(user_id, card.id)
        state.record_view(user_id, card.id)
        state.increment_menu_view(user_id)  # 抽卡也计入使用次数
        # 获取用户已看过的概念名称（用于「接着认识」过滤）
        viewed_ids = state.viewed_card_ids(user_id)
        viewed_terms = {
            c.term for c in catalog.all_cards() if c.id in viewed_ids
        }
        rolling = build_rolling_card(face, card)
        rolling_result = await channel.send(chat_id, {"card": rolling})
        await asyncio.sleep(0.85)
        knowledge_card = build_knowledge_card(
            card,
            favorite=state.is_favorite(user_id, card.id),
            viewed_terms=viewed_terms,
        )
        if rolling_result.success and rolling_result.message_id:
            try:
                result = await channel.update_card(
                    rolling_result.message_id,
                    knowledge_card,
                )
            except Exception as exc:
                print(f"更新卡片失败，改为发送新卡片: {exc}")
                result = await channel.send(chat_id, {"card": knowledge_card})
        else:
            result = await channel.send(
                chat_id,
                {"markdown": format_card(card)},
            )
        if result.success:
            print("已完成一次骰子揭晓。")

    def favorite_cards(user_id: str) -> list[Card]:
        cards = []
        for card_id in state.favorite_ids(user_id):
            card = catalog.card_by_id(card_id)
            if card:
                cards.append(card)
        return cards

    async def on_message(message) -> None:
        if allowed_chat_id and message.chat_id != allowed_chat_id:
            return
        try:
            await _handle_message(message)
        except Exception as exc:
            print(f"[on_message 异常] {exc}")
            try:
                await channel.send(
                    message.chat_id,
                    {"text": "抱歉，刚才处理消息时出了点小问题，请再试一次。"},
                )
            except Exception:
                pass

    async def _handle_message(message) -> None:
        command = _normalize_command(message.body_text or message.content_text or "")
        cards = catalog.daily_cards(message.chat_id)
        user_id = message.sender_id or message.chat_id

        # 已订阅用户在新对话中交互时，更新推送目标对话
        if state.is_subscribed(user_id):
            state.update_chat_id(user_id, message.chat_id)

        # 数字输入：直接揭晓对应卡片
        selected = _selected_number(command)
        if selected is not None and 1 <= selected <= len(cards):
            await reveal(
                chat_id=message.chat_id,
                user_id=user_id,
                cards=cards,
                face=selected,
            )
            return

        # 骰子/随机输入：随机揭晓一张
        if command in DRAW_COMMANDS:
            await reveal(
                chat_id=message.chat_id,
                user_id=user_id,
                cards=cards,
                face=random.SystemRandom().randint(1, len(cards)),
            )
            return

        # 菜单命令：直接显示今日卡组（体验3次后提示订阅）
        if command in MENU_COMMANDS:
            view_count = state.increment_menu_view(user_id)
            show_hint = view_count >= 3 and not state.is_subscribed(user_id)
            await channel.send(
                message.chat_id,
                {"card": build_menu_card(cards, show_subscribe_hint=show_hint)},
            )
            return

        # 其他文字：回复欢迎/订阅卡片（纯推送模式）
        subscribed = state.is_subscribed(user_id)
        await channel.send(
            message.chat_id,
            {"card": build_welcome_card(subscribed=subscribed)},
        )

    async def on_card_action(event) -> None:
        if allowed_chat_id and event.chat_id != allowed_chat_id:
            return
        try:
            await _handle_card_action(event)
        except Exception as exc:
            print(f"[on_card_action 异常] {exc}")
            try:
                await channel.send(
                    event.chat_id,
                    {"text": "抱歉，刚才操作时出了点小问题，请再试一次。"},
                )
            except Exception:
                pass

    async def _handle_card_action(event) -> None:
        value = event.action.value if isinstance(event.action.value, dict) else {}
        action = value.get("action")
        user_id = event.operator.open_id or event.chat_id
        cards = catalog.daily_cards(event.chat_id)

        # 已订阅用户在新对话中交互时，更新推送目标对话
        if state.is_subscribed(user_id):
            state.update_chat_id(user_id, event.chat_id)

        if action == "subscribe":
            state.subscribe(user_id, event.chat_id)
            await channel.send(
                event.chat_id,
                {"card": build_welcome_card(subscribed=True)},
            )
            # 订阅后立即推送今日卡组
            await channel.send(
                event.chat_id,
                {"card": build_menu_card(cards)},
            )
            return
        elif action == "unsubscribe":
            state.unsubscribe(user_id)
            await channel.send(
                event.chat_id,
                {"card": build_unsubscribe_card()},
            )
            return

        if action == "select":
            face = _safe_card_number(value.get("index"), len(cards))
            if face:
                await reveal(
                    chat_id=event.chat_id,
                    user_id=user_id,
                    cards=cards,
                    face=face,
                )
        elif action == "dice":
            await reveal(
                chat_id=event.chat_id,
                user_id=user_id,
                cards=cards,
                face=random.SystemRandom().randint(1, len(cards)),
            )
        elif action in {"favorite", "unfavorite"}:
            card_id = _safe_card_number(value.get("card_id"), 1_000_000)
            card = catalog.card_by_id(card_id) if card_id else None
            if card:
                if action == "favorite":
                    state.add_favorite(user_id, card.id)
                else:
                    state.remove_favorite(user_id, card.id)
                viewed_ids = state.viewed_card_ids(user_id)
                viewed_terms = {
                    c.term for c in catalog.all_cards() if c.id in viewed_ids
                }
                updated_card = build_knowledge_card(
                    card,
                    favorite=state.is_favorite(user_id, card.id),
                    viewed_terms=viewed_terms,
                )
                try:
                    await channel.update_card(event.message_id, updated_card)
                except Exception as exc:
                    print(f"收藏操作更新卡片失败，改为发送新卡片: {exc}")
                    await channel.send(event.chat_id, {"card": updated_card})
        elif action == "favorites":
            await channel.send(
                event.chat_id,
                {"card": build_favorites_card(favorite_cards(user_id))},
            )
        elif action == "menu":
            view_count = state.increment_menu_view(user_id)
            show_hint = view_count >= 3 and not state.is_subscribed(user_id)
            await channel.send(
                event.chat_id,
                {"card": build_menu_card(cards, show_subscribe_hint=show_hint)},
            )
        elif action == "jump":
            term = value.get("term", "")
            target = next(
                (c for c in catalog.all_cards() if c.term == term), None
            )
            if target:
                state.record_view(user_id, target.id)
                viewed_ids = state.viewed_card_ids(user_id)
                viewed_terms = {
                    c.term for c in catalog.all_cards() if c.id in viewed_ids
                }
                await channel.send(
                    event.chat_id,
                    {
                        "card": build_knowledge_card(
                            target,
                            favorite=state.is_favorite(user_id, target.id),
                            viewed_terms=viewed_terms,
                        )
                    },
                )
            else:
                await channel.send(
                    event.chat_id,
                    {"text": f"还没有「{term}」的概念卡，先从今日卡组里选一个吧。"},
                )
        elif action == "share":
            card_id = _safe_card_number(value.get("card_id"), 1_000_000)
            card = catalog.card_by_id(card_id) if card_id else None
            if card:
                share_text = _format_share_text(card)
                tip = (
                    "💡 分享给飞书好友：点卡片右上角「...」→「转发」，直接选人转发。\n"
                    "📋 分享到其他平台（微信/朋友圈等）：复制下方纯文本 👇\n\n"
                )
                await channel.send(
                    event.chat_id,
                    {"text": tip + share_text},
                    {"reply_to": event.message_id},
                )
            else:
                await channel.send(
                    event.chat_id,
                    {"text": "这张卡暂时无法分享。"},
                    {"reply_to": event.message_id},
                )

    async def on_error(error) -> None:
        print(f"飞书连接出现异常：{error}")

    async def on_bot_added(event) -> None:
        """机器人被添加到聊天时，主动发送欢迎卡片。"""
        if allowed_chat_id and event.chat_id != allowed_chat_id:
            return
        chat_name = getattr(event, "chat_name", None) or "新对话"
        print(f"机器人被添加到：{chat_name}（{event.chat_id}），发送欢迎卡片")
        operator = getattr(event, "operator", None)
        user_id = getattr(operator, "open_id", None) or event.chat_id
        subscribed = state.is_subscribed(user_id)
        if subscribed:
            state.update_chat_id(user_id, event.chat_id)
        await channel.send(
            event.chat_id,
            {"card": build_welcome_card(subscribed=subscribed)},
        )

    channel.on("message", on_message)
    channel.on("cardAction", on_card_action)
    channel.on("botAdded", on_bot_added)
    channel.on("error", on_error)
    print("AI 概念骰子正在连接飞书，按 Control-C 可停止。")
    asyncio.run(channel.connect())


def _normalize_command(value: str) -> str:
    value = re.sub(r"<at[^>]*>.*?</at>", "", value, flags=re.IGNORECASE)
    return value.strip().lower()


def _selected_number(command: str) -> int | None:
    match = re.fullmatch(r"(?:选)?\s*([1-6一二三四五六])\s*(?:号|张)?", command)
    if not match:
        return None
    value = match.group(1)
    chinese_numbers = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
    return chinese_numbers.get(value, int(value) if value.isdigit() else None)


def _safe_card_number(value: object, maximum: int) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= maximum else None


def _format_share_text(card) -> str:
    """生成可复制分享的纯文本版本。"""
    from .content import MATURITY_LABELS, CONFIDENCE_LABELS

    aliases = f"（{' / '.join(card.aliases)}）" if card.aliases else ""
    lines = [
        f"📖 {card.term}{aliases}",
        f"{'─' * 20}",
        card.one_line_definition,
        "",
        f"为什么值得知道：{card.why_it_matters}",
        "",
        f"认识边界：{card.uncertainty_note}",
        "",
        f"状态：{MATURITY_LABELS.get(card.maturity_status, card.maturity_status)}"
        f" · 信心：{CONFIDENCE_LABELS.get(card.confidence, card.confidence)}",
    ]
    if card.sources:
        lines.append("")
        lines.append("来源：")
        for source in card.sources[:2]:
            lines.append(f"  · {source.podcast_name}｜{source.episode_title}")
    lines.append("")
    lines.append("—— 来自「AI 概念骰子」飞书机器人")
    return "\n".join(lines)
