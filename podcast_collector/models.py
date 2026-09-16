from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Podcast:
    id: str
    name: str
    platform_url: str
    feed_url: str | None
    language: str = "zh-CN"
    authority: str = "secondary_digest"
    enabled: bool = True


@dataclass(frozen=True)
class Episode:
    guid: str
    title: str
    page_url: str | None = None
    audio_url: str | None = None
    published_at: str | None = None
    author: str | None = None
    show_notes: str | None = None
    duration_seconds: int | None = None


@dataclass(frozen=True)
class CardDraft:
    term: str
    aliases: list[str]
    one_line_definition: str
    why_it_matters: str
    maturity_status: str
    uncertainty_note: str
    confidence: str
    source_episode_ids: list[int]
