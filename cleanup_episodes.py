"""古いエピソードを自動削除するスクリプト（GitHub Actions から呼び出し用）"""
import sys
from rss_feed_generator import RSSFeedGenerator
import config


def main():
    feed_path = sys.argv[1] if len(sys.argv) > 1 else "gh-pages-deploy/feed.xml"
    episodes_dir = sys.argv[2] if len(sys.argv) > 2 else "gh-pages-deploy/episodes"
    retention_days = config.EPISODE_RETENTION_DAYS

    gen = RSSFeedGenerator()
    removed = gen.cleanup_old_episodes(
        feed_path=feed_path,
        episodes_dir=episodes_dir,
        retention_days=retention_days,
    )
    if removed:
        print(f"Cleaned up {len(removed)} old episodes: {', '.join(removed)}")
    else:
        print("No old episodes to clean up")


if __name__ == "__main__":
    main()
