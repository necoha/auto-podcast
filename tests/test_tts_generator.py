# pyright: reportPrivateUsage=false

import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, call, patch

from tts_generator import (
    TTSGenerator,
    TTSRequestBudgetExceeded,
    TransientTTSError,
)


def _response(*parts: Any, finish_reason: str = "STOP") -> SimpleNamespace:
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(parts=list(parts)),
                finish_reason=finish_reason,
            )
        ]
    )


def _audio_part(
    data: bytes | None,
    mime_type: str = "audio/L16;codec=pcm;rate=24000",
) -> SimpleNamespace:
    return SimpleNamespace(
        inline_data=SimpleNamespace(data=data, mime_type=mime_type)
    )


def _generator(*responses: Any) -> tuple[TTSGenerator, Mock]:
    generator = TTSGenerator.__new__(TTSGenerator)
    generate_content = Mock(side_effect=responses)
    cast(Any, generator).client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate_content)
    )
    generator.model = "test-model"
    generator.host_name = "Host"
    generator.voice_a = "Kore"
    generator.guest_name = "Guest"
    generator.voice_b = "Charon"
    return generator, generate_content


class TTSResponseTests(unittest.TestCase):
    def test_empty_audio_is_retried(self):
        generator, generate_content = _generator(
            _response(_audio_part(None), finish_reason="OTHER"),
            _response(_audio_part(b"pcm")),
        )

        with patch("tts_generator.RETRY_DELAY", 0):
            result = generator._generate_with_retry("test prompt")

        self.assertEqual(result, b"pcm")
        self.assertEqual(generate_content.call_count, 2)

    def test_missing_candidates_is_transient(self):
        generator, _ = _generator(SimpleNamespace(candidates=[]))

        with self.assertRaisesRegex(TransientTTSError, "候補"):
            generator._call_tts_api("test prompt")

    def test_transient_errors_use_exponential_backoff(self):
        generator, _ = _generator()
        generator._call_tts_api = Mock(
            side_effect=[TransientTTSError("busy")] * 4
        )

        with patch("tts_generator.time.sleep") as sleep:
            with self.assertRaisesRegex(TransientTTSError, "busy"):
                generator._generate_with_retry("test prompt")

        self.assertEqual(generator._call_tts_api.call_count, 4)
        self.assertEqual(
            sleep.call_args_list,
            [call(30.0), call(60.0), call(120.0)],
        )

    def test_503_response_is_retried(self):
        generator, _ = _generator()
        generator._call_tts_api = Mock(
            side_effect=[RuntimeError("503 UNAVAILABLE"), b"pcm"]
        )

        with patch("tts_generator.time.sleep"):
            result = generator._generate_with_retry("test prompt")

        self.assertEqual(result, b"pcm")
        self.assertEqual(generator._call_tts_api.call_count, 2)

    def test_request_budget_is_shared_across_chunks(self):
        generator, _ = _generator()
        generator.request_budget = 3
        generator.requests_made = 0
        generator._call_tts_api = Mock(
            side_effect=[b"first", TransientTTSError("busy"), b"second"]
        )

        with patch("tts_generator.time.sleep"):
            self.assertEqual(generator._generate_with_retry("chunk 1"), b"first")
            self.assertEqual(generator._generate_with_retry("chunk 2"), b"second")
            with self.assertRaisesRegex(TTSRequestBudgetExceeded, "3/3"):
                generator._generate_with_retry("chunk 3")

        self.assertEqual(generator._call_tts_api.call_count, 3)
        self.assertEqual(generator.requests_made, 3)

    def test_audio_is_found_in_later_part(self):
        generator, _ = _generator(
            _response(
                SimpleNamespace(inline_data=None),
                _audio_part(b"pcm"),
            )
        )

        self.assertEqual(generator._call_tts_api("test prompt"), b"pcm")


if __name__ == "__main__":
    unittest.main()