import os
from dotenv import load_dotenv

load_dotenv()

# Gemini API設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# TTS設定
TTS_MODEL = "gemini-2.5-flash-preview-tts"
TTS_VOICE = "Kore"    # デフォルト音声
TTS_VOICE_A = "Kore"  # 話者A（ホスト）
TTS_VOICE_B = "Charon"  # 話者B（ゲスト）

# LLM設定（台本生成）
LLM_MODEL = "gemini-2.5-flash"

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
]

# 環境変数からカスタムRSSフィードを追加
if os.getenv("CUSTOM_RSS_FEEDS"):
    RSS_FEEDS.extend(os.getenv("CUSTOM_RSS_FEEDS").split(","))

# ファイル管理設定
AUDIO_OUTPUT_DIR = "./audio_files"
CONTENT_DIR = "./content"

# Podcast設定
PODCAST_TITLE = "AI Auto Podcast"
PODCAST_DESCRIPTION = "Gemini AIで自動生成するテクノロジーポッドキャスト"
PODCAST_AUTHOR = "Auto Podcast Generator"
PODCAST_LANGUAGE = "ja"

# コンテンツ制限
MAX_CONTENT_LENGTH = 10000  # 文字数制限
MAX_ARTICLES = 5  # 1エピソードに含む記事数上限