#!/usr/bin/env python3
"""
每日任务：自动采集播客 → 生成知识卡草稿 → 每日发布 2 张 → 100 张上限提醒。

用法：
    python3 daily_job.py              # 执行完整每日任务
    python3 daily_job.py --sync-only  # 只同步播客
    python3 daily_job.py --publish-only  # 只发布草稿
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE = PROJECT_ROOT / "data" / "podcasts.sqlite3"
PODCAST_CONFIG = PROJECT_ROOT / "config" / "podcasts.json"
MAX_POOL_SIZE = 100
DAILY_PUBLISH_COUNT = 2


def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


def sync_podcasts() -> bool:
    """同步播客 RSS，发现新单集。"""
    log("开始同步播客 RSS…")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "podcast_collector",
                "--config",
                str(PODCAST_CONFIG),
                "--database",
                str(DATABASE),
                "sync",
                "--max-per-podcast",
                "30",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.returncode == 0:
            log("播客同步完成")
            return True
        log(f"播客同步返回非零退出码：{result.returncode}")
        return False
    except Exception as exc:
        log(f"播客同步失败：{exc}")
        return False


def generate_drafts() -> int:
    """使用 OpenAI API 从新单集生成知识卡草稿。返回生成数量。"""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        log("未设置 OPENAI_API_KEY，跳过卡片生成（如需自动生成新卡，请配置 API 密钥）")
        return 0

    log("开始生成知识卡草稿…")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "podcast_collector",
                "--database",
                str(DATABASE),
                "generate",
                "--per-podcast",
                "5",
                "--max-cards",
                "10",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=600,
            env={**os.environ, "OPENAI_API_KEY": api_key},
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.returncode == 0:
            # 解析生成数量
            for line in result.stdout.splitlines():
                if "已生成" in line and "张" in line:
                    log(line.strip())
                    return 1
            log("卡片生成完成")
            return 1
        log(f"卡片生成返回非零退出码：{result.returncode}")
        return 0
    except Exception as exc:
        log(f"卡片生成失败：{exc}")
        return 0


def get_published_count(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        "SELECT COUNT(*) FROM knowledge_cards WHERE status='published'"
    )
    return cursor.fetchone()[0]


def get_published_today_count(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        """
        SELECT COUNT(*) FROM knowledge_cards
        WHERE status='published' AND date(published_at) = date('now')
        """
    )
    return cursor.fetchone()[0]


def publish_drafts(conn: sqlite3.Connection, count: int) -> int:
    """发布指定数量的草稿卡。返回实际发布数量。"""
    published_today = get_published_today_count(conn)
    remaining = max(0, count - published_today)
    if remaining == 0:
        log(f"今日已发布 {published_today} 张，达到每日上限 {count} 张，跳过")
        return 0

    # 检查卡池上限
    total_published = get_published_count(conn)
    if total_published >= MAX_POOL_SIZE:
        log(f"⚠️ 卡池已达上限 {MAX_POOL_SIZE} 张（当前 {total_published} 张），停止发布新卡。请审核清理或调整上限。")
        return 0

    # 选取最旧的未发布草稿
    cursor = conn.execute(
        """
        SELECT id, term FROM knowledge_cards
        WHERE status='draft'
        ORDER BY created_at ASC
        LIMIT ?
        """,
        (remaining,),
    )
    drafts = cursor.fetchall()
    if not drafts:
        log("没有待发布的草稿卡（可运行 generate 生成，或手动 import-cards 导入）")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    published = 0
    for card_id, term in drafts:
        conn.execute(
            "UPDATE knowledge_cards SET status='published', published_at=? WHERE id=?",
            (now, card_id),
        )
        log(f"  发布 #{card_id}「{term}」")
        published += 1

    conn.commit()

    # 发布后再次检查上限
    new_total = get_published_count(conn)
    if new_total >= MAX_POOL_SIZE - 5:
        log(f"⚠️ 卡池即将达上限：当前 {new_total} 张，上限 {MAX_POOL_SIZE} 张。建议审核整理。")

    return published


def push_to_subscribers() -> int:
    """调用推送脚本，向所有订阅用户推送今日卡组。"""
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "push_daily.py")],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode
    except Exception as exc:
        log(f"推送失败：{exc}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="每日任务：采集 + 生成 + 发布")
    parser.add_argument("--sync-only", action="store_true", help="只同步播客")
    parser.add_argument("--publish-only", action="store_true", help="只发布草稿")
    parser.add_argument("--count", type=int, default=DAILY_PUBLISH_COUNT, help=f"每日发布数量（默认 {DAILY_PUBLISH_COUNT}）")
    args = parser.parse_args()

    if not DATABASE.is_file():
        log(f"错误：数据库不存在 {DATABASE}")
        return 1

    conn = sqlite3.connect(DATABASE)
    try:
        if args.publish_only:
            log("=== 仅发布模式 ===")
            publish_drafts(conn, args.count)
            return 0

        if args.sync_only:
            log("=== 仅同步模式 ===")
            sync_podcasts()
            return 0

        # 完整流程
        log("=" * 50)
        log("每日任务开始")
        log(f"当前卡池：{get_published_count(conn)} 张已发布 / 上限 {MAX_POOL_SIZE} 张")
        log("=" * 50)

        # 1. 同步播客
        sync_podcasts()

        # 2. 生成草稿
        generate_drafts()

        # 3. 发布每日新卡
        log(f"开始发布今日新卡（每日 {args.count} 张）…")
        published = publish_drafts(conn, args.count)
        if published > 0:
            log(f"今日新发布 {published} 张卡")
        else:
            log("今日无新卡发布")

        # 4. 推送今日卡组给所有订阅用户
        log("开始推送今日卡组…")
        push_result = push_to_subscribers()
        if push_result == 0:
            log("推送完成")
        else:
            log(f"推送过程中出现问题（退出码 {push_result}）")

        log(f"任务完成。当前卡池：{get_published_count(conn)} 张")
        log("=" * 50)
        return 0

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
