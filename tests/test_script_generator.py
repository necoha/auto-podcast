# pyright: reportPrivateUsage=false

import json
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from google.genai import errors

from deep_podcast_generator import DeepDivePodcastGenerator
from deep_script_generator import DeepScriptGenerator
from podcast_generator import PodcastGenerator
from script_generator import ScriptGenerator, ScriptLine
from tts_generator import TTSGenerator


class ModelFailoverTests(unittest.TestCase):
    def setUp(self):
        wait_patch = patch("time.sleep")
        self.wait = wait_patch.start()
        self.addCleanup(wait_patch.stop)
        logger_patch = patch("script_generator.logger")
        self.logger = logger_patch.start()
        self.addCleanup(logger_patch.stop)

    @staticmethod
    def _response(line_count=5):
        return SimpleNamespace(text=json.dumps([
            {"speaker": "A" if index % 2 == 0 else "B", "text": f"News {index}"}
            for index in range(line_count)
        ]))

    def _generator(self, *responses, generator_type=ScriptGenerator, fallback_models=("backup-model",)):
        self.wait.reset_mock()
        with patch("script_generator.genai.Client") as client_factory, patch(
            "config.LLM_MODEL", "primary-model"
        ), patch(
            "config.LLM_FALLBACK_MODELS", list(fallback_models)
        ):
            generate_content = client_factory.return_value.models.generate_content
            generate_content.side_effect = responses
            generator = generator_type(api_key="test-key")
        return generator, generate_content

    def test_automatic_switch_after_primary_503_retries(self):
        for generator_type in (ScriptGenerator, DeepScriptGenerator):
            with self.subTest(generator=generator_type.__name__):
                error = errors.ServerError(503, {"error": {"message": "busy"}})
                generator, generate_content = self._generator(
                    *([error] * 5 + [self._response()]), generator_type=generator_type
                )
                script = generator.generate_script([{"title": "Test news"}])

                self.assertEqual(len(script), 5)
                self.assertEqual(generator.model, "backup-model")
                self.assertEqual(
                    [request.kwargs["model"] for request in generate_content.call_args_list],
                    ["primary-model"] * 5 + ["backup-model"],
                )
                self.assertEqual(
                    [request.args[0] for request in self.wait.call_args_list],
                    [60, 120, 180, 240],
                )

    def test_primary_success_does_not_use_backup(self):
        generator, generate_content = self._generator(self._response())

        generator.generate_script([{"title": "Test news"}])

        generate_content.assert_called_once()
        self.assertEqual(generate_content.call_args.kwargs["model"], "primary-model")
        self.wait.assert_not_called()

    def test_primary_retry_success_does_not_use_backup(self):
        generator, generate_content = self._generator(
            RuntimeError("503 UNAVAILABLE"), self._response()
        )

        generator.generate_script([{"title": "Test news"}])

        self.assertEqual(
            [request.kwargs["model"] for request in generate_content.call_args_list],
            ["primary-model", "primary-model"],
        )
        self.wait.assert_called_once_with(60)

    def test_all_unavailable_models_stop_after_bounded_retries(self):
        generator, generate_content = self._generator(
            *([RuntimeError("503 UNAVAILABLE")] * 10)
        )

        with self.assertRaisesRegex(RuntimeError, "503"):
            generator.generate_script([{"title": "Test news"}])

        self.assertEqual(
            [request.kwargs["model"] for request in generate_content.call_args_list],
            ["primary-model"] * 5 + ["backup-model"] * 5,
        )
        self.assertEqual(
            [request.args[0] for request in self.wait.call_args_list],
            [60, 120, 180, 240] * 2,
        )

    def test_client_error_codes_do_not_switch_even_if_message_mentions_503(self):
        for code in (400, 403, 404, 429):
            with self.subTest(code=code):
                error = errors.ClientError(code, {"error": {"message": "Diagnostic mentions 503 UNAVAILABLE"}})
                generator, generate_content = self._generator(error)

                with self.assertRaises(errors.ClientError):
                    generator.generate_script([{"title": "Test news"}])

                generate_content.assert_called_once()
                self.wait.assert_not_called()

    def test_candidates_are_ordered_unique_and_restart_with_primary(self):
        generator, generate_content = self._generator(
            *([RuntimeError("503 UNAVAILABLE")] * 10 + [self._response(), self._response()]),
            fallback_models=("primary-model", "backup-model", "backup-model", "last-model"),
        )

        generator.generate_script([{"title": "Test news"}])
        self.assertEqual(generator.model, "last-model")
        generator.generate_script([{"title": "Next news"}])

        self.assertEqual(generator.model, "primary-model")
        self.assertEqual(
            [request.kwargs["model"] for request in generate_content.call_args_list],
            ["primary-model"] * 5 + ["backup-model"] * 5 + ["last-model", "primary-model"],
        )

    def test_short_script_retries_same_model_then_succeeds(self):
        generator, generate_content = self._generator(self._response(1), self._response())

        script = generator.generate_script([{"title": "Test news"}])

        self.assertEqual(len(script), 5)
        self.assertEqual(generator.model, "primary-model")
        self.assertEqual(generate_content.call_count, 2)
        self.wait.assert_called_once_with(60)

    def test_short_script_exhaustion_does_not_switch_models(self):
        generator, generate_content = self._generator(*([self._response(1)] * 5))

        with self.assertRaisesRegex(ValueError, "台本が短すぎます"):
            generator.generate_script([{"title": "Test news"}])

        self.assertEqual(generator.model, "primary-model")
        self.assertEqual(generate_content.call_count, 5)

    def test_parse_error_mentioning_503_does_not_switch_models(self):
        generator, generate_content = self._generator(self._response())

        with patch.object(
            generator, "_parse_response", side_effect=ValueError("Invalid JSON containing 503 UNAVAILABLE")
        ), self.assertRaisesRegex(ValueError, "Invalid JSON"):
            generator.generate_script([{"title": "Test news"}])

        generate_content.assert_called_once()
        self.wait.assert_not_called()

    def test_empty_articles_do_not_call_api(self):
        generator, generate_content = self._generator()

        with self.assertRaisesRegex(ValueError, "記事リストが空"):
            generator.generate_script([])

        generate_content.assert_not_called()


