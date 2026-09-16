from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import CardDraft, Episode, Podcast


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS podcasts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    platform_url TEXT NOT NULL,
    feed_url TEXT,
    language TEXT NOT NULL,
    authority TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    last_synced_at TEXT,
    sync_status TEXT NOT NULL DEFAULT 'pending',
    sync_error TEXT
);

CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    podcast_id TEXT NOT NULL REFERENCES podcasts(id),
    guid TEXT NOT NULL,
    title TEXT NOT NULL,
    page_url TEXT,
    audio_url TEXT,
    published_at TEXT,
    author TEXT,
    show_notes TEXT,
    duration_seconds INTEGER,
    content_hash TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(podcast_id, guid)
);

CREATE INDEX IF NOT EXISTS idx_episodes_podcast ON episodes(podcast_id);
CREATE INDEX IF NOT EXISTS idx_episodes_published ON episodes(published_at DESC);

CREATE TABLE IF NOT EXISTS knowledge_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    normalized_term TEXT NOT NULL UNIQUE,
    aliases_json TEXT NOT NULL,
    one_line_definition TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    maturity_status TEXT NOT NULL,
    uncertainty_note TEXT NOT NULL,
    confidence TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS card_sources (
    card_id INTEGER NOT NULL REFERENCES knowledge_cards(id) ON DELETE CASCADE,
    episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    PRIMARY KEY(card_id, episode_id)
);

