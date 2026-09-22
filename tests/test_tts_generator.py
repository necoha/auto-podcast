# pyright: reportPrivateUsage=false

import base64
import io
import unittest
import wave
from array import array
from math import pi, sin
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, call, patch

from script_generator import ScriptLine
from tts_generator import (
    TTSGenerator,
    TTSRequestBudgetExceeded,
    TransientTTSError,
)


def _response(*outputs: Any, status: str = "completed") -> SimpleNamespace:
    return SimpleNamespace(outputs=list(outputs), status=status)


def _audio_output(
    data: bytes | None,
    mime_type: str = "audio/pcm;rate=24000",
) -> SimpleNamespace:
    encoded = base64.b64encode(data).decode("ascii") if data is not None else None
    return SimpleNamespace(type="audio", data=encoded, mime_type=mime_type)


def _generator(*responses: Any) -> tuple[TTSGenerator, Mock]:
    generator = TTSGenerator.__new__(TTSGenerator)
    create_interaction = Mock(side_effect=responses)
    cast(Any, generator).client = SimpleNamespace(
        interactions=SimpleNamespace(create=create_interaction)
    )
    generator.model = "test-model"
    generator.host_name = "Host"
    generator.voice_a = "Kore"
    generator.guest_name = "Guest"
    generator.voice_b = "Charon"
    return generator, create_interaction


def _wave(seconds: float, seed: int = 0) -> bytes:
    samples = array('h')
    sample_count = int(24000 * seconds)
    block_size = int(24000 * 0.1)
    for index in range(sample_count):
        block = index // block_size
        frequency = 170 + ((block * 47 + seed * 83) % 430)
        amplitude = 4000 + ((block * 811 + seed * 997) % 9000)
        samples.append(
            int(amplitude * sin(2 * pi * frequency * index / 24000))
        )
    return samples.tobytes()


class TTSResponseTests(unittest.TestCase):
    @patch("tts_generator.genai.Client")
    def test_client_uses_bounded_http_policy(self, client: Mock):
        TTSGenerator(
            api_key="test-key",
            host_name="Host",
            host_voice="Kore",
            guest_name="Guest",
            guest_voice="Charon",
        )

        http_options = client.call_args.kwargs["http_options"]
        self.assertEqual(http_options.timeout, 300_000)
        self.assertEqual(http_options.retry_options.attempts, 0)

    def test_split_script_keeps_turn_pairs_within_twenty_lines(self):
        script = [
            ScriptLine(
                speaker="A" if index % 2 == 0 else "B",
                text=f"line {index}",
            )
            for index in range(45)
        ]

        chunks = TTSGenerator._split_script(script, 20)

        self.assertEqual([len(chunk) for chunk in chunks], [20, 20, 5])
        self.assertTrue(all(chunk[-1].speaker == "B" for chunk in chunks[:-1]))
        self.assertTrue(all(chunk[0].speaker == "A" for chunk in chunks))

    def test_empty_audio_is_retried(self):
        generator, create_interaction = _generator(
            _response(_audio_output(None), status="incomplete"),
            _response(_audio_output(b"pcm")),
        )

        with patch("tts_generator.RETRY_DELAY", 0):
            result = generator._generate_with_retry("test prompt")

        self.assertEqual(result, b"pcm")
        self.assertEqual(create_interaction.call_count, 2)

    def test_missing_outputs_is_transient(self):
        generator, _ = _generator(SimpleNamespace(outputs=[], status="failed"))

        with self.assertRaisesRegex(TransientTTSError, "音声データ"):
            generator._call_tts_api("test prompt")

    def test_invalid_base64_is_transient(self):
        generator, _ = _generator(
            _response(
                SimpleNamespace(
                    type="audio",
                    data="not-base64!",
                    mime_type="audio/pcm",
                )
            )
        )

        with self.assertRaisesRegex(TransientTTSError, "Base64"):
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

    def test_audio_is_found_in_later_output(self):
        generator, create_interaction = _generator(
            _response(
                SimpleNamespace(type="text", data="ignored", mime_type=None),
                _audio_output(b"pcm"),
            )
        )

        self.assertEqual(generator._call_tts_api("test prompt"), b"pcm")
        request = create_interaction.call_args.kwargs
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(request["response_format"], {"type": "audio"})
        self.assertEqual(
            request["generation_config"]["speech_config"],
            [
                {"speaker": "Host", "voice": "Kore"},
                {"speaker": "Guest", "voice": "Charon"},
            ],
        )

    def test_wav_output_is_converted_to_pcm(self):
        pcm = b"\x01\x00\x02\x00"
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes(pcm)
        generator, _ = _generator(
            _response(_audio_output(wav_buffer.getvalue(), "audio/wav"))
        )

        self.assertEqual(generator._call_tts_api("test prompt"), pcm)

    def test_invalid_wav_is_transient(self):
        generator, _ = _generator(
            _response(_audio_output(b"not-a-wave", "audio/wav"))
        )

        with self.assertRaisesRegex(TransientTTSError, "WAV"):
            generator._call_tts_api("test prompt")

    def test_unsupported_audio_format_is_transient(self):
        generator, _ = _generator(
            _response(_audio_output(b"compressed", "audio/mp3"))
        )

        with self.assertRaisesRegex(TransientTTSError, "audio/mp3"):
            generator._call_tts_api("test prompt")

    def test_repeated_prefix_is_trimmed(self):
        prefix = _wave(0.8)
        audio = prefix + prefix + _wave(0.8, seed=1)

        with patch.multiple(
            "tts_generator",
            REPEATED_PREFIX_WINDOW_SEC=0.4,
            REPEATED_PREFIX_SEARCH_START_SEC=0.5,
            REPEATED_PREFIX_SEARCH_END_SEC=1.2,
            REPEATED_PREFIX_WAVEFORM_WINDOW_SEC=0.2,
        ):
            trimmed = TTSGenerator._trim_repeated_prefix(audio)

        self.assertEqual(trimmed, audio[len(prefix):])

    def test_non_repeated_audio_is_unchanged(self):
        audio = _wave(0.8) + _wave(0.8, seed=1) + _wave(0.8, seed=2)

        with patch.multiple(
            "tts_generator",
            REPEATED_PREFIX_WINDOW_SEC=0.4,
            REPEATED_PREFIX_SEARCH_START_SEC=0.5,
            REPEATED_PREFIX_SEARCH_END_SEC=1.2,
            REPEATED_PREFIX_WAVEFORM_WINDOW_SEC=0.2,
        ):
            trimmed = TTSGenerator._trim_repeated_prefix(audio)

        self.assertEqual(trimmed, audio)

    def test_prompt_forbids_restarting_transcript(self):
        self.assertIn("先頭から末尾まで一度だけ", TTSGenerator.DIRECTOR_NOTES_TEMPLATE)
        self.assertIn("途中で先頭に戻ったり", TTSGenerator.DIRECTOR_NOTES_TEMPLATE)


if __name__ == "__main__":
    unittest.main()