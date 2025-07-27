import os
from dotenv import load_dotenv

load_dotenv()

# NotebookLM関連設定
NOTEBOOKLM_URL = "https://notebooklm.google.com"
GOOGLE_ACCOUNT_EMAIL = os.getenv("GOOGLE_ACCOUNT_EMAIL")
GOOGLE_ACCOUNT_PASSWORD = os.getenv("GOOGLE_ACCOUNT_PASSWORD")

# コンテンツソース設定
RSS_FEEDS = [
    "https://rss.cnn.com/rss/edition.rss",
    "https://feeds.feedburner.com/TechCrunch",
    # 他のRSSフィードを追加
]

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