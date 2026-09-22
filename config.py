import os
from dotenv import load_dotenv

load_dotenv()

# Gemini API設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# TTS設定
TTS_MODEL = os.getenv("TTS_MODEL", "gemini-3.1-flash-tts-preview")
TTS_VOICE = "Kore"    # デフォルト音声（フォールバック用）
TTS_MAX_REQUESTS_PER_PODCAST = int(
    os.getenv("TTS_MAX_REQUESTS_PER_PODCAST", "5")
)

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
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.8-flash")
LLM_MAX_ATTEMPTS = 3
LLM_RETRY_BASE_DELAY_SECONDS = 30
GEMINI_LLM_TIMEOUT_MS = 180_000
GEMINI_TTS_TIMEOUT_MS = 300_000
GEMINI_SDK_MAX_ATTEMPTS = 1
GEMINI_INTERACTIONS_MAX_RETRIES = 0

# コンテンツソース設定
# 追加・変更前に docs/CRD.md「4.1.1 RSSニュースソース採用・除外基準」を確認する。
# 承認済みソースのallowlist。CUSTOM_RSS_FEEDSにも同じ基準を適用する。
RSS_FEEDS = [
    # テクノロジー（日本語）
    "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",  # ITmedia NEWS
    "https://www.publickey1.jp/atom.xml",  # Publickey
    "https://gigazine.net/news/rss_2.0/",  # GIGAZINE
    "https://japan.cnet.com/rss/index.rdf",  # CNET Japan
    "https://www.watch.impress.co.jp/data/rss/1.0/ipw/feed.rdf",  # Impress Watch
    "https://ascii.jp/rss.xml",  # ASCII.jp

    # テクノロジー（海外・英語）
    "https://techcrunch.com/feed/",  # TechCrunch（スタートアップ・AI・VC）
    "https://feeds.arstechnica.com/arstechnica/index",  # Ars Technica
    "https://hnrss.org/frontpage?count=10",  # Hacker News

    # 経済・ビジネス（日本語）
    "https://business.nikkei.com/rss/sns/nb.rdf",  # 日経ビジネス
    "https://assets.wor.jp/rss/rdf/reuters/top.rdf",  # ロイター（日本語）
    "https://news.yahoo.co.jp/rss/topics/business.xml",  # Yahoo経済
    "https://www.asahi.com/rss/asahi/business.rdf",  # 朝日新聞経済
]

# 環境変数からカスタムRSSフィードを追加
custom_rss_feeds = os.getenv("CUSTOM_RSS_FEEDS")
if custom_rss_feeds:
    RSS_FEEDS.extend(custom_rss_feeds.split(","))

# ファイル管理設定
AUDIO_OUTPUT_DIR = "./audio_files"
CONTENT_DIR = "./content"

# Podcast設定
PODCAST_TITLE = "テック速報 AI ニュースラジオ"
PODCAST_DESCRIPTION = "AIが届ける毎朝のテック＆経済ニュースダイジェスト。元記事の著作権は各メディアに帰属します。"
PODCAST_AUTHOR = "Auto Podcast Generator"
PODCAST_LANGUAGE = "ja"

# コンテンツ制限
MAX_CONTENT_LENGTH = 10000  # 文字数制限
MAX_ARTICLES = 2  # 1フィードから取得する記事数上限
MAX_TOTAL_ARTICLES = 20  # URL Contextへ渡す記事数上限

# GitHub Pages 配信設定
PODCAST_BASE_URL = "https://necoha.github.io/auto-podcast"
RSS_FEED_FILENAME = "feed.xml"
EPISODES_DIR = "episodes"  # gh-pages ブランチ上の MP3 格納ディレクトリ
EPISODE_RETENTION_DAYS = 60  # gh-pages 上に保持するエピソード日数（60日超の古いMP3を自動削除）
PODCAST_IMAGE_URL = "https://necoha.github.io/auto-podcast/cover.jpg?v=2"
PODCAST_OWNER_EMAIL = os.getenv("PODCAST_OWNER_EMAIL", "")

# ===== Deep Dive Podcast 設定 =====
DEEP_PODCAST_TITLE = "テック深掘り AI 解説ラジオ"
DEEP_PODCAST_DESCRIPTION = "最新ニュースの背景・影響・技術解説・今後の展望までAIが深掘り解説。元記事の著作権は各メディアに帰属します。"
DEEP_RSS_FEED_FILENAME = "feed_deep.xml"
DEEP_EPISODES_DIR = "episodes_deep"
DEEP_PODCAST_IMAGE_URL = "https://necoha.github.io/auto-podcast/cover_deep.jpg"
DEEP_MAX_TOPICS = 3  # 深掘りするトピック数