import os
from dotenv import load_dotenv

load_dotenv()

# NotebookLM関連設定 (OAuth対応)
NOTEBOOKLM_URL = "https://notebooklm.google.com"

# OAuth認証設定
GOOGLE_OAUTH_CREDENTIALS = os.getenv("GOOGLE_OAUTH_CREDENTIALS")
OAUTH_SESSION_DATA = os.getenv("OAUTH_SESSION_DATA")

# Legacy: アプリパスワード方式（非推奨）
GOOGLE_ACCOUNT_EMAIL = os.getenv("GOOGLE_ACCOUNT_EMAIL")
GOOGLE_ACCOUNT_PASSWORD = os.getenv("GOOGLE_ACCOUNT_PASSWORD")

# コンテンツソース設定
RSS_FEEDS = [
    # 日本語ニュース
    "https://www3.nhk.or.jp/rss/news/cat0.xml",  # NHKニュース
    "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",  # ITmedia
    
    # 英語テクノロジーニュース
    "https://feeds.feedburner.com/TechCrunch",  # TechCrunch
    "https://feeds.arstechnica.com/arstechnica/index",  # Ars Technica
    
    # GitHub・開発関連
    "https://github.blog/feed/",  # GitHub Blog
    
    # カスタムRSSフィード（必要に応じて追加）
    # os.getenv("CUSTOM_RSS_FEEDS", "").split(",") if os.getenv("CUSTOM_RSS_FEEDS") else []
]

# 環境変数からカスタムRSSフィードを追加
if os.getenv("CUSTOM_RSS_FEEDS"):
    RSS_FEEDS.extend(os.getenv("CUSTOM_RSS_FEEDS").split(","))

# ファイル管理設定
AUDIO_OUTPUT_DIR = "./audio_files"
CONTENT_DIR = "./content"
RSS_OUTPUT_FILE = "./podcast_feed.xml"

# Podcast設定
PODCAST_TITLE = "AI Auto Podcast"
PODCAST_DESCRIPTION = "Notebook LMのAudio Overview機能を使った自動生成ポッドキャスト"
PODCAST_AUTHOR = "Auto Podcast Generator"
PODCAST_LANGUAGE = "ja"
PODCAST_BASE_URL = os.getenv("PODCAST_BASE_URL", "https://your-domain.com")

# 生成間隔設定
GENERATION_SCHEDULE = "daily"  # daily, weekly, hourly

# 無料サービス制限
MAX_DAILY_GENERATIONS = 3  # NotebookLM無料版の制限
MAX_CONTENT_LENGTH = 10000  # 文字数制限