CREATE INDEX IF NOT EXISTS idx_cards_status ON knowledge_cards(status);
"""


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def upsert_podcast(self, podcast: Podcast) -> None:
        self.connection.execute(
            """
            INSERT INTO podcasts (id, name, platform_url, feed_url, language, authority, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, platform_url=excluded.platform_url,
                feed_url=excluded.feed_url, language=excluded.language,
                authority=excluded.authority, enabled=excluded.enabled
            """,
            (
                podcast.id,
                podcast.name,
                podcast.platform_url,
                podcast.feed_url,
                podcast.language,
                podcast.authority,
                int(podcast.enabled),
            ),
        )
        self.connection.commit()

    def upsert_episode(self, podcast_id: str, episode: Episode) -> str:
        content_hash = _episode_hash(episode)
        existing = self.connection.execute(
            "SELECT content_hash FROM episodes WHERE podcast_id=? AND guid=?",
            (podcast_id, episode.guid),
        ).fetchone()
        now = _now()
        self.connection.execute(
            """
            INSERT INTO episodes
                (podcast_id, guid, title, page_url, audio_url, published_at, author,
                 show_notes, duration_seconds, content_hash, discovered_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(podcast_id, guid) DO UPDATE SET
                title=excluded.title, page_url=excluded.page_url,
                audio_url=excluded.audio_url, published_at=excluded.published_at,
                author=excluded.author, show_notes=excluded.show_notes,
                duration_seconds=excluded.duration_seconds,
                content_hash=excluded.content_hash, updated_at=excluded.updated_at
            """,
            (
                podcast_id,
                episode.guid,
                episode.title,
                episode.page_url,
                episode.audio_url,
                episode.published_at,
                episode.author,
                episode.show_notes,
                episode.duration_seconds,
                content_hash,
                now,
                now,
            ),
        )
        self.connection.commit()
        if existing is None:
            return "new"
        return "updated" if existing["content_hash"] != content_hash else "unchanged"

    def mark_sync(self, podcast_id: str, status: str, error: str | None = None) -> None:
        self.connection.execute(
            "UPDATE podcasts SET last_synced_at=?, sync_status=?, sync_error=? WHERE id=?",
            (_now(), status, error[:2000] if error else None, podcast_id),
        )
        self.connection.commit()

    def list_episodes(self, limit: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT e.title, e.page_url, e.published_at, e.duration_seconds,
                       p.name AS podcast_name
                FROM episodes e JOIN podcasts p ON p.id=e.podcast_id
                ORDER BY COALESCE(e.published_at, e.discovered_at) DESC LIMIT ?
                """,
                (limit,),
            )
        )

    def episode_inputs(self, per_podcast: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                WITH ranked AS (
                    SELECT e.id, e.title, e.show_notes, e.page_url, e.published_at,
                           e.discovered_at, p.name AS podcast_name, p.authority,
                           ROW_NUMBER() OVER (
                               PARTITION BY e.podcast_id
                               ORDER BY COALESCE(e.published_at, e.discovered_at) DESC
                           ) AS rank_in_podcast
                    FROM episodes e JOIN podcasts p ON p.id=e.podcast_id
                    WHERE e.show_notes IS NOT NULL AND trim(e.show_notes) != ''
                )
                SELECT id, title, show_notes, page_url, published_at,
                       podcast_name, authority
                FROM ranked WHERE rank_in_podcast <= ?
                ORDER BY COALESCE(published_at, discovered_at) DESC
                """,
                (per_podcast,),
            )
        )

    def save_card_draft(
        self,
        draft: CardDraft,
        model: str,
        prompt_version: str,
    ) -> int:
        import json

        normalized = _normalize_term(draft.term)
        if not normalized:
            raise ValueError("Card term cannot be empty")
        valid_episode_ids = {
            row["id"]
            for row in self.connection.execute(
                f"SELECT id FROM episodes WHERE id IN ({','.join('?' for _ in draft.source_episode_ids)})",
                draft.source_episode_ids,
            )
        } if draft.source_episode_ids else set()
        if not valid_episode_ids:
            raise ValueError(f"Card {draft.term!r} has no valid source episode")

        now = _now()
        self.connection.execute(
            """
            INSERT INTO knowledge_cards
                (term, normalized_term, aliases_json, one_line_definition,
                 why_it_matters, maturity_status, uncertainty_note, confidence,
                 status, model, prompt_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)
            ON CONFLICT(normalized_term) DO UPDATE SET
                term=excluded.term, aliases_json=excluded.aliases_json,
                one_line_definition=excluded.one_line_definition,
                why_it_matters=excluded.why_it_matters,
                maturity_status=excluded.maturity_status,
                uncertainty_note=excluded.uncertainty_note,
                confidence=excluded.confidence, model=excluded.model,
                prompt_version=excluded.prompt_version, updated_at=excluded.updated_at
            WHERE knowledge_cards.status='draft'
            """,
            (
                draft.term.strip(),
                normalized,
                json.dumps(draft.aliases, ensure_ascii=False),
                draft.one_line_definition.strip(),
                draft.why_it_matters.strip(),
                draft.maturity_status,
                draft.uncertainty_note.strip(),
                draft.confidence,
                model,
                prompt_version,
                now,
                now,
            ),
        )
        row = self.connection.execute(
            "SELECT id, status FROM knowledge_cards WHERE normalized_term=?", (normalized,)
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to save card")
        card_id = row["id"]
        if row["status"] == "draft":
            self.connection.execute("DELETE FROM card_sources WHERE card_id=?", (card_id,))
            self.connection.executemany(
                "INSERT INTO card_sources(card_id, episode_id) VALUES (?, ?)",
                [(card_id, episode_id) for episode_id in sorted(valid_episode_ids)],
            )
        self.connection.commit()
        return card_id

    def list_cards(self, limit: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT c.id, c.term, c.one_line_definition, c.why_it_matters,
                       c.maturity_status, c.confidence, c.status,
                       COUNT(cs.episode_id) AS source_count
                FROM knowledge_cards c
                LEFT JOIN card_sources cs ON cs.card_id=c.id
                GROUP BY c.id ORDER BY c.updated_at DESC LIMIT ?
                """,
                (limit,),
            )
        )


def _episode_hash(episode: Episode) -> str:
    value = "\n".join(
        str(part or "")
        for part in (
            episode.title,
            episode.page_url,
            episode.audio_url,
            episode.published_at,
            episode.author,
            episode.show_notes,
            episode.duration_seconds,
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_term(term: str) -> str:
    return " ".join(term.casefold().strip().split())
