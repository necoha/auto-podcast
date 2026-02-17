"""
RSS フィード生成モジュール
Apple Podcasts / Spotify 互換の RSS 2.0 + iTunes 拡張 XML を生成・更新する
"""

import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from typing import Optional

import config

logger = logging.getLogger(__name__)

# iTunes 名前空間
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM_NS = "http://www.w3.org/2005/Atom"

# 名前空間登録（出力時に ns0: のようなプレフィックスを避ける）
ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("atom", ATOM_NS)

JST = timezone(timedelta(hours=9))


class RSSFeedGenerator:
    """ポッドキャスト配信用 RSS 2.0 フィードを生成・更新する

    - 既存 feed.xml があれば読み込んで新エピソードを先頭に追加
    - なければ新規作成
    - Apple Podcasts / Spotify 互換の iTunes 拡張タグを含む
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        feed_dir: Optional[str] = None,
    ):
        self.base_url = (base_url or config.PODCAST_BASE_URL).rstrip("/")
        self.feed_dir = feed_dir or config.AUDIO_OUTPUT_DIR
        self.feed_path = os.path.join(
            self.feed_dir, getattr(config, "RSS_FEED_FILENAME", "feed.xml")
        )
        self.episodes_subdir = getattr(config, "EPISODES_DIR", "episodes")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_episode(
        self,
        mp3_filename: str,
        title: str,
        description: str,
        episode_number: int,
        duration_seconds: int,
        pub_date: Optional[datetime] = None,
        mp3_size: Optional[int] = None,
    ) -> str:
        """既存フィードにエピソードを追加して保存する

        Args:
            mp3_filename: MP3 ファイル名（例: episode_1_20260217.mp3）
            title: エピソードタイトル
            description: エピソード説明文
            episode_number: エピソード番号
            duration_seconds: 再生秒数
            pub_date: 配信日時（None なら現在時刻 JST）
            mp3_size: MP3 ファイルサイズ (bytes)。None の場合はローカルから取得を試みる。

        Returns:
            保存先 feed.xml のパス
        """
        tree = self._load_existing_feed()
        if tree is None:
            tree = self._create_empty_feed()

        channel = tree.find("channel")
        if channel is None:
            raise RuntimeError("RSS channel 要素が見つかりません")

        # <item> を構築
        item = self._create_item_element(
            mp3_filename=mp3_filename,
            title=title,
            description=description,
            episode_number=episode_number,
            duration_seconds=duration_seconds,
            pub_date=pub_date,
            mp3_size=mp3_size,
        )

        # channel の先頭（既存 item より前）に挿入
        # lastBuildDate の直後に追加
        insert_idx = 0
        for i, child in enumerate(channel):
            if child.tag == "item":
                insert_idx = i
                break
        else:
            insert_idx = len(channel)

        channel.insert(insert_idx, item)

        # lastBuildDate を更新
        last_build = channel.find("lastBuildDate")
        now_str = self._format_rfc2822(datetime.now(JST))
        if last_build is not None:
            last_build.text = now_str
        else:
            lb = ET.SubElement(channel, "lastBuildDate")
            lb.text = now_str

        # 保存
        os.makedirs(os.path.dirname(self.feed_path) or ".", exist_ok=True)
        tree.write(self.feed_path, encoding="unicode", xml_declaration=True)

        logger.info("RSS フィード更新: %s (エピソード #%d)", self.feed_path, episode_number)
        return self.feed_path

    def generate_feed(self) -> str:
        """空のフィード（チャンネル情報のみ）を新規作成して保存する

        Returns:
            保存先 feed.xml のパス
        """
        tree = self._create_empty_feed()
        os.makedirs(os.path.dirname(self.feed_path) or ".", exist_ok=True)
        tree.write(self.feed_path, encoding="unicode", xml_declaration=True)
        logger.info("RSS フィード新規作成: %s", self.feed_path)
        return self.feed_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_existing_feed(self) -> Optional[ET.ElementTree]:
        """既存 feed.xml をパースして返す。なければ None。"""
        if not os.path.exists(self.feed_path):
            return None
        try:
            tree = ET.parse(self.feed_path)
            return tree
        except ET.ParseError as e:
            logger.warning("既存 feed.xml のパースに失敗: %s — 新規作成します", e)
            return None

    def _create_empty_feed(self) -> ET.ElementTree:
        """チャンネル情報のみの空フィードを構築する"""
        rss = ET.Element("rss")
        rss.set("version", "2.0")

        channel = ET.SubElement(rss, "channel")

        # 基本情報
        ET.SubElement(channel, "title").text = config.PODCAST_TITLE
        ET.SubElement(channel, "link").text = self.base_url
        ET.SubElement(channel, "description").text = getattr(
            config, "PODCAST_DESCRIPTION", config.PODCAST_TITLE
        )
        ET.SubElement(channel, "language").text = getattr(config, "PODCAST_LANGUAGE", "ja")
        ET.SubElement(channel, "lastBuildDate").text = self._format_rfc2822(
            datetime.now(JST)
        )

        # Atom self link（Spotify / Apple 推奨）
        feed_url = f"{self.base_url}/{getattr(config, 'RSS_FEED_FILENAME', 'feed.xml')}"
        atom_link = ET.SubElement(channel, f"{{{ATOM_NS}}}link")
        atom_link.set("href", feed_url)
        atom_link.set("rel", "self")
        atom_link.set("type", "application/rss+xml")

        # iTunes 拡張
        ET.SubElement(
            channel, f"{{{ITUNES_NS}}}author"
        ).text = getattr(config, "PODCAST_AUTHOR", "Auto Podcast Generator")
        ET.SubElement(
            channel, f"{{{ITUNES_NS}}}summary"
        ).text = getattr(config, "PODCAST_DESCRIPTION", config.PODCAST_TITLE)
        cat = ET.SubElement(channel, f"{{{ITUNES_NS}}}category")
        cat.set("text", "Technology")
        ET.SubElement(
            channel, f"{{{ITUNES_NS}}}explicit"
        ).text = "false"

        return ET.ElementTree(rss)

    def _create_item_element(
        self,
        mp3_filename: str,
        title: str,
        description: str,
        episode_number: int,
        duration_seconds: int,
        pub_date: Optional[datetime] = None,
        mp3_size: Optional[int] = None,
    ) -> ET.Element:
        """RSS <item> 要素を構築する"""
        item = ET.Element("item")

        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "description").text = description

        # enclosure（MP3 URL）
        mp3_url = f"{self.base_url}/{self.episodes_subdir}/{mp3_filename}"
        file_size = mp3_size or self._get_file_size(mp3_filename)
        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", mp3_url)
        enclosure.set("length", str(file_size))
        enclosure.set("type", "audio/mpeg")

        # guid（一意識別子）
        date_str = (pub_date or datetime.now(JST)).strftime("%Y%m%d")
        guid = ET.SubElement(item, "guid")
        guid.set("isPermaLink", "false")
        guid.text = f"episode-{episode_number}-{date_str}"

        # pubDate
        dt = pub_date or datetime.now(JST)
        ET.SubElement(item, "pubDate").text = self._format_rfc2822(dt)

        # iTunes 拡張
        ET.SubElement(
            item, f"{{{ITUNES_NS}}}episode"
        ).text = str(episode_number)
        ET.SubElement(
            item, f"{{{ITUNES_NS}}}duration"
        ).text = str(duration_seconds)
        ET.SubElement(
            item, f"{{{ITUNES_NS}}}explicit"
        ).text = "false"

        return item

    def _get_file_size(self, mp3_filename: str) -> int:
        """ローカルの MP3 ファイルサイズを取得する（バイト数）"""
        # audio_files/ 配下を探す
        local_path = os.path.join(config.AUDIO_OUTPUT_DIR, mp3_filename)
        if os.path.exists(local_path):
            return os.path.getsize(local_path)
        logger.warning("MP3 ファイルが見つかりません（サイズ=0）: %s", local_path)
        return 0

    @staticmethod
    def _format_rfc2822(dt: datetime) -> str:
        """datetime を RFC 2822 形式にフォーマットする（RSS 互換）

        例: Mon, 17 Feb 2026 00:00:00 +0900
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return format_datetime(dt)


# ------------------------------------------------------------------
# スタンドアロン実行
# ------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    gen = RSSFeedGenerator()

    # テスト: 空フィード作成 → エピソード追加
    gen.generate_feed()
    gen.add_episode(
        mp3_filename="episode_1_20260217.mp3",
        title="第1話 - AI Auto Podcast (2026-02-17)",
        description="テストエピソードです。",
        episode_number=1,
        duration_seconds=600,
        mp3_size=3_000_000,
    )
    print(f"feed.xml を生成しました: {gen.feed_path}")
