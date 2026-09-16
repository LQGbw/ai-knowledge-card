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
        rolling = build_rolling_card(face, card)
        rolling_result = await channel.send(chat_id, {"card": rolling})
        await asyncio.sleep(0.85)
        if rolling_result.success and rolling_result.message_id:
            result = await channel.update_card(
                rolling_result.message_id,
                build_knowledge_card(
                    card,
                    favorite=state.is_favorite(user_id, card.id),
                ),
            )
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

        command = _normalize_command(message.body_text or message.content_text or "")
        cards = catalog.daily_cards(message.chat_id)
        user_id = message.sender_id or message.chat_id
        if command in MENU_COMMANDS or command in HELP_COMMANDS or not command:
            result = await channel.send(
                message.chat_id,
                {"card": build_menu_card(cards)},
            )
            if not result.success:
                await channel.send(
                    message.chat_id,
                    {"markdown": format_menu(cards)},
                    {"reply_to": message.message_id},
                )
        elif command in DRAW_COMMANDS:
            await reveal(
                chat_id=message.chat_id,
                user_id=user_id,
                cards=cards,
                face=random.SystemRandom().randint(1, len(cards)),
            )
        elif command in FAVORITE_COMMANDS or command in UNFAVORITE_COMMANDS:
            card_id = state.last_reveal(user_id)
            card = catalog.card_by_id(card_id) if card_id else None
            if card is None:
                reply = "还没有可以收藏的概念。先回复「骰子」抽一个吧。"
            elif command in FAVORITE_COMMANDS:
                state.add_favorite(user_id, card.id)
                reply = f"★ 已收藏「{card.term}」。回复「我的收藏」随时查看。"
            else:
                state.remove_favorite(user_id, card.id)
                reply = f"已从收藏中移除「{card.term}」。"
            await channel.send(
                message.chat_id,
                {"text": reply},
                {"reply_to": message.message_id},
            )
        elif command in FAVORITES_COMMANDS:
            await channel.send(
                message.chat_id,
                {"card": build_favorites_card(favorite_cards(user_id))},
            )
        else:
            selected = _selected_number(command)
            if selected is not None and selected <= len(cards):
                await reveal(
                    chat_id=message.chat_id,
                    user_id=user_id,
                    cards=cards,
                    face=selected,
                )
            else:
                reply = (
                    "我现在认识这些玩法：回复「今日卡组」看话题暗示，"
                    "回复 1 到 6 选择，回复「骰子」随机抽取，"
                    "回复「收藏」或「我的收藏」整理知识盒。"
                )
                await channel.send(
                    message.chat_id,
                    {"text": reply},
                    {"reply_to": message.message_id},
                )

    async def on_card_action(event) -> None:
        if allowed_chat_id and event.chat_id != allowed_chat_id:
            return
        value = event.action.value if isinstance(event.action.value, dict) else {}
        action = value.get("action")
        user_id = event.operator.open_id or event.chat_id
        cards = catalog.daily_cards(event.chat_id)

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
                await channel.update_card(
                    event.message_id,
                    build_knowledge_card(
                        card,
                        favorite=state.is_favorite(user_id, card.id),
                    ),
                )
        elif action == "favorites":
            await channel.send(
                event.chat_id,
                {"card": build_favorites_card(favorite_cards(user_id))},
            )
        elif action == "menu":
            await channel.send(event.chat_id, {"card": build_menu_card(cards)})

    async def on_error(error) -> None:
        print(f"飞书连接出现异常：{error}")

    channel.on("message", on_message)
    channel.on("cardAction", on_card_action)
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
