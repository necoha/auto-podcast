"""
ポッドキャスト生成オーケストレーター
コンテンツ収集 → 台本生成 → 音声生成 → MP3変換 → RSS更新 → メタデータ保存
"""

import logging
import os
from datetime import date, datetime
from typing import Optional

from pydub import AudioSegment

import config
from content_manager import ContentManager
from script_generator import ScriptGenerator, Script, fallback_script
from tts_generator import TTSGenerator, get_daily_speakers
from rss_feed_generator import RSSFeedGenerator
from podcast_uploader import PodcastUploader, EpisodeMetadata

logger = logging.getLogger(__name__)


class PodcastGenerator:
    """ポッドキャスト生成の全体オーケストレーション"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")

        # 曜日ローテーションで出演者を決定
        host_name, host_voice, guest_name, guest_voice = get_daily_speakers()
        self.host_name = host_name
        self.guest_name = guest_name
        logger.info(
            "本日の出演者: %s(%s) & %s(%s)",
            host_name, host_voice, guest_name, guest_voice,
        )

        self.content_manager = ContentManager()
        self.script_generator = ScriptGenerator(
            api_key=self.api_key,
            host_name=host_name,
            guest_name=guest_name,
        )
        self.tts_generator = TTSGenerator(
            api_key=self.api_key,
            host_name=host_name,
            host_voice=host_voice,
            guest_name=guest_name,
            guest_voice=guest_voice,
        )
        self.rss_generator = RSSFeedGenerator()
        self.uploader = PodcastUploader()

        os.makedirs(config.AUDIO_OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.CONTENT_DIR, exist_ok=True)

    def generate(self) -> Optional[EpisodeMetadata]:
        """メインフロー: 収集 → 台本 → 音声 → アップロード

        Returns:
            成功時はEpisodeMetadata、失敗時はNone
        """
        logger.info("=== ポッドキャスト生成開始 ===")

        # 1. コンテンツ収集
        logger.info("1. コンテンツ収集中...")
        max_articles = getattr(config, 'MAX_ARTICLES', 5)
        articles = self.content_manager.fetch_rss_feeds(max_articles=max_articles)

        if not articles:
            logger.error("記事が取得できませんでした。生成を中止します。")
            return None

        logger.info("  %d件の記事を取得しました", len(articles))

        # 2. 台本生成
        logger.info("2. 台本生成中...")
        try:
            script = self.script_generator.generate_script(articles)
        except Exception as e:
            logger.warning("台本生成失敗、フォールバック使用: %s", e)
            script = fallback_script(articles, self.host_name, self.guest_name)

        logger.info("  台本: %d行", len(script))

        # 3. 音声生成
        logger.info("3. 音声生成中...")
        episode_num = self._get_episode_number()
        audio_filename = f"episode_{episode_num}_{date.today().strftime('%Y%m%d')}.wav"
        audio_path = os.path.join(config.AUDIO_OUTPUT_DIR, audio_filename)

        try:
            self.tts_generator.generate_audio(script, audio_path)
        except Exception as e:
            logger.error("音声生成失敗: %s", e)
            return None

        # 3.5 WAV → MP3 変換
        mp3_path = audio_path.replace('.wav', '.mp3')
        try:
            mp3_path = self._convert_to_mp3(audio_path, mp3_path)
            # 変換成功時はMP3を最終出力とする
            audio_path = mp3_path
        except Exception as e:
            logger.warning("MP3変換失敗、WAVのまま使用: %s", e)

        # 4. メタデータ構築 & RSS フィード更新
        logger.info("4. メタデータ構築・RSS フィード更新中...")
        metadata = self._build_metadata(articles, audio_path, episode_num)

        # RSS フィード更新（feed.xml にエピソード追加）
        mp3_filename = os.path.basename(audio_path)
        mp3_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else None
        try:
            self.rss_generator.add_episode(
                mp3_filename=mp3_filename,
                title=metadata.title,
                description=metadata.description,
                episode_number=episode_num,
                duration_seconds=metadata.duration_seconds,
                mp3_size=mp3_size,
            )
        except Exception as e:
            logger.error("RSS フィード更新失敗: %s", e)

        # 5. メタデータ JSON 保存
        success = self.uploader.upload(audio_path, metadata)

        if success:
            logger.info("=== ポッドキャスト生成完了 ===")
            logger.info("  エピソード: %s", metadata.title)
            logger.info("  音声ファイル: %s", audio_path)
        else:
            logger.warning("アップロード失敗（音声ファイルはローカルに保存済み）")

        return metadata

    def _get_episode_number(self) -> int:
        """次のエピソード番号を算出する"""
        return self.uploader.get_episode_count() + 1

    def _build_metadata(
        self,
        articles: list,
        audio_path: str,
        episode_num: int,
    ) -> EpisodeMetadata:
        """エピソードメタデータを構築する"""
        today_str = date.today().strftime("%Y-%m-%d")

        title = f"第{episode_num}話 - {config.PODCAST_TITLE} ({today_str})"

        # 出演者名を取得
        host_name, _, guest_name, _ = get_daily_speakers()

        # ソース名をユニーク化（記事タイトルは著作権リスクのため列挙しない）
        sources = sorted(set(a.get("source", "") for a in articles if a.get("source")))
        sources_text = "、".join(sources) if sources else "各種ニュースサイト"

        # 説明文（簡潔に）
        desc_parts = [
            f"配信日: {today_str}",
            f"出演: {host_name} & {guest_name}",
            "",
            f"本日のニュースソース: {sources_text}",
            f"（{len(articles)}件の記事をもとに構成）",
            "",
            "Gemini AIで自動生成されたポッドキャストです。",
            "",
            "📎 参考リンク:",
        ]
        for a in articles:
            link = a.get("link", "")
            source = a.get("source", "")
            if link:
                desc_parts.append(f"・[{source}] {link}" if source else f"・{link}")
        description = "\n".join(desc_parts)

        # 音声の長さ
        duration = self._get_audio_duration(audio_path)

        # ソース記事情報（メタデータ保存用に簡素化）
        source_articles = [
            {"title": a.get("title", ""), "source": a.get("source", ""), "link": a.get("link", "")}
            for a in articles
        ]

        return EpisodeMetadata(
            title=title,
            description=description,
            episode_number=episode_num,
            published_date=today_str,
            source_articles=source_articles,
            duration_seconds=duration,
        )

    def _get_audio_duration(self, audio_path: str) -> int:
        """音声ファイルの再生秒数を取得する（WAV/MP3対応）"""
        try:
            audio = AudioSegment.from_file(audio_path)
            return int(len(audio) / 1000)
        except Exception:
            return 0

    def _convert_to_mp3(
        self, wav_path: str, mp3_path: str, bitrate: str = "128k"
    ) -> str:
        """WAV を MP3 に変換し、元 WAV を削除する

        Args:
            wav_path: 入力WAVファイルパス
            mp3_path: 出力MP3ファイルパス
            bitrate: MP3ビットレート

        Returns:
            出力MP3ファイルパス
        """
        wav_size = os.path.getsize(wav_path)
        logger.info("MP3変換開始: %s (%.1f MB)", wav_path, wav_size / 1024 / 1024)

        audio = AudioSegment.from_wav(wav_path)
        audio.export(mp3_path, format="mp3", bitrate=bitrate)

        mp3_size = os.path.getsize(mp3_path)
        ratio = wav_size / mp3_size if mp3_size else 0
        logger.info(
            "MP3変換完了: %s (%.1f MB, 圧縮率 %.1fx)",
            mp3_path, mp3_size / 1024 / 1024, ratio,
        )

        # 変換成功時は元WAVを削除
        os.remove(wav_path)
        logger.info("元WAVファイルを削除: %s", wav_path)

        return mp3_path


# メイン実行部分
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    generator = PodcastGenerator()
    result = generator.generate()

    if result:
        print(f"\n生成完了: {result.title}")
        exit(0)
    else:
        print("\nポッドキャスト生成に失敗しました")
        exit(1)