"""
TTS音声生成モジュール
Gemini Flash TTS Multi-Speaker APIを使い、台本テキストから音声ファイルを生成する

Multi-Speaker TTS により台本全体を1回のAPIコールで音声化するため、
レート制限（Free Tier 3 RPM）の影響を受けない。
"""

import io
import logging
import time
import wave
import os
from typing import List, Optional

from google import genai
from google.genai import types

import config
from script_generator import Script, ScriptLine

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2  # 16-bit

# Multi-Speaker TTS の話者名（プロンプト内の名前と一致させる）
SPEAKER_NAME_A = "HostA"
SPEAKER_NAME_B = "GuestB"

MAX_RETRIES = 3
RETRY_DELAY = 30.0  # 429エラー時のリトライ待機秒数


class TTSGenerator:
    """Gemini Flash TTS Multi-Speaker APIで台本から音声ファイルを生成する

    台本全体を1回のAPIコールで処理するため、レート制限の問題が発生しない。
    """

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
        """台本全体から音声ファイルを生成する（Multi-Speaker TTS 1回コール）

        Args:
            script: ScriptLineのリスト
            output_path: 出力ファイルパス (.wav)

        Returns:
            出力ファイルパス
        """
        if not script:
            raise ValueError("台本が空です")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # 台本を Multi-Speaker プロンプト形式に変換
        prompt = self._build_multi_speaker_prompt(script)
        logger.info(
            "Multi-Speaker TTS生成開始 (話者A=%s, 話者B=%s, %d行)",
            self.voice_a, self.voice_b, len(script),
        )

        # リトライ付きでTTS APIを呼び出し
        pcm_data = self._generate_with_retry(prompt)

        # WAVファイルとして保存
        self._save_audio(pcm_data, output_path)
        logger.info("音声ファイル生成完了: %s", output_path)
        return output_path

    def _build_multi_speaker_prompt(self, script: Script) -> str:
        """ScriptLineリストをMulti-Speaker TTSプロンプト文字列に変換する

        出力例:
            HostA: こんにちは、今日のニュースをお届けします。
            GuestB: よろしくお願いします。
        """
        lines = []
        for line in script:
            name = SPEAKER_NAME_A if line.speaker == "A" else SPEAKER_NAME_B
            lines.append(f"{name}: {line.text}")
        return "\n".join(lines)

    def _generate_with_retry(self, prompt: str) -> bytes:
        """リトライ付き Multi-Speaker TTS API 呼び出し"""
        for attempt in range(MAX_RETRIES):
            try:
                if attempt > 0:
                    wait = RETRY_DELAY * attempt
                    logger.info("  リトライ待機: %.0f秒...", wait)
                    time.sleep(wait)

                return self._call_tts_api(prompt)

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(
                            "  レート制限 (試行%d/%d)、リトライします",
                            attempt + 1, MAX_RETRIES,
                        )
                        continue
                raise
        raise RuntimeError(f"TTS生成に{MAX_RETRIES}回失敗しました")

    def _call_tts_api(self, prompt: str) -> bytes:
        """Multi-Speaker TTS API 呼び出し→PCMバイナリを返す"""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            types.SpeakerVoiceConfig(
                                speaker=SPEAKER_NAME_A,
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=self.voice_a,
                                    )
                                ),
                            ),
                            types.SpeakerVoiceConfig(
                                speaker=SPEAKER_NAME_B,
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=self.voice_b,
                                    )
                                ),
                            ),
                        ]
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

        logger.info("  音声データ取得: %d bytes, mime=%s", len(audio_bytes), mime_type)
        return audio_bytes

    def _extract_pcm_from_wav(self, wav_bytes: bytes) -> bytes:
        """WAVバイナリからPCMデータ部分のみを抽出する"""
        try:
            buf = io.BytesIO(wav_bytes)
            with wave.open(buf, 'rb') as wf:
                return wf.readframes(wf.getnframes())
        except Exception:
            logger.warning("WAVヘッダー解析失敗、生データとして扱います")
            return wav_bytes

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
