# HLD - High-Level Design
## AI Auto Podcast アーキテクチャ設計書

**採用プラン: α（完全無料 × 高品質）**

---

## 1. システムアーキテクチャ概要

```mermaid
flowchart TD
    subgraph CI["GitHub Actions"]
        Cron["⏰ cron: 毎日 06:00 JST<br/>(21:00 UTC)"]
        Runner["🖥️ ubuntu-latest"]
    end

    subgraph App["PodcastGenerator"]
        ROT["0. 曜日ローテーション<br/>14人日替わり（7ペア）"]
        CM["1. ContentManager<br/>収集 + 日付フィルタ + 重複排除"]
        SG["2. ScriptGenerator<br/>台本生成 + 発音補正"]
        TTS["3. TTSGenerator<br/>Multi-Speaker TTS"]
        MP3["3.5 MP3変換<br/>pydub + ffmpeg"]
        RGEN["4. RSSFeedGenerator<br/>feed.xml 更新"]
        UP["5. PodcastUploader<br/>メタデータ保存"]
    end

    subgraph External["外部サービス"]
        RSS[("RSS Feeds<br/>テクノロジー6 + 経済4")]
        GeminiLLM["Gemini 2.5 Flash<br/>台本生成 API"]
        GeminiTTS["Gemini Flash TTS<br/>Multi-Speaker 音声生成"]
        GHP["GitHub Pages<br/>MP3 + RSS ホスティング"]
        Spotify["Spotify / Apple Podcasts<br/>RSS 自動取得"]
    end

    Cron --> Runner
    Runner --> ROT --> CM
    CM --> SG --> TTS --> MP3 --> RGEN --> UP

    CM -.-> RSS
    SG -.-> GeminiLLM
    TTS -.-> GeminiTTS
    UP -.-> GHP
    GHP -.-> Spotify
```

---

## 2. コンポーネント構成

### 2.1 コンポーネント一覧

| コンポーネント | モジュール | 責務 |
|---------------|-----------|------|
| **PodcastGenerator** | `podcast_generator.py` | オーケストレーター。収集→台本→音声→RSS→配信の統合制御 |
| **ContentManager** | `content_manager.py` | RSSフィードからのコンテンツ収集・テキスト処理 |
| **ScriptGenerator** | `script_generator.py` | Gemini Flash APIでポッドキャスト対話台本を生成 |
| **TTSGenerator** | `tts_generator.py` | Gemini Flash TTS APIで台本から音声ファイルを生成 |
| **RSSFeedGenerator** | `rss_feed_generator.py` | ポッドキャスト配信用 RSS XML を生成・更新 |
| **PodcastUploader** | `podcast_uploader.py` | メタデータ保存 + gh-pages へのデプロイ |
| **Config** | `config.py` | 全体設定管理（環境変数・定数・曜日ローテーション） |

### 2.2 コンポーネント関係図

```mermaid
graph TD
    PG["PodcastGenerator<br/><i>podcast_generator.py</i>"]
    CM["ContentManager<br/><i>content_manager.py</i>"]
    SG["ScriptGenerator<br/><i>script_generator.py</i>"]
    TTS["TTSGenerator<br/><i>tts_generator.py</i>"]
    RGEN["RSSFeedGenerator<br/><i>rss_feed_generator.py</i>"]
    UP["PodcastUploader<br/><i>podcast_uploader.py</i>"]
    CFG["Config<br/><i>config.py</i>"]

    PG --> CM
    PG --> SG
    PG --> TTS
    PG --> RGEN
    PG --> UP

    CM -.->|参照| CFG
    SG -.->|参照| CFG
    TTS -.->|参照| CFG
    RGEN -.->|参照| CFG
    UP -.->|参照| CFG
    PG -.->|参照| CFG
```

### 2.3 旧アーキテクチャとの差分

| 項目 | 旧（Notebook LM） | 新（プランα） |
|------|-------------------|--------------|
| 音声生成 | Selenium + Notebook LM | Gemini Flash TTS API |
| 台本生成 | Notebook LM 内部 | Gemini Flash API（明示的） |
| 話者 | 匿名2人固定 | 14人日替わりローテーション（7ペア） |
| 認証 | OAuth + Cookie + セッション管理 | APIキー1つ |
| ブラウザ | Chrome/Firefox/Chromium/Edge | 不要 |
| コード量 | ~4,500行（6ファイル） | ~300行（3ファイル新規） |
| CI動作 | モック音声のみ | 実音声生成可能 |
| 配信 | 手動アップロード | GitHub Pages + RSS → Spotify/Apple自動取得 |

---

## 3. データフロー

### 3.1 メインフロー（日次生成）

