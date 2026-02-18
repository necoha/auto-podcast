"""
TTS音声生成モジュール
Gemini Flash TTS Multi-Speaker APIを使い、台本テキストから音声ファイルを生成する

Multi-Speaker TTS により台本全体を1回のAPIコールで音声化するため、
レート制限（Free Tier 3 RPM）の影響を受けない。
"""

import io
import logging
import re
import time
import wave
import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from google import genai
from google.genai import types

import config
from script_generator import Script, ScriptLine

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2  # 16-bit

MAX_RETRIES = 3
RETRY_DELAY = 30.0  # 429エラー時のリトライ待機秒数
CHUNK_DELAY = 5.0   # チャンク間のAPI待機秒数
SILENCE_PADDING_SEC = 0.8  # 末尾に追加する無音（秒）

JST = timezone(timedelta(hours=9))


def get_daily_speakers() -> Tuple[str, str, str, str]:
    """曜日に応じたホスト・ゲスト情報を返す

    Returns:
        (host_name, host_voice, guest_name, guest_voice)
    """
    weekday = datetime.now(JST).weekday()  # 0=月, 6=日
    daily = getattr(config, 'DAILY_SPEAKERS', None)
    if daily and weekday in daily:
        return daily[weekday]
    # フォールバック
    return ("アオイ", config.TTS_VOICE_A, "タクミ", config.TTS_VOICE_B)


class TTSGenerator:
    """Gemini Flash TTS Multi-Speaker APIで台本から音声ファイルを生成する

    台本全体を1回のAPIコールで処理するため、レート制限の問題が発生しない。
    曜日ローテーションで7ペア×2人 = 14人の出演者を切り替える。
    """

    def __init__(self, api_key: Optional[str] = None,
                 host_name: Optional[str] = None,
                 host_voice: Optional[str] = None,
                 guest_name: Optional[str] = None,
                 guest_voice: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")
        self.client = genai.Client(api_key=self.api_key)
        self.model = config.TTS_MODEL

        # 曜日ローテーションから取得（明示的に指定された場合はそちらを優先）
        daily = get_daily_speakers()
        self.host_name = host_name or daily[0]
        self.voice_a = host_voice or daily[1]
        self.guest_name = guest_name or daily[2]
        self.voice_b = guest_voice or daily[3]

    def generate_audio(self, script: Script, output_path: str) -> str:
        """台本から音声ファイルを生成する

        台本をチャンクに分割し、各チャンクを個別のTTS APIコールで
        音声化してからPCMデータを結合する。これにより出力トークン
        上限による末尾切れを防止する。

        Args:
            script: ScriptLineのリスト
            output_path: 出力ファイルパス (.wav)

        Returns:
            出力ファイルパス
        """
        if not script:
            raise ValueError("台本が空です")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        chunk_size = getattr(config, 'TTS_CHUNK_LINES', 12)
        chunks = self._split_script(script, chunk_size)

        logger.info(
            "Multi-Speaker TTS生成開始 (ホスト=%s[%s], ゲスト=%s[%s], %d行, %dチャンク)",
            self.host_name, self.voice_a, self.guest_name, self.voice_b,
            len(script), len(chunks),
        )

        all_pcm = bytearray()
        for i, chunk in enumerate(chunks):
            # チャンク間で少し待機（レート制限回避）
            if i > 0:
                logger.info("  チャンク間待機: %.0f秒...", CHUNK_DELAY)
                time.sleep(CHUNK_DELAY)

            prompt = self._build_multi_speaker_prompt(chunk)
            logger.info("  チャンク %d/%d (%d行) TTS生成中...", i + 1, len(chunks), len(chunk))
            pcm_data = self._generate_with_retry(prompt)
            all_pcm.extend(pcm_data)
            logger.info("  チャンク %d/%d 完了 (%d bytes)", i + 1, len(chunks), len(pcm_data))

        # 末尾に無音を追加（ぶつ切り防止）
        silence = self._generate_silence(SILENCE_PADDING_SEC)
        all_pcm.extend(silence)

        # WAVファイルとして保存
        self._save_audio(bytes(all_pcm), output_path)
        logger.info("音声ファイル生成完了: %s (合計 %d bytes)", output_path, len(all_pcm))
        return output_path

    @staticmethod
    def _split_script(script: Script, chunk_size: int) -> List[Script]:
        """台本をチャンクに分割する

        同じ話者の発話が途中で切れないよう、チャンク境界を調整する。
        次のチャンクが話者A（ホスト）で始まるよう、分割位置をずらす。
        """
        if len(script) <= chunk_size:
            return [script]

        chunks: List[Script] = []
        i = 0
        while i < len(script):
            end = min(i + chunk_size, len(script))
            # 末尾が会話の途中にならないよう、話者Aの開始位置までずらす
            if end < len(script):
                min_end = max(i + chunk_size // 3, i + 1)
                for j in range(end, min_end - 1, -1):
                    if script[j].speaker == "A":
                        end = j
                        break
            chunks.append(script[i:end])
            i = end
        return chunks

    @staticmethod
    def _generate_silence(seconds: float) -> bytes:
        """指定秒数の無音PCMデータを生成する"""
        num_samples = int(SAMPLE_RATE * seconds)
        return b'\x00' * (num_samples * SAMPLE_WIDTH)

    DIRECTOR_NOTES_TEMPLATE = """### DIRECTOR'S NOTES
Language: 日本語（Japanese）
Style: 明るく親しみやすいテクノロジー系ポッドキャスト。
Pacing: 落ち着いたテンポで、聞き取りやすく話す。
Pronunciation:
- 括弧内のカタカナ読みに従って発音すること。
  例: GitHub（ギットハブ） → 「ギットハブ」と読む
- 括弧自体は読み上げない。
- 英語の単語が出た場合は自然な日本語アクセントで読む。

### TRANSCRIPT
"""

    def _build_multi_speaker_prompt(self, script: Script) -> str:
        """台本を Multi-Speaker TTS プロンプトに変換する

        台本中の speaker:"A" をホスト名、"B" をゲスト名にマッピング。
        英字固有名詞はカタカナ読みに置換して TTS の誤読を防ぐ。
        """
        lines = []
        for line in script:
            name = self.host_name if line.speaker == "A" else self.guest_name
            text = self._prepare_for_tts(line.text)
            lines.append(f"{name}: {text}")
        transcript = "\n".join(lines)
        return self.DIRECTOR_NOTES_TEMPLATE + transcript

    def _prepare_for_tts(self, text: str) -> str:
        """テキストをTTS向けに前処理する

        1. 英字の固有名詞（読み）→ 読みのみに置換
           例: GIGAZINE（ギガジン） → ギガジン
        2. 漢字の読みアノテーション（ひらがな）は括弧部分を除去
           例: 脆弱性（ぜいじゃくせい） → 脆弱性
        """
        # 英字（+数字・記号）の後に（読み）が付いている → 読みだけに置換
        text = re.sub(
            r'[A-Za-z][A-Za-z0-9./_\-]*(?:\s[A-Za-z][A-Za-z0-9./_\-]*)*（([^）]+)）',
            r'\1',
            text,
        )
        # 漢字の後に（ひらがな/カタカナ読み）→ 括弧ごと除去（漢字はTTSが読める）
        text = re.sub(r'（[ぁ-ゟァ-ヿー\s]+）', '', text)
        return text

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
                                speaker=self.host_name,
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=self.voice_a,
                                    )
                                ),
                            ),
                            types.SpeakerVoiceConfig(
                                speaker=self.guest_name,
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
