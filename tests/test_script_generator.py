# pyright: reportPrivateUsage=false

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from script_generator import (
    ScriptGenerator,
    ScriptLine,
    is_transient_generation_error,
)
from tts_generator import TTSGenerator


class PronunciationTests(unittest.TestCase):
    def test_unverified_readings_are_replaced_by_approved_dictionary(self):
        generator = ScriptGenerator.__new__(ScriptGenerator)
        script = [
            ScriptLine(
                speaker="A",
                text=(
                    "国（こく）の安全保障、中国（ちゅうこく）、"
                    "日本銀行（にほんぎんぎょう）、"
                    "中国銀行（ちゅうこくぎんぎょう）、"
                    "メガバンク各行（かくぎょう）、銀行（ぎんぎょう）、"
                    "Tailcat（テイルキャット）"
                ),
            )
        ]

        fixed = generator._apply_pronunciation_fixes(script)[0].text

        self.assertIn("国の安全保障", fixed)
        self.assertNotIn("国（こく）", fixed)
        self.assertIn("中国（ちゅうごく）", fixed)
        self.assertIn("日本銀行（にっぽんぎんこう）", fixed)
        self.assertIn("中国（ちゅうごく）銀行（ぎんこう）", fixed)
        self.assertIn("各行（かくこう）", fixed)
        self.assertIn("銀行（ぎんこう）", fixed)
        self.assertIn("Tailcat（テイルキャット）", fixed)

        prepared = TTSGenerator.__new__(TTSGenerator)._prepare_for_tts(fixed)
        self.assertIn("クニの安全保障", prepared)
        self.assertIn("ちゅうごく", prepared)
        self.assertIn("にっぽんぎんこう", prepared)
        self.assertIn("ちゅうごくぎんこう", prepared)
        self.assertIn("かくこう", prepared)
        self.assertIn("テイルキャット", prepared)
        self.assertNotIn("かくぎょう", prepared)

    def test_standalone_country_does_not_change_compound_words(self):
        generator = TTSGenerator.__new__(TTSGenerator)

        prepared = generator._prepare_for_tts(
            "国の制度、中国、米国、各国、国際関係、国家戦略"
        )

        self.assertEqual(
            prepared,
            "クニの制度、中国、米国、各国、国際関係、国家戦略",
        )


class GenerationRetryTests(unittest.TestCase):
    def test_generate_script_uses_selected_fallback_model(self):
        generate_content = Mock(
            return_value=SimpleNamespace(
                text=json.dumps(
                    [
                        {"speaker": "A", "text": f"発話{index}"}
                        for index in range(5)
                    ],
                    ensure_ascii=False,
                )
            )
        )
        generator = ScriptGenerator.__new__(ScriptGenerator)
        generator.client = SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content)
        )
        generator.model = "gemini-3.8-flash"
        generator.system_prompt = "test prompt"

        generator.generate_script(
            [
                {
                    "title": "記事",
                    "source": "媒体",
                    "link": "https://example.com/article",
                }
            ],
            model="gemini-3.7-flash",
        )

        self.assertEqual(
            generate_content.call_args.kwargs["model"],
            "gemini-3.7-flash",
        )

    def test_timeout_is_transient(self):
        self.assertTrue(
            is_transient_generation_error(RuntimeError("Request timed out"))
        )

    def test_quota_error_is_not_retried(self):
        self.assertFalse(
            is_transient_generation_error(RuntimeError("429 RESOURCE_EXHAUSTED"))
        )


if __name__ == "__main__":
    unittest.main()