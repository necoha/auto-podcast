"""
ポッドキャストアップロードモジュール
メタデータJSON保存を担当。GitHub Actions が gh-pages へのデプロイを実行する。
"""

import json
import logging
import os
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import config

JST = timezone(timedelta(hours=9))

logger = logging.getLogger(__name__)


@dataclass
class EpisodeMetadata:
    """エピソードのメタデータ"""
    title: str
    description: str
    episode_number: int
    published_date: str
    source_articles: List[dict]
    duration_seconds: int = 0


class PodcastUploader:
    """ポッドキャスト音声のメタデータ保存管理

    メタデータ JSON を content/ に保存する。
    MP3 + feed.xml の配信は GitHub Actions が gh-pages ブランチへ push して行う。
    """

    def __init__(self):
        self.output_dir = config.AUDIO_OUTPUT_DIR
        self.content_dir = config.CONTENT_DIR
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.content_dir, exist_ok=True)

    def upload(self, audio_path: str, metadata: EpisodeMetadata) -> bool:
        """音声ファイルをアップロード（または保存）する

        Args:
            audio_path: 音声ファイルのパス
            metadata: エピソードメタデータ

        Returns:
            成功した場合True
        """
        if not os.path.exists(audio_path):
            logger.error("音声ファイルが見つかりません: %s", audio_path)
            return False

        # 現時点ではローカル保存方式
        return self._save_for_manual_upload(audio_path, metadata)

    def _save_for_manual_upload(self, audio_path: str, metadata: EpisodeMetadata) -> bool:
        """ローカル保存 + メタデータJSON出力（手動アップロード用）"""
        try:
            # メタデータをJSON保存
            ep_num = metadata.episode_number
            date_str = datetime.now(JST).strftime("%Y%m%d")
            metadata_filename = f"episode_{ep_num}_{date_str}.json"
            metadata_path = os.path.join(self.content_dir, metadata_filename)

            meta_dict = asdict(metadata)
            meta_dict["audio_file"] = os.path.basename(audio_path)
            meta_dict["generated_at"] = datetime.now(JST).isoformat()

            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(meta_dict, f, ensure_ascii=False, indent=2)

            logger.info("メタデータ保存完了: %s", metadata_path)
            logger.info(
                "音声ファイル: %s (GitHub Actions が gh-pages に自動デプロイします)",
                audio_path
            )
            return True

        except Exception as e:
            logger.error("メタデータ保存エラー: %s", e)
            return False

    def get_episode_count(self) -> int:
        """保存済みエピソード数を返す"""
        if not os.path.exists(self.content_dir):
            return 0
        return len([
            f for f in os.listdir(self.content_dir)
            if f.startswith("episode_") and f.endswith(".json")
        ])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # テスト
    meta = EpisodeMetadata(
        title="テストエピソード",
        description="これはテストです",
        episode_number=1,
        published_date=datetime.now().strftime("%Y-%m-%d"),
        source_articles=[{"title": "テスト記事", "source": "テスト"}],
        duration_seconds=600,
    )

    uploader = PodcastUploader()
    # ダミーファイルでテスト
    test_path = os.path.join(config.AUDIO_OUTPUT_DIR, "test.wav")
    if os.path.exists(test_path):
        result = uploader.upload(test_path, meta)
        print(f"アップロード結果: {result}")
    else:
        print(f"テスト用音声ファイルが必要です: {test_path}")
