"""
深掘りポッドキャスト生成オーケストレーター
コンテンツ収集 → 記事厳選＋深掘り台本生成 → 音声生成 → MP3変換 → RSS更新 → メタデータ保存

既存の速報版（podcast_generator.py）とは独立して動作する。
同じRSSソースから記事を取得するが、別のRSSフィード（feed_deep.xml）に出力する。
"""

import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Optional

from pydub import AudioSegment

import config
from content_manager import ContentManager
from deep_script_generator import DeepScriptGenerator, deep_fallback_script
from script_generator import Script
from tts_generator import TTSGenerator, get_daily_speakers
from rss_feed_generator import RSSFeedGenerator
from podcast_uploader import PodcastUploader, EpisodeMetadata

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


class DeepDivePodcastGenerator:
    """深掘りポッドキャスト生成の全体オーケストレーション"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")

        # 曜日ローテーションで出演者を決定（速報版と同じペア）
        host_name, host_voice, guest_name, guest_voice = get_daily_speakers()
        self.host_name = host_name
        self.guest_name = guest_name
        logger.info(
            "[Deep Dive] 本日の出演者: %s(%s) & %s(%s)",
            host_name, host_voice, guest_name, guest_voice,
        )

        max_topics = getattr(config, 'DEEP_MAX_TOPICS', 3)

        self.content_manager = ContentManager()
        self.script_generator = DeepScriptGenerator(
            api_key=self.api_key,
            host_name=host_name,
            guest_name=guest_name,
            max_topics=max_topics,
        )
        self.tts_generator = TTSGenerator(
            api_key=self.api_key,
            host_name=host_name,
            host_voice=host_voice,
            guest_name=guest_name,
            guest_voice=guest_voice,
        )

        # 深掘り版用のRSSフィードジェネレーター
        self.rss_generator = RSSFeedGenerator(
            feed_filename=getattr(config, 'DEEP_RSS_FEED_FILENAME', 'feed_deep.xml'),
            podcast_title=getattr(config, 'DEEP_PODCAST_TITLE', 'AI Auto Podcast - Deep Dive'),
            podcast_description=getattr(config, 'DEEP_PODCAST_DESCRIPTION', ''),
            podcast_image_url=getattr(config, 'DEEP_PODCAST_IMAGE_URL', ''),
            episodes_subdir=getattr(config, 'DEEP_EPISODES_DIR', 'episodes_deep'),
        )
        self.uploader = PodcastUploader()

        os.makedirs(config.AUDIO_OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.CONTENT_DIR, exist_ok=True)

    def generate(self) -> Optional[EpisodeMetadata]:
        """メインフロー: 収集 → 深掘り台本 → 音声 → RSS更新

        Returns:
            成功時はEpisodeMetadata、失敗時はNone
        """
        logger.info("=== 深掘りポッドキャスト生成開始 ===")

        # 1. コンテンツ収集（速報版と同じソースから全記事取得）
        logger.info("[Deep] 1. コンテンツ収集中...")
        max_articles = getattr(config, 'MAX_ARTICLES', 5)
        articles = self.content_manager.fetch_rss_feeds(max_articles=max_articles)

        if not articles:
            logger.error("[Deep] 記事が取得できませんでした。生成を中止します。")
            return None

        logger.info("[Deep]   %d件の記事を取得（ここからAIが厳選）", len(articles))

        # 2. 深掘り台本生成（AIが記事を厳選＋深い分析台本を生成）
        logger.info("[Deep] 2. 深掘り台本生成中...")
        try:
            script = self.script_generator.generate_script(articles)
        except Exception as e:
            logger.warning("[Deep] 台本生成失敗、フォールバック使用: %s", e)
            script = deep_fallback_script(articles, self.host_name, self.guest_name)

        logger.info("[Deep]   台本: %d行", len(script))

        # 3. 音声生成
        logger.info("[Deep] 3. 音声生成中...")
        episode_num = self._get_episode_number()
        today_jst = datetime.now(JST).date()
        audio_filename = f"deep_{episode_num}_{today_jst.strftime('%Y%m%d')}.wav"
        audio_path = os.path.join(config.AUDIO_OUTPUT_DIR, audio_filename)

        try:
            self.tts_generator.generate_audio(script, audio_path)
        except Exception as e:
            logger.error("[Deep] 音声生成失敗: %s", e)
            return None

        # 3.5 WAV → MP3 変換
        mp3_path = audio_path.replace('.wav', '.mp3')
        try:
            mp3_path = self._convert_to_mp3(audio_path, mp3_path)
            audio_path = mp3_path
        except Exception as e:
            logger.warning("[Deep] MP3変換失敗、WAVのまま使用: %s", e)

        # 4. メタデータ構築 & RSS フィード更新
        logger.info("[Deep] 4. メタデータ構築・RSS フィード更新中...")
        metadata = self._build_metadata(articles, audio_path, episode_num)

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
            logger.error("[Deep] RSS フィード更新失敗: %s", e)

        # 5. メタデータ JSON 保存
        success = self.uploader.upload(audio_path, metadata)

        if success:
            logger.info("=== 深掘りポッドキャスト生成完了 ===")
            logger.info("[Deep]   エピソード: %s", metadata.title)
            logger.info("[Deep]   音声ファイル: %s", audio_path)
        else:
            logger.warning("[Deep] アップロード失敗（音声ファイルはローカルに保存済み）")

        return metadata

    def _get_episode_number(self) -> int:
        """次のエピソード番号を算出する（feed_deep.xml から）"""
        feed_filename = getattr(config, 'DEEP_RSS_FEED_FILENAME', 'feed_deep.xml')
        feed_path = os.path.join(config.AUDIO_OUTPUT_DIR, feed_filename)
        if os.path.exists(feed_path):
            try:
                tree = ET.parse(feed_path)
                channel = tree.find("channel")
                if channel is not None:
                    existing = len(channel.findall("item"))
                    if existing > 0:
                        return existing + 1
            except Exception:
                pass
        return 1

    def _build_metadata(
        self,
        articles: list,
        audio_path: str,
        episode_num: int,
    ) -> EpisodeMetadata:
        """エピソードメタデータを構築する"""
        today_str = datetime.now(JST).date().strftime("%Y-%m-%d")
        deep_title = getattr(config, 'DEEP_PODCAST_TITLE', 'AI Auto Podcast - Deep Dive')
        title = f"第{episode_num}話 - {deep_title} ({today_str})"

        host_name, _, guest_name, _ = get_daily_speakers()

        sources = sorted(set(a.get("source", "") for a in articles if a.get("source")))
        sources_text = "、".join(sources) if sources else "各種ニュースサイト"

        desc_parts = [
            f"配信日: {today_str}",
            f"出演: {host_name} & {guest_name}",
            "",
            f"本日のニュースソース: {sources_text}",
            f"（{len(articles)}件の記事からAIが厳選して深掘り解説）",
            "",
            "Gemini AIで自動生成された深掘り解説ポッドキャストです。",
        ]
        description = "\n".join(desc_parts)

        duration = self._get_audio_duration(audio_path)

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
        """音声ファイルの再生秒数を取得する"""
        try:
            audio = AudioSegment.from_file(audio_path)
            return int(len(audio) / 1000)
        except Exception:
            return 0

    def _convert_to_mp3(
        self, wav_path: str, mp3_path: str, bitrate: str = "128k"
    ) -> str:
        """WAV を MP3 に変換し、元 WAV を削除する"""
        wav_size = os.path.getsize(wav_path)
        logger.info("[Deep] MP3変換開始: %s (%.1f MB)", wav_path, wav_size / 1024 / 1024)

        audio = AudioSegment.from_wav(wav_path)
        audio.export(mp3_path, format="mp3", bitrate=bitrate)

        mp3_size = os.path.getsize(mp3_path)
        ratio = wav_size / mp3_size if mp3_size else 0
        logger.info(
            "[Deep] MP3変換完了: %s (%.1f MB, 圧縮率 %.1fx)",
            mp3_path, mp3_size / 1024 / 1024, ratio,
        )

        os.remove(wav_path)
        logger.info("[Deep] 元WAVファイルを削除: %s", wav_path)

        return mp3_path


# メイン実行部分
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    generator = DeepDivePodcastGenerator()
    result = generator.generate()

    if result:
        print(f"\n[Deep Dive] 生成完了: {result.title}")
        exit(0)
    else:
        print("\n[Deep Dive] ポッドキャスト生成に失敗しました")
        exit(1)
