# pyright: reportPrivateUsage=false

import os
import subprocess
import sys
import unittest

from script_generator import ScriptGenerator, ScriptLine
from tts_generator import TTSGenerator


class ModelConfigurationTests(unittest.TestCase):
    def test_model_overrides_and_empty_defaults(self):
        model_cases = (
            ("", "", "gemini-3.8-flash gemini-3.1-flash-tts-preview"),
            (
                "gemini-2.5-flash",
                "gemini-2.5-flash-preview-tts",
                "gemini-2.5-flash gemini-2.5-flash-preview-tts",
            ),
        )
        for llm_model, tts_model, expected in model_cases:
            environment = dict(os.environ, LLM_MODEL=llm_model, TTS_MODEL=tts_model)
            output = subprocess.check_output(
                [sys.executable, "-c", "import config; print(config.LLM_MODEL, config.TTS_MODEL)"],
                env=environment,
                text=True,
            )
            self.assertEqual(output.strip(), expected)


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


if __name__ == "__main__":
    unittest.main()