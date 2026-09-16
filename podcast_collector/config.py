from __future__ import annotations

import json
from pathlib import Path

from .models import Podcast


VALID_AUTHORITIES = {"first_hand", "expert_interview", "secondary_digest"}


def load_podcasts(path: Path) -> list[Podcast]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Podcast config must be a JSON array")

    podcasts: list[Podcast] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Podcast #{index + 1} must be an object")
        missing = [key for key in ("id", "name", "platform_url") if not item.get(key)]
        if missing:
            raise ValueError(f"Podcast #{index + 1} is missing: {', '.join(missing)}")
        if item["id"] in seen:
            raise ValueError(f"Duplicate podcast id: {item['id']}")
        authority = item.get("authority", "secondary_digest")
        if authority not in VALID_AUTHORITIES:
            raise ValueError(f"Invalid authority for {item['id']}: {authority}")
        seen.add(item["id"])
        podcasts.append(
            Podcast(
                id=item["id"],
                name=item["name"],
                platform_url=item["platform_url"],
                feed_url=item.get("feed_url"),
                language=item.get("language", "zh-CN"),
                authority=authority,
                enabled=bool(item.get("enabled", True)),
            )
        )
    return podcasts