```mermaid
sequenceDiagram
    participant Cron as GitHub Actions cron
    participant Runner as ubuntu-latest
    participant CM as ContentManager
    participant RSS as RSS Feeds (10)
    participant SG as ScriptGenerator
    participant Gemini as Gemini 2.5 Flash
    participant TTS as TTSGenerator
    participant GTTS as Gemini Flash TTS
    participant RGEN as RSSFeedGenerator
    participant GHP as GitHub Pages (gh-pages)
    participant Spotify as Spotify / Apple Podcasts

    Cron->>Runner: 毎日 21:00 UTC (06:00 JST)
    Runner->>Runner: get_daily_speakers() — 曜日ローテーションで出演者決定
    Runner->>CM: generate() 開始

    rect rgb(230, 245, 255)
        Note over CM,RSS: 1. コンテンツ収集（日付フィルタ + 重複排除）
        CM->>RSS: fetch_rss_feeds(max=5, hours=24)
        RSS-->>CM: 記事リスト
        CM->>CM: 日付フィルタ (24h) → 重複排除 (URL+タイトル類似度)
    end

    rect rgb(230, 255, 230)
        Note over SG,Gemini: 2. 台本生成 + 発音補正
        CM->>SG: articles
        SG->>Gemini: generate_content(SYSTEM_PROMPT_TEMPLATE + 記事)
        Note right of Gemini: ホスト名/ゲスト名が<br/>プロンプトに埋め込まれる
        Gemini-->>SG: 対話台本 JSON
        SG->>SG: PRONUNCIATION_MAP で読み仮名を付与
    end

    rect rgb(255, 245, 230)
        Note over TTS,GTTS: 3. 音声生成（Multi-Speaker TTS 1コール）
        SG->>TTS: Script (曜日のホスト/ゲスト)
        TTS->>GTTS: generate_content(Director's Notes + 全台本)
        GTTS-->>TTS: 音声バイナリ (PCM)
        TTS->>TTS: WAV保存 → MP3変換 (128kbps) → WAV削除
    end

    rect rgb(245, 230, 255)
        Note over RGEN,GHP: 4. RSS更新 & 配信
        TTS->>RGEN: MP3 + metadata
        RGEN->>RGEN: feed.xml に新エピソード追加
        RGEN->>GHP: MP3 + feed.xml を gh-pages に push
        GHP-->>Spotify: RSS定期取得 → 新エピソード自動反映
    end
```

### 3.2 エラー時フォールバック

```mermaid
flowchart TD
    A["ScriptGenerator<br/>台本生成"] -->|成功| B["対話台本"]
    A -->|失敗| A2["記事テキストを<br/>そのまま読み上げ用に整形"]
    A2 --> B

    B --> C["TTSGenerator<br/>音声生成"]
    C -->|成功| D["音声ファイル"]
    C -->|失敗| C2["リトライ<br/>（最大3回、30秒間隔）"]
    C2 -->|成功| D
    C2 -->|失敗| C3["❌ 生成中止<br/>次回実行に委ねる"]

    D --> E["PodcastUploader<br/>アップロード"]
    E -->|成功| F["✅ gh-pages に push<br/>Spotify/Apple が自動取得"]
    E -->|失敗| E2["ローカル保存<br/>次回実行で自然リトライ"]
```

---

## 4. ファイル・ディレクトリ構成

```
auto-podcast/
├── .github/
│   └── workflows/
│       └── generate-podcast.yml   # GitHub Actions 定期実行
│
├── docs/                          # ドキュメント
│   ├── CRD.md                     #   構想・要件定義書
│   ├── HLD.md                     #   アーキテクチャ設計書
│   └── LLD.md                     #   詳細設計書
│
├── podcast_generator.py           # オーケストレーター
├── content_manager.py             # コンテンツ収集 + 日付フィルタ + 重複排除
├── script_generator.py            # 台本生成 + 発音補正 (PRONUNCIATION_MAP)
├── tts_generator.py               # Multi-Speaker TTS音声生成
├── rss_feed_generator.py          # ポッドキャスト配信用 RSS XML 生成
├── podcast_uploader.py            # メタデータ保存 + gh-pages デプロイ
├── config.py                      # 設定管理（曜日ローテーション含む）
├── generate_cover.py              # カバーアート生成 (Pillow)
├── cleanup_episodes.py            # 古いエピソードの自動削除（60日超）
│
├── pyproject.toml                 # プロジェクト定義 + 依存関係 (uv)
├── uv.lock                        # 依存ロックファイル
├── .python-version                # Python 3.11
├── CLAUDE.md                      # AI Agent向けガイダンス
├── README.md                      # プロジェクト説明
│
├── audio_files/                   # 生成音声ファイル（Git管理外）
├── content/                       # コンテンツ・メタデータ（Git管理外）
└── .env                           # 環境変数（Git管理外）
```

---

## 5. 技術スタック

