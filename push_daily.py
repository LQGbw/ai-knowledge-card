#!/usr/bin/env python3
"""
每日推送脚本：向所有订阅用户推送今日 AI 概念六面骰。
使用飞书 REST API 直接发送消息，不建立 WebSocket 连接（避免与运行中的机器人冲突）。

用法：
    python3 push_daily.py              # 推送给所有订阅用户
    python3 push_daily.py --dry-run    # 只打印将推送的用户，不实际发送
    python3 push_daily.py --chat-id xx # 推送到指定聊天（测试用）
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import truststore
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---- lark_channel 兼容性补丁：同步 HTTP Transport 缺 Content-Type 头 ----
import lark_channel.core.http.transport as _transport

_original_build_header = _transport._build_header


def _patched_build_header(request, option, conf=None):
    headers = _original_build_header(request, option, conf)
    if request.body is not None and not any(
        k.lower() == "content-type" for k in headers
    ):
        headers["Content-Type"] = "application/json"
    return headers


_transport._build_header = _patched_build_header
# ---- 补丁结束 ----

from feishu_bot.cards import build_menu_card
from feishu_bot.content import CardCatalog
from feishu_bot.state import BotStateStore


def log(msg: str) -> None:
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


async def send_card(client, chat_id: str, card: dict) -> bool:
    """通过 REST API 向指定聊天发送卡片消息。"""
    try:
        import json
        from lark_channel.api.im.v1.model.create_message_request import CreateMessageRequest
        from lark_channel.api.im.v1.model.create_message_request_body import CreateMessageRequestBody

        body = CreateMessageRequestBody.builder() \
            .receive_id(chat_id) \
            .msg_type("interactive") \
            .content(json.dumps(card, ensure_ascii=False)) \
            .build()

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(body) \
            .build()

        resp = await client.im.v1.message.acreate(request)
        return resp.code == 0
    except Exception as exc:
        log(f"  发送失败 {chat_id}: {exc}")
        return False


async def main() -> int:
    parser = argparse.ArgumentParser(description="每日推送今日卡组")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不实际发送")
    parser.add_argument("--chat-id", type=str, default=None, help="只推送到指定聊天（测试用）")
    args = parser.parse_args()

    truststore.inject_into_ssl()
    load_dotenv(PROJECT_ROOT / ".env")

    app_id = os.getenv("LARK_APP_ID", "").strip()
    app_secret = os.getenv("LARK_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        log("错误：缺少飞书应用凭证")
        return 1

    database = Path(os.getenv("PODCAST_DATABASE", "data/podcasts.sqlite3"))
    state_database = Path(os.getenv("FEISHU_STATE_DATABASE", "data/feishu_bot.sqlite3"))

    catalog = CardCatalog(database)
    state = BotStateStore(state_database)

    if args.chat_id:
        subscribers = [("test", args.chat_id)]
        log(f"测试模式：只推送到 {args.chat_id}")
    else:
        subscribers = state.all_subscriptions()  # [(user_id, chat_id), ...]
        log(f"订阅用户数：{len(subscribers)}")

    if not subscribers:
        log("没有订阅用户，跳过推送")
        return 0

    if args.dry_run:
        for user_id, chat_id in subscribers:
            cards = catalog.daily_cards(chat_id)
            log(f"  [DRY-RUN] {user_id} → {chat_id}（{len(cards)} 张卡）")
        return 0

    # 创建 REST API 客户端（不需要 WebSocket 连接）
    from lark_channel import Client

    client = Client.builder() \
        .app_id(app_id) \
        .app_secret(app_secret) \
        .domain("https://open.feishu.cn") \
        .build()

    success_count = 0
    fail_count = 0

    for user_id, chat_id in subscribers:
        cards = catalog.daily_cards(chat_id)
        if not cards:
            log(f"  {user_id}: 没有可用卡片，跳过")
            fail_count += 1
            continue

        card = build_menu_card(cards)
        ok = await send_card(client, chat_id, card)
        if ok:
            state.record_push(user_id)
            success_count += 1
            log(f"  ✓ {user_id} 推送成功")
        else:
            fail_count += 1
            log(f"  ✗ {user_id} 推送失败")
        await asyncio.sleep(0.5)  # 避免频率限制

    log(f"推送完成：成功 {success_count}，失败 {fail_count}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
