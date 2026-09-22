import unittest

from deep_script_generator import deep_fallback_script
from podcast_uploader import EpisodeMetadata
from script_generator import fallback_script


ARTICLES = [
    {"title": "見出しA", "source": "媒体A", "link": "https://example.com/a"},
    {"title": "見出しB", "source": "媒体B", "link": "https://example.com/b"},
]


class FactFallbackTests(unittest.TestCase):
    def test_breaking_fallback_uses_only_titles_and_valid_speakers(self):
        script = fallback_script(ARTICLES, "ホスト", "ゲスト")
        text = "\n".join(line.text for line in script)

        self.assertEqual({line.speaker for line in script}, {"A", "B"})
        self.assertIn("見出しAというニュースです", text)
        self.assertIn("見出しBというニュースです", text)
        self.assertNotIn("影響", text)

    def test_breaking_fallback_is_limited_to_one_tts_chunk(self):
        articles = [
            {
                "title": f"見出し{i}",
                "source": f"媒体{i}",
                "link": f"https://example.com/{i}",
            }
            for i in range(18)
        ]

        script = fallback_script(articles, "ホスト", "ゲスト")
        text = "\n".join(line.text for line in script)

        self.assertEqual(len(script), 14)
        self.assertIn("見出し4というニュースです", text)
        self.assertNotIn("見出し5というニュースです", text)

    def test_deep_fallback_does_not_invent_analysis(self):
        script = deep_fallback_script(ARTICLES, "ホスト", "ゲスト")
        text = "\n".join(line.text for line in script)

        self.assertEqual({line.speaker for line in script}, {"A", "B"})
        self.assertIn("見出しAというニュースです", text)
        self.assertNotIn("今後の動向", text)
        self.assertNotIn("影響がある", text)

    def test_episode_metadata_records_verification_evidence(self):
        metadata = EpisodeMetadata(
            title="title",
            description="description",
            episode_number=1,
            published_date="2026-09-21",
            source_articles=ARTICLES,
            verification_status="grounded",
            verification_sources=["https://example.com/fact"],
            script_lines=[{"speaker": "A", "text": "確認済みです。"}],
        )

        self.assertEqual(metadata.verification_status, "grounded")
        self.assertEqual(
            metadata.verification_sources,
            ["https://example.com/fact"],
        )
        self.assertEqual(
            metadata.script_lines,
            [{"speaker": "A", "text": "確認済みです。"}],
        )


if __name__ == "__main__":
    unittest.main()