class PipelineModelSelectionTests(unittest.TestCase):
    @staticmethod
    def _generator(podcast_type):
        generator = podcast_type.__new__(podcast_type)
        generator.host_name = "Host"
        generator.guest_name = "Guest"
        generator.content_manager = Mock()
        generator.content_manager.fetch_rss_feeds.return_value = [{"title": "Test news"}]
        generator.script_generator = Mock(model="backup-model")
        generator.script_generator._apply_pronunciation_fixes.side_effect = lambda script: script
        generator.script_reviewer = Mock(model="primary-model")
        generator.script_reviewer.review.side_effect = lambda script, articles: script
        generator.tts_generator = Mock()
        generator.tts_generator.generate_audio.side_effect = RuntimeError("Stop after script checks")
        generator._get_episode_number = Mock(return_value=1)
        return generator

    def test_pipelines_use_successful_model_for_review(self):
        for podcast_type in (PodcastGenerator, DeepDivePodcastGenerator):
            with self.subTest(edition=podcast_type.__name__):
                generator = self._generator(podcast_type)
                script = [ScriptLine(speaker="A", text="News")] * 5
                generator.script_generator.generate_script.return_value = script

                with self.assertLogs(podcast_type.__module__, level="INFO"):
                    self.assertIsNone(generator.generate())

                generator.script_generator.generate_script.assert_called_once()
                generator.script_reviewer.review.assert_called_once()
                self.assertEqual(generator.script_reviewer.model, "backup-model")

    def test_pipelines_do_not_retry_exhausted_model_chain(self):
        for podcast_type in (PodcastGenerator, DeepDivePodcastGenerator):
            with self.subTest(edition=podcast_type.__name__):
                generator = self._generator(podcast_type)
                generator.script_generator.generate_script.side_effect = RuntimeError("503 UNAVAILABLE")

                with patch("time.sleep"), self.assertLogs(podcast_type.__module__, level="INFO"):
                    self.assertIsNone(generator.generate())

                generator.script_generator.generate_script.assert_called_once()
                generator.script_reviewer.review.assert_not_called()
                announcement = generator.tts_generator.generate_audio.call_args.args[0]
                self.assertEqual(
                    [line.speaker for line in announcement],
                    ["A", "B", "A", "B", "A"],
                )


class ModelConfigurationTests(unittest.TestCase):
    def test_model_overrides_and_empty_defaults(self):
        model_cases = (
            ("", "", "", "gemini-3.8-flash gemini-2.5-flash-preview-tts 0.8"),
            (
                "gemini-2.5-flash",
                "gemini-3.1-flash-tts-preview",
                "1.0",
                "gemini-2.5-flash gemini-3.1-flash-tts-preview 1.0",
            ),
        )
        for llm_model, tts_model, tempo, expected in model_cases:
            environment = dict(os.environ, LLM_MODEL=llm_model, TTS_MODEL=tts_model, TTS_TEMPO=tempo)
            output = subprocess.check_output(
                [sys.executable, "-c", "import config; print(config.LLM_MODEL, config.TTS_MODEL, config.TTS_TEMPO)"],
                env=environment,
                text=True,
            )
            self.assertEqual(output.strip(), expected)

    def test_fallback_model_defaults_and_custom_order(self):
        model_cases = (
            ("", ["gemini-2.5-flash"]),
            (" backup-one, backup-two, ,backup-one ", ["backup-one", "backup-two", "backup-one"]),
        )
        for configured, expected in model_cases:
            with self.subTest(configured=configured):
                environment = dict(os.environ, LLM_FALLBACK_MODELS=configured)
                output = subprocess.check_output(
                    [sys.executable, "-c", "import config, json; print(json.dumps(config.LLM_FALLBACK_MODELS))"],
                    env=environment,
                    text=True,
                )
                self.assertEqual(json.loads(output), expected)


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

    def test_news_pronunciation_distinguishes_rice_from_country(self):
        generator = TTSGenerator.__new__(TTSGenerator)

        prepared = generator._prepare_for_tts(
            "今日も米価格、米の値段、米不足、米価、傘下を紹介します。製品の輪郭と米国と米中の話題もあります。"
        )

        self.assertIn("キョウモ", prepared)
        self.assertIn("コメ価格", prepared)
        self.assertIn("コメの値段", prepared)
        self.assertIn("コメ不足", prepared)
        self.assertIn("ベイカ", prepared)
        self.assertIn("サンカ", prepared)
        self.assertIn("リンカク", prepared)
        self.assertIn("米国と米中", prepared)


if __name__ == "__main__":
    unittest.main()