| レイヤー | 技術 | 備考 |
|---------|------|------|
| **言語** | Python 3.11 | `.python-version` で固定 |
| **パッケージ管理** | uv | pyproject.toml + uv.lock |
| **LLM** | Gemini 2.5 Flash | 台本生成（無料枠） |
| **TTS** | Gemini 2.5 Flash Preview TTS | Multi-Speaker 音声生成（無料枠、RPD=10） |
| **RSS生成** | xml.etree.ElementTree | Apple Podcasts RSS仕様準拠 |
| **音声変換** | pydub + ffmpeg | WAV→MP3 (128kbps, 約5x圧縮) |
| **RSS解析** | feedparser | 12フィード対応（テクノロジー6 + 経済4） |
| **HTMLスクレイピング** | BeautifulSoup4 | 記事本文取得 |
| **API SDK** | google-genai v1.63+ | Gemini LLM + TTS 統合SDK |
| **環境変数** | python-dotenv | ローカル開発用 |
| **スケジューリング** | GitHub Actions cron | 毎日 06:00 JST (21:00 UTC) |
| **実行基盤** | GitHub Actions (ubuntu-latest) | Free tier 2000分/月 |
| **ホスティング** | GitHub Pages (gh-pages) | MP3 + RSS 配信。無料 100GB/月帯域 |
| **配信** | Spotify / Apple Podcasts | RSS経由で自動配信 |

---

## 6. 環境・デプロイ構成

### 6.1 環境一覧

| 環境 | 用途 | 認証 |
|------|------|------|
| **ローカル開発** | テスト・手動実行 | `.env` ファイル内 GEMINI_API_KEY |
| **GitHub Actions** | 定期自動実行 | GitHub Secrets `GEMINI_API_KEY` |

### 6.2 GitHub Actions ワークフロー

```yaml
# .github/workflows/generate-podcast.yml
on:
  schedule:
    - cron: "0 21 * * *"    # 毎日 06:00 JST
  workflow_dispatch:         # 手動実行対応

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - Checkout → uv setup → uv sync → ffmpeg install
      - 既存 feed.xml を gh-pages から curl で復元（エピソード蓄積のため）
      - podcast_generator.py 実行（生成 + feed.xml 追記）
      - gh-pages ブランチに MP3 + feed.xml を push
      - 古いエピソードのクリーンアップ（60日超）
      - Artifacts にバックアップ保存（90日）
```

- GitHub Actions はクリーン環境のため、Generate 前に gh-pages の既存 feed.xml を復元する
- 生成した MP3 + feed.xml は **gh-pages ブランチ** に自動 push
- GitHub Pages が `https://necoha.github.io/auto-podcast/` で配信
- Spotify / Apple Podcasts が RSS を定期取得 → 新エピソード自動反映
- Artifacts には90日間バックアップ保存

### 6.3 環境変数

| 変数名 | 用途 | 必須 |
|--------|------|------|
| `GEMINI_API_KEY` | Gemini API（台本生成 + TTS 共通） | Yes |
| `PODCAST_BASE_URL` | GitHub Pages のベースURL | No（デフォルト: `https://necoha.github.io/auto-podcast`） |
| `PODCAST_TITLE` | ポッドキャスト名 | No（デフォルトあり） |
| `PODCAST_LANGUAGE` | 言語コード | No（デフォルト: ja） |
| `PODCAST_OWNER_EMAIL` | RSS/Spotify登録用メールアドレス | Yes（GitHub Secrets） |

> **配信方式**: GitHub Pages で MP3 と RSS をホスティング。
> Spotify for Creators と Apple Podcasts Connect に RSS URL を初回登録するだけで、
> 以降は新エピソードが自動的に配信される。
>
> RSS URL: `https://necoha.github.io/auto-podcast/feed.xml`

---

## 7. エラーハンドリング戦略

| レベル | 戦略 |
|--------|------|
| **コンテンツ収集** | フィード単位でエラーキャッチ、取得できたフィードで続行 |
| **台本生成** | Gemini API失敗 → 記事テキストをそのまま読み上げテキストとして使用 |
| **音声生成** | Gemini TTS失敗 → リトライ（最大3回、30秒間隔）→ 失敗時は生成中止、次回実行に委ねる |
| **アップロード** | 失敗 → ローカル保存。次回実行で自然リトライ |
| **レート制限** | Gemini無料枠の制限に到達 → ログ出力して次回実行にスキップ |

---

## 8. セキュリティ

| 項目 | 対策 |
|------|------|
| APIキー | 環境変数で管理。コードに平文保存しない |
| Git管理 | `.env`, `audio_files/`, `content/` は `.gitignore` に追加 |
| 通信 | 全てHTTPS経由 |
| GitHub Actions | Secrets で API キー管理。GitHub Pages配信のためPublic（APIキーはSecretsで保護） |
