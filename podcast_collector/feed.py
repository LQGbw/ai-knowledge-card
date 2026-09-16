from __future__ import annotations

import email.utils
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timezone

import certifi

from .models import Episode


USER_AGENT = "AI-Term-Radar/0.1 (+podcast research collector)"


def fetch_feed(url: str, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
        return response.read()


def parse_feed(payload: bytes) -> list[Episode]:
    root = ET.fromstring(payload)
    root_name = _local_name(root.tag)
    if root_name in {"rss", "rdf"}:
        return _parse_rss(root)
    if root_name == "feed":
        return _parse_atom(root)
    raise ValueError(f"Unsupported podcast feed: {root_name}")


def _parse_rss(root: ET.Element) -> list[Episode]:
    episodes: list[Episode] = []
    for item in root.iter():
        if _local_name(item.tag) != "item":
            continue
        title = _child_text(item, "title") or "Untitled"
        page_url = _child_text(item, "link")
        guid = _child_text(item, "guid") or page_url
        enclosure = _child(item, "enclosure")
        audio_url = enclosure.attrib.get("url") if enclosure is not None else None
        if not guid:
            guid = audio_url
        if not guid:
            continue
        episodes.append(
            Episode(
                guid=guid.strip(),
                title=title.strip(),
                page_url=page_url.strip() if page_url else None,
                audio_url=audio_url,
                published_at=_normalize_date(
                    _child_text(item, "pubdate") or _child_text(item, "date")
                ),
                author=_child_text(item, "author") or _child_text(item, "creator"),
                show_notes=_child_text(item, "encoded") or _child_text(item, "description"),
                duration_seconds=_parse_duration(_child_text(item, "duration")),
            )
        )
    return episodes


def _parse_atom(root: ET.Element) -> list[Episode]:
    episodes: list[Episode] = []
    for entry in root:
        if _local_name(entry.tag) != "entry":
            continue
        page_url = None
        audio_url = None
        for link in entry:
            if _local_name(link.tag) != "link":
                continue
            rel = link.attrib.get("rel", "alternate")
            href = link.attrib.get("href")
            media_type = link.attrib.get("type", "")
            if rel == "enclosure" or media_type.startswith("audio/"):
                audio_url = href
            elif rel == "alternate":
                page_url = href
        guid = _child_text(entry, "id") or page_url or audio_url
        if not guid:
            continue
        episodes.append(
            Episode(
                guid=guid.strip(),
                title=(_child_text(entry, "title") or "Untitled").strip(),
                page_url=page_url,
                audio_url=audio_url,
                published_at=_normalize_date(
                    _child_text(entry, "published") or _child_text(entry, "updated")
                ),
                author=_atom_author(entry),
                show_notes=_child_text(entry, "content") or _child_text(entry, "summary"),
                duration_seconds=_parse_duration(_child_text(entry, "duration")),
            )
        )
    return episodes


def _atom_author(entry: ET.Element) -> str | None:
    author = _child(entry, "author")
    return _child_text(author, "name") if author is not None else None


def _child(node: ET.Element, wanted: str) -> ET.Element | None:
    wanted = wanted.lower()
    for child in node:
        if _local_name(child.tag) == wanted:
            return child
    return None


def _child_text(node: ET.Element | None, wanted: str) -> str | None:
    if node is None:
        return None
    child = _child(node, wanted)
    if child is None:
        return None
    value = "".join(child.itertext()).strip()
    return value or None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    return value.strip()


def _parse_duration(value: str | None) -> int | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return int(value)
    if not re.fullmatch(r"\d{1,3}:\d{1,2}(?::\d{1,2})?", value):
        return None
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds
