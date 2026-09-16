import unittest

from podcast_collector.feed import parse_feed


class FeedParsingTests(unittest.TestCase):
    def test_parses_podcast_rss(self) -> None:
        payload = b"""<?xml version="1.0"?>
        <rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
             xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><item>
          <title>Agent Memory</title>
          <link>https://example.com/agent-memory</link>
          <guid>episode-1</guid>
          <pubDate>Sat, 16 Aug 2026 08:00:00 GMT</pubDate>
          <content:encoded>A new memory architecture.</content:encoded>
          <itunes:duration>01:02:03</itunes:duration>
          <enclosure url="https://example.com/audio.mp3" type="audio/mpeg" />
        </item></channel></rss>"""
        episodes = parse_feed(payload)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0].title, "Agent Memory")
        self.assertEqual(episodes[0].guid, "episode-1")
        self.assertEqual(episodes[0].duration_seconds, 3723)
        self.assertEqual(episodes[0].audio_url, "https://example.com/audio.mp3")
        self.assertEqual(episodes[0].published_at, "2026-08-16T08:00:00+00:00")

    def test_parses_atom(self) -> None:
        payload = b"""<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom"><entry>
          <title>Context Engineering</title>
          <link rel="alternate" href="https://example.com/context" />
          <link rel="enclosure" type="audio/mpeg" href="https://example.com/audio.mp3" />
          <updated>2026-08-16T08:00:00Z</updated>
          <author><name>Example Author</name></author>
        </entry></feed>"""
        episodes = parse_feed(payload)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0].page_url, "https://example.com/context")
        self.assertEqual(episodes[0].author, "Example Author")


if __name__ == "__main__":
    unittest.main()
