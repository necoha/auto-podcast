# pyright: reportPrivateUsage=false, reportAttributeAccessIssue=false

import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

from deep_podcast_generator import DeepDivePodcastGenerator
from podcast_generator import PodcastGenerator
from podcast_uploader import EpisodeMetadata
from script_generator import Script, ScriptLine
from script_reviewer import FactVerificationError


ARTICLES = [
    {"title": "見出しA", "source": "媒体A", "link": "https://example.com/a"},
    {"title": "見出しB", "source": "媒体B", "link": "https://example.com/b"},
]
UNVERIFIED_SCRIPT = [
    ScriptLine(speaker="A", text="裏付けのない具体的な説明です。"),
    ScriptLine(speaker="B", text="政策金利は0.5%です。"),
]


def _metadata() -> EpisodeMetadata:
    return EpisodeMetadata(
        title="title",
        description="description",
        episode_number=1,
        published_date="2026-09-21",
        source_articles=ARTICLES,
    )


def _identity_script(script: Script) -> Script:
    return script


def _configure_generator(generator: Any) -> None:
    generator.host_name = "ホスト"
    generator.guest_name = "ゲスト"
    generator.content_manager = SimpleNamespace(
        fetch_rss_feeds=Mock(return_value=ARTICLES)
    )
    generator.script_generator = SimpleNamespace(
        generate_script=Mock(return_value=UNVERIFIED_SCRIPT),
        _apply_pronunciation_fixes=Mock(side_effect=_identity_script),
    )
    generator.script_reviewer = SimpleNamespace(
        review=Mock(side_effect=FactVerificationError("verification failed")),
        last_verification_urls=[],
    )
    generator.tts_generator = SimpleNamespace(generate_audio=Mock())
    generator.rss_generator = SimpleNamespace(add_episode=Mock())
    generator.uploader = SimpleNamespace(upload=Mock(return_value=True))
    generator._get_episode_number = Mock(return_value=1)
    generator._convert_to_mp3 = Mock(return_value="/tmp/fact-gate-test.mp3")
    generator._build_metadata = Mock(return_value=_metadata())


class FactGateIntegrationTests(unittest.TestCase):
    def test_breaking_news_discards_unverified_script(self):
        generator = cast(Any, PodcastGenerator.__new__(PodcastGenerator))
        _configure_generator(generator)

        generator.generate()

        script = generator.tts_generator.generate_audio.call_args.args[0]
        text = "\n".join(line.text for line in script)
        self.assertNotIn("政策金利は0.5%", text)
        self.assertIn("見出しAというニュースです", text)
        self.assertTrue(
            generator.script_reviewer.review.call_args.kwargs[
                "require_all_articles"
            ]
        )
        self.assertEqual(
            generator._build_metadata.call_args.kwargs["verification_status"],
            "title_only_fallback",
        )

    def test_deep_dive_discards_unverified_script(self):
        generator = cast(
            Any,
            DeepDivePodcastGenerator.__new__(DeepDivePodcastGenerator),
        )
        _configure_generator(generator)

        generator.generate()

        script = generator.tts_generator.generate_audio.call_args.args[0]
        text = "\n".join(line.text for line in script)
        self.assertNotIn("政策金利は0.5%", text)
        self.assertIn("見出しAというニュースです", text)
        self.assertFalse(
            generator.script_reviewer.review.call_args.kwargs[
                "require_all_articles"
            ]
        )
        self.assertEqual(
            generator._build_metadata.call_args.kwargs["verification_status"],
            "title_only_fallback",
        )


if __name__ == "__main__":
    unittest.main()