from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cards import PROMPT_VERSION, generate_card_drafts, parse_card_drafts, validate_evidence
from .config import load_podcasts
from .feed import fetch_feed, parse_feed
from .store import Store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect episodes from trusted AI podcasts")
    parser.add_argument("--config", type=Path, default=Path("config/podcasts.json"))
    parser.add_argument("--database", type=Path, default=Path("data/podcasts.sqlite3"))
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync", help="sync podcast feeds")
    sync.add_argument("--max-per-podcast", type=int, default=30)
    listing = commands.add_parser("list", help="list collected episodes")
    listing.add_argument("--limit", type=int, default=20)
    generate = commands.add_parser("generate", help="generate knowledge-card drafts")
    generate.add_argument("--per-podcast", type=int, default=5)
    generate.add_argument("--max-cards", type=int, default=10)
    generate.add_argument("--model", default=None)
    cards = commands.add_parser("cards", help="list knowledge-card drafts")
    cards.add_argument("--limit", type=int, default=20)
    importing = commands.add_parser("import-cards", help="import reviewed card drafts from JSON")
    importing.add_argument("path", type=Path)
    importing.add_argument("--model", default="editorial-seed")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = Store(args.database)
    try:
        if args.command == "sync":
            return sync(store, args.config, args.max_per_podcast)
        if args.command == "list":
            return list_episodes(store, args.limit)
        if args.command == "generate":
            return generate(store, args.per_podcast, args.max_cards, args.model)
        if args.command == "cards":
            return list_cards(store, args.limit)
        return import_cards(store, args.path, args.model)
    finally:
        store.close()


def sync(store: Store, config_path: Path, max_per_podcast: int) -> int:
    failures = 0
    for podcast in load_podcasts(config_path):
        if not podcast.enabled:
            continue
        store.upsert_podcast(podcast)
        if not podcast.feed_url:
            store.mark_sync(podcast.id, "needs_feed", "No public RSS feed resolved yet")
            print(f"[{podcast.name}] RSS 尚未确认，已保留节目来源")
            continue
        print(f"[{podcast.name}] 同步 RSS")
        try:
            episodes = parse_feed(fetch_feed(podcast.feed_url))[:max_per_podcast]
            counts = {"new": 0, "updated": 0, "unchanged": 0}
            for episode in episodes:
                counts[store.upsert_episode(podcast.id, episode)] += 1
            store.mark_sync(podcast.id, "synced")
            print(
                f"  {len(episodes)} 集：新增 {counts['new']}，"
                f"更新 {counts['updated']}，未变化 {counts['unchanged']}"
            )
        except Exception as exc:
            failures += 1
            store.mark_sync(podcast.id, "failed", str(exc))
            print(f"  同步失败：{exc}", file=sys.stderr)
    return 1 if failures else 0


def list_episodes(store: Store, limit: int) -> int:
    for row in store.list_episodes(limit):
        duration = row["duration_seconds"]
        duration_text = f"{duration // 60} 分钟" if duration else "时长未知"
        print(
            f"{row['published_at'] or '日期未知'} | {row['podcast_name']} | "
            f"{duration_text} | {row['title']}"
        )
        if row["page_url"]:
            print(f"  {row['page_url']}")
    return 0


def generate(store: Store, per_podcast: int, max_cards: int, model: str | None) -> int:
    episodes = store.episode_inputs(per_podcast)
    if not episodes:
        print("没有可用于生成卡片的单集，请先运行 sync。", file=sys.stderr)
        return 1
    try:
        drafts, selected_model = generate_card_drafts(episodes, max_cards, model)
    except RuntimeError as exc:
        print(f"无法生成卡片：{exc}", file=sys.stderr)
        return 2
    for draft in drafts:
        store.save_card_draft(draft, selected_model, PROMPT_VERSION)
    print(f"已生成 {len(drafts)} 张待审核知识卡，模型：{selected_model}")
    return 0


def list_cards(store: Store, limit: int) -> int:
    for row in store.list_cards(limit):
        print(
            f"#{row['id']} [{row['status']}/{row['confidence']}/{row['maturity_status']}] "
            f"{row['term']}（{row['source_count']} 个来源）"
        )
        print(f"  {row['one_line_definition']}")
        print(f"  为什么重要：{row['why_it_matters']}")
    return 0


def import_cards(store: Store, path: Path, model: str) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    drafts = validate_evidence(parse_card_drafts(payload), store.episode_inputs(10_000))
    for draft in drafts:
        store.save_card_draft(draft, model, "manual-import-v1")
    print(f"已导入 {len(drafts)} 张待审核知识卡")
    return 0
