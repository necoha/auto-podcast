"""
デプロイ前フィード検証スクリプト

GitHub Actions の CI ステップで実行し、feed.xml / feed_deep.xml の
チャンネルメタデータ・エピソード構造が config.py の期待値と一致するか検証する。
不一致があれば exit(1) でワークフローを失敗させる。
"""

import sys
import os
import xml.etree.ElementTree as ET

# プロジェクト直下の config をインポート
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


def validate_feed(feed_path: str, expected: dict) -> list[str]:
    """フィードXMLを検証し、エラーメッセージのリストを返す。空なら合格。"""
    errors: list[str] = []
    label = expected.get("label", feed_path)

    # --- ファイル存在チェック ---
    if not os.path.exists(feed_path):
        errors.append(f"[{label}] ファイルが存在しません: {feed_path}")
        return errors

    # --- XMLパース ---
    try:
        tree = ET.parse(feed_path)
    except ET.ParseError as e:
        errors.append(f"[{label}] XMLパースエラー: {e}")
        return errors

    channel = tree.find("channel")
    if channel is None:
        errors.append(f"[{label}] <channel> 要素が見つかりません")
        return errors

    # --- チャンネルタイトル ---
    title_el = channel.find("title")
    actual_title = title_el.text if title_el is not None else "(なし)"
    if actual_title != expected["title"]:
        errors.append(
            f"[{label}] チャンネルタイトル不一致: "
            f"期待={expected['title']!r}, 実際={actual_title!r}"
        )

    # --- チャンネル説明 ---
    desc_el = channel.find("description")
    actual_desc = desc_el.text if desc_el is not None else "(なし)"
    if actual_desc != expected["description"]:
        errors.append(
            f"[{label}] チャンネル説明不一致: "
            f"期待={expected['description']!r}, 実際={actual_desc!r}"
        )

    # --- itunes:summary ---
    summary_el = channel.find(f"{{{ITUNES_NS}}}summary")
    actual_summary = summary_el.text if summary_el is not None else "(なし)"
    if actual_summary != expected["description"]:
        errors.append(
            f"[{label}] itunes:summary不一致: "
            f"期待={expected['description']!r}, 実際={actual_summary!r}"
        )

    # --- itunes:image ---
    img_el = channel.find(f"{{{ITUNES_NS}}}image")
    if img_el is not None:
        actual_img = img_el.get("href", "(なし)")
    else:
        actual_img = "(なし)"
    if actual_img != expected["image_url"]:
        errors.append(
            f"[{label}] itunes:image不一致: "
            f"期待={expected['image_url']!r}, 実際={actual_img!r}"
        )

    # --- エピソードが1件以上あること ---
    items = channel.findall("item")
    if len(items) == 0:
        errors.append(f"[{label}] エピソードが0件です")

    # --- 各エピソードの enclosure URL に正しい episodes_subdir が含まれること ---
    episodes_subdir = expected["episodes_subdir"]
    for item in items:
        enc = item.find("enclosure")
        if enc is None:
            item_title = item.findtext("title", "(不明)")
            errors.append(f"[{label}] <enclosure> がありません: {item_title}")
            continue
        url = enc.get("url", "")
        if f"/{episodes_subdir}/" not in url:
            item_title = item.findtext("title", "(不明)")
            errors.append(
                f"[{label}] enclosure URLにサブディレクトリ {episodes_subdir!r} が含まれていません: "
                f"{url} ({item_title})"
            )

    # --- エピソードタイトルにチャンネルタイトルまたは期待ラベルが含まれること ---
    # (古いエピソードは旧タイトルのままの場合があるので警告のみ)

    return errors


def main():
    """速報版・深掘り版の両フィードを検証する。"""
    # 引数でデプロイディレクトリを指定可能（デフォルト: audio_files）
    deploy_dir = sys.argv[1] if len(sys.argv) > 1 else "audio_files"

    feeds_to_check = [
        {
            "path": os.path.join(deploy_dir, getattr(config, "RSS_FEED_FILENAME", "feed.xml")),
            "expected": {
                "label": "速報版 feed.xml",
                "title": config.PODCAST_TITLE,
                "description": config.PODCAST_DESCRIPTION,
                "image_url": getattr(config, "PODCAST_IMAGE_URL", ""),
                "episodes_subdir": getattr(config, "EPISODES_DIR", "episodes"),
            },
        },
        {
            "path": os.path.join(deploy_dir, getattr(config, "DEEP_RSS_FEED_FILENAME", "feed_deep.xml")),
            "expected": {
                "label": "深掘り版 feed_deep.xml",
                "title": getattr(config, "DEEP_PODCAST_TITLE", ""),
                "description": getattr(config, "DEEP_PODCAST_DESCRIPTION", ""),
                "image_url": getattr(config, "DEEP_PODCAST_IMAGE_URL", ""),
                "episodes_subdir": getattr(config, "DEEP_EPISODES_DIR", "episodes_deep"),
            },
        },
    ]

    all_errors: list[str] = []

    for feed_info in feeds_to_check:
        path = feed_info["path"]
        expected = feed_info["expected"]

        if not os.path.exists(path):
            print(f"⏭️  {expected['label']}: ファイルなし（スキップ）")
            continue

        errors = validate_feed(path, expected)
        if errors:
            all_errors.extend(errors)
            print(f"❌ {expected['label']}: {len(errors)}件のエラー")
            for e in errors:
                print(f"   {e}")
        else:
            print(f"✅ {expected['label']}: 検証OK")

    if all_errors:
        print(f"\n🚨 検証失敗: 合計{len(all_errors)}件のエラー")
        sys.exit(1)
    else:
        print("\n✅ 全フィード検証OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
