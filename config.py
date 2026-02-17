import os
from dotenv import load_dotenv

load_dotenv()

# Gemini API設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# TTS設定
TTS_MODEL = "gemini-2.5-flash-preview-tts"
TTS_VOICE = "Kore"    # デフォルト音声（フォールバック用）

# 曜日ローテーション（7ペア × ホスト＋ゲスト = 14人）
# 各タプル: (ホスト名, ホスト音声, ゲスト名, ゲスト音声)
DAILY_SPEAKERS = {
    0: ("アオイ",   "Kore",       "タクミ",   "Charon"),      # 月曜
    1: ("ヒナタ",   "Aoede",      "ソウタ",   "Puck"),        # 火曜
    2: ("ミオ",     "Leda",       "ハルト",   "Fenrir"),      # 水曜
    3: ("サクラ",   "Erinome",    "レン",     "Orus"),        # 木曜
    4: ("リコ",     "Laomedeia",  "カイト",   "Iapetus"),     # 金曜
    5: ("シオリ",   "Despina",    "ユウマ",   "Enceladus"),   # 土曜
    6: ("ナツキ",   "Autonoe",    "リュウセイ", "Algenib"),   # 日曜
}

# 後方互換のためデフォルト値も維持
TTS_VOICE_A = "Kore"
TTS_VOICE_B = "Charon"

# LLM設定（台本生成）
LLM_MODEL = "gemini-2.5-flash"

# コンテンツソース設定
RSS_FEEDS = [
    # テクノロジー（日本語）
    "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",  # ITmedia NEWS
    "https://www.publickey1.jp/atom.xml",  # Publickey（クラウド・開発）
    "https://gigazine.net/news/rss_2.0/",  # GIGAZINE
    "https://japan.cnet.com/rss/index.rdf",  # CNET Japan
    "https://www.watch.impress.co.jp/data/rss/1.0/ipw/feed.rdf",  # Impress Watch
    "https://gihyo.jp/feed/rss2",  # gihyo.jp（技術評論社）
    "https://ascii.jp/rss.xml",  # ASCII.jp

    # 経済・ビジネス（日本語）
    "https://business.nikkei.com/rss/sns/nb.rdf",  # 日経ビジネス
    "https://www3.nhk.or.jp/rss/news/cat5.xml",  # NHK 経済・ビジネス
    "https://assets.wor.jp/rss/rdf/reuters/top.rdf",  # ロイター日本語
    "https://news.yahoo.co.jp/rss/topics/business.xml",  # Yahoo経済
    "https://www.asahi.com/rss/asahi/business.rdf",  # 朝日新聞経済
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

# GitHub Pages 配信設定
PODCAST_BASE_URL = "https://necoha.github.io/auto-podcast"
RSS_FEED_FILENAME = "feed.xml"
EPISODES_DIR = "episodes"  # gh-pages ブランチ上の MP3 格納ディレクトリ
EPISODE_RETENTION_DAYS = 60  # gh-pages 上に保持するエピソード日数（60日超の古いMP3を自動削除）
PODCAST_IMAGE_URL = "https://necoha.github.io/auto-podcast/cover.jpg"
PODCAST_OWNER_EMAIL = "cloha.mikage@gmail.com"