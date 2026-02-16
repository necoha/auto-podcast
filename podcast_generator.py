"""
ポッドキャスト生成オーケストレーター
コンテンツ収集 → 台本生成 → 音声生成 → アップロードの統合制御
"""

import logging
import os
import wave
from datetime import date, datetime
from typing import Optional

import config
from content_manager import ContentManager
from script_generator import ScriptGenerator, Script, fallback_script
from tts_generator import TTSGenerator
from podcast_uploader import PodcastUploader, EpisodeMetadata

logger = logging.getLogger(__name__)


class PodcastGenerator:
    """ポッドキャスト生成の全体オーケストレーション"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")

        self.content_manager = ContentManager()
        self.script_generator = ScriptGenerator(api_key=self.api_key)
        self.tts_generator = TTSGenerator(api_key=self.api_key)
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
            script = fallback_script(articles)

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

        # 4. メタデータ構築 & アップロード
        logger.info("4. メタデータ保存・アップロード中...")
        metadata = self._build_metadata(articles, audio_path, episode_num)
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

        # 記事タイトルからエピソードタイトルを生成
        top_titles = [a.get("title", "") for a in articles[:3]]
        title = f"第{episode_num}話 - {config.PODCAST_TITLE} ({today_str})"

        # 説明文
        desc_parts = [f"配信日: {today_str}", ""]
        desc_parts.append("取り上げた記事:")
        for i, a in enumerate(articles, 1):
            desc_parts.append(f"  {i}. {a.get('title', '不明')} ({a.get('source', '')})")
        desc_parts.append("")
        desc_parts.append("Gemini AIで自動生成されたポッドキャストです。")
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
        """WAVファイルの再生秒数を取得する"""
        try:
            with wave.open(audio_path, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return int(frames / rate)
        except Exception:
            return 0


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