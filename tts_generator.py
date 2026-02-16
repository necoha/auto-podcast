"""
TTS音声生成モジュール
Gemini Flash TTS APIを使い、台本テキストから音声ファイルを生成する
"""

import io
import logging
import struct
import wave
import os
from typing import List, Optional

from google import genai
from google.genai import types

import config
from script_generator import Script, ScriptLine

logger = logging.getLogger(__name__)

# 無音セグメント: 500ms @ 24kHz 16bit mono
SILENCE_DURATION_MS = 500
SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2  # 16-bit


def _generate_silence(duration_ms: int = SILENCE_DURATION_MS) -> bytes:
    """指定ミリ秒の無音PCMデータを生成する (16-bit mono)"""
    num_samples = int(SAMPLE_RATE * duration_ms / 1000)
    return b'\x00\x00' * num_samples


class TTSGenerator:
    """Gemini Flash TTS APIで台本から音声ファイルを生成する"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")
        self.client = genai.Client(api_key=self.api_key)
        self.model = config.TTS_MODEL
        # 話者ごとの音声設定
        self.voice_a = getattr(config, 'TTS_VOICE_A', config.TTS_VOICE)
        self.voice_b = getattr(config, 'TTS_VOICE_B', 'Charon')

    def generate_audio(self, script: Script, output_path: str) -> str:
        """台本全体から音声ファイルを生成する

        Args:
            script: ScriptLineのリスト
            output_path: 出力ファイルパス (.wav)

        Returns:
            出力ファイルパス
        """
        if not script:
            raise ValueError("台本が空です")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        segments: List[bytes] = []
        total = len(script)
        silence = _generate_silence()

        for i, line in enumerate(script):
            voice = self.voice_a if line.speaker == "A" else self.voice_b
            logger.info(
                "TTS生成中 [%d/%d] 話者%s (%s): %s...",
                i + 1, total, line.speaker, voice,
                line.text[:30]
            )

            try:
                pcm = self._generate_segment(line.text, voice)
                segments.append(pcm)
                # セグメント間に無音を挿入
                if i < total - 1:
                    segments.append(silence)
            except Exception as e:
                logger.warning("TTSセグメント生成失敗 [%d/%d]: %s", i + 1, total, e)
                # 失敗セグメントは無音で埋める（1秒）
                segments.append(_generate_silence(1000))

        if not any(len(s) > 0 for s in segments):
            raise RuntimeError("全てのTTSセグメント生成に失敗しました")

        # 全セグメントを結合
        combined = self._concatenate_segments(segments)

        # WAVファイルとして保存
        self._save_audio(combined, output_path)
        logger.info("音声ファイル生成完了: %s", output_path)
        return output_path

    def _generate_segment(self, text: str, voice: str) -> bytes:
        """1発話分のTTS API呼び出しを行い、PCMバイナリを返す"""
        response = self.client.models.generate_content(
            model=self.model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_id=voice,
                    )
                ),
            ),
        )

        # レスポンスから音声データ取得
        part = response.candidates[0].content.parts[0]
        if not hasattr(part, 'inline_data') or part.inline_data is None:
            raise RuntimeError("TTS応答に音声データが含まれていません")

        audio_bytes = part.inline_data.data
        mime_type = part.inline_data.mime_type or ""

        # WAV形式の場合はPCMデータのみ抽出
        if mime_type.startswith("audio/wav") or mime_type.startswith("audio/x-wav"):
            audio_bytes = self._extract_pcm_from_wav(audio_bytes)
        elif mime_type.startswith("audio/L16") or mime_type.startswith("audio/pcm"):
            pass  # すでにPCMデータ

        return audio_bytes

    def _extract_pcm_from_wav(self, wav_bytes: bytes) -> bytes:
        """WAVバイナリからPCMデータ部分のみを抽出する"""
        try:
            buf = io.BytesIO(wav_bytes)
            with wave.open(buf, 'rb') as wf:
                return wf.readframes(wf.getnframes())
        except Exception:
            # WAVヘッダーが不正な場合はそのまま返す
            logger.warning("WAVヘッダー解析失敗、生データとして扱います")
            return wav_bytes

    def _concatenate_segments(self, segments: List[bytes]) -> bytes:
        """複数のPCMセグメントを連結する"""
        return b''.join(segments)

    def _save_audio(self, pcm_data: bytes, output_path: str) -> str:
        """PCMデータをWAVファイルとして保存する"""
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(1)        # mono
            wf.setsampwidth(SAMPLE_WIDTH)  # 16-bit
            wf.setframerate(SAMPLE_RATE)   # 24kHz
            wf.writeframes(pcm_data)
        return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # テスト: 短い台本で音声生成
    test_script = [
        ScriptLine(speaker="A", text="こんにちは、今日のAIニュースをお届けします。"),
        ScriptLine(speaker="B", text="よろしくお願いします。今日も面白いニュースがありますね。"),
        ScriptLine(speaker="A", text="それでは早速いきましょう。"),
    ]

    gen = TTSGenerator()
    output = gen.generate_audio(test_script, "./audio_files/test_tts.wav")
    print(f"テスト音声生成完了: {output}")
