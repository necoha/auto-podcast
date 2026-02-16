# HLD - High-Level Design
## AI Auto Podcast アーキテクチャ設計書

**採用プラン: α（完全無料 × 高品質）**

---

## 1. システムアーキテクチャ概要

```mermaid
flowchart TD
    subgraph CI["GitHub Actions"]
        Cron["⏰ cron: 毎日 00:00 JST<br/>(15:00 UTC)"]
        Runner["🖥️ ubuntu-latest"]
    end

    subgraph App["PodcastGenerator"]
        CM["1. ContentManager<br/>収集 + 日付フィルタ + 重複排除"]
        SG["2. ScriptGenerator<br/>台本生成 + 発音補正"]
        TTS["3. TTSGenerator<br/>Multi-Speaker TTS"]
        MP3["3.5 MP3変換<br/>pydub + ffmpeg"]
        UP["4. PodcastUploader<br/>メタデータ保存"]
    end

    subgraph External["外部サービス"]
        RSS[("RSS Feeds<br/>テクノロジー7 + 経済5")]
        GeminiLLM["Gemini 2.5 Flash<br/>台本生成 API"]
        GeminiTTS["Gemini Flash TTS<br/>Multi-Speaker 音声生成"]
        Spotify["Spotify for Creators<br/>配信プラットフォーム"]
    end

    Cron --> Runner
    Runner --> CM
    CM --> SG --> TTS --> MP3 --> UP

    CM -.-> RSS
    SG -.-> GeminiLLM
    TTS -.-> GeminiTTS
    UP -.-> Spotify
```

---

## 2. コンポーネント構成

### 2.1 コンポーネント一覧

| コンポーネント | モジュール | 責務 |
|---------------|-----------|------|
| **PodcastGenerator** | `podcast_generator.py` | オーケストレーター。収集→台本→音声→アップロードの統合制御 |
| **ContentManager** | `content_manager.py` | RSSフィードからのコンテンツ収集・テキスト処理（既存流用） |
| **ScriptGenerator** | `script_generator.py` | Gemini Flash APIでポッドキャスト対話台本を生成 |
| **TTSGenerator** | `tts_generator.py` | Gemini Flash TTS APIで台本から音声ファイルを生成 |
| **PodcastUploader** | `podcast_uploader.py` | 生成した音声をSpotify for Creatorsにアップロード |
| **Config** | `config.py` | 全体設定管理（環境変数・定数） |

### 2.2 コンポーネント関係図

```mermaid
graph TD
    PG["PodcastGenerator<br/><i>podcast_generator.py</i>"]
    CM["ContentManager<br/><i>content_manager.py</i>"]
    SG["ScriptGenerator<br/><i>script_generator.py</i>"]
    TTS["TTSGenerator<br/><i>tts_generator.py</i>"]
    UP["PodcastUploader<br/><i>podcast_uploader.py</i>"]
    CFG["Config<br/><i>config.py</i>"]

    PG --> CM
    PG --> SG
    PG --> TTS
    PG --> UP

    CM -.->|参照| CFG
    SG -.->|参照| CFG
    TTS -.->|参照| CFG
    UP -.->|参照| CFG
    PG -.->|参照| CFG
```

### 2.3 旧アーキテクチャとの差分

| 項目 | 旧（Notebook LM） | 新（プランα） |
|------|-------------------|--------------|
| 音声生成 | Selenium + Notebook LM | Gemini Flash TTS API |
| 台本生成 | Notebook LM 内部 | Gemini Flash API（明示的） |
| 認証 | OAuth + Cookie + セッション管理 | APIキー1つ |
| ブラウザ | Chrome/Firefox/Chromium/Edge | 不要 |
| コード量 | ~4,500行（6ファイル） | ~300行（3ファイル新規） |
| CI動作 | モック音声のみ | 実音声生成可能 |

---

## 3. データフロー

### 3.1 メインフロー（日次生成）

```mermaid
sequenceDiagram
    participant Cron as GitHub Actions cron
    participant Runner as ubuntu-latest
    participant CM as ContentManager
    participant RSS as RSS Feeds (12)
    participant SG as ScriptGenerator
    participant Gemini as Gemini 2.5 Flash
    participant TTS as TTSGenerator
    participant GTTS as Gemini Flash TTS
    participant UP as PodcastUploader
    participant Art as Actions Artifacts

    Cron->>Runner: 毎日 15:00 UTC (00:00 JST)
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
        SG->>Gemini: generate_content(SYSTEM_PROMPT + 記事)
        Gemini-->>SG: 対話台本 JSON
        SG->>SG: PRONUNCIATION_MAP で読み仮名を付与
    end

    rect rgb(255, 245, 230)
        Note over TTS,GTTS: 3. 音声生成（Multi-Speaker TTS 1コール）
        SG->>TTS: Script (HostA/GuestB)
        TTS->>GTTS: generate_content(Director's Notes + 全台本)
        GTTS-->>TTS: 音声バイナリ (PCM)
        TTS->>TTS: WAV保存 → MP3変換 (128kbps) → WAV削除
    end

    rect rgb(245, 230, 255)
        Note over UP,Art: 4. 保存
        TTS->>UP: MP3 + metadata
        UP->>UP: メタデータJSON保存
        UP->>Art: MP3 + JSON を Artifacts にアップロード
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
    C -->|失敗| C2["Google Cloud TTS WaveNet<br/>（無料枠）で再試行"]
    C2 -->|成功| D
    C2 -->|失敗| C3["❌ 生成中止<br/>次回実行に委ねる"]

    D --> E["PodcastUploader<br/>アップロード"]
    E -->|成功| F["✅ Spotify配信完了"]
    E -->|失敗| E2["ローカル保存<br/>+ リトライキュー追加"]
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
├── podcast_uploader.py            # メタデータ保存
├── config.py                      # 設定管理
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
| **音声変換** | pydub + ffmpeg | WAV→MP3 (128kbps, 約5x圧縮) |
| **RSS解析** | feedparser | 12フィード対応（テクノロジー7 + 経済5） |
| **HTMLスクレイピング** | BeautifulSoup4 | 記事本文取得 |
| **API SDK** | google-genai v1.63+ | Gemini LLM + TTS 統合SDK |
| **環境変数** | python-dotenv | ローカル開発用 |
| **スケジューリング** | GitHub Actions cron | 毎日 00:00 JST (15:00 UTC) |
| **実行基盤** | GitHub Actions (ubuntu-latest) | Free tier 2000分/月 |
| **配信** | Spotify for Creators | 無料・無制限ホスティング |

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
    - cron: "0 15 * * *"    # 毎日 00:00 JST
  workflow_dispatch:         # 手動実行対応

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - Checkout → uv setup → uv sync → podcast_generator.py → Artifacts upload
```

- 生成した MP3 + メタデータ JSON は **Actions Artifacts** に90日間保存
- 手動で Spotify for Creators にアップロード（API未提供のため）

### 6.3 環境変数

| 変数名 | 用途 | 必須 |
|--------|------|------|
| `GEMINI_API_KEY` | Gemini API（台本生成 + TTS 共通） | Yes |
| `PODCAST_TITLE` | ポッドキャスト名 | No（デフォルトあり） |
| `PODCAST_LANGUAGE` | 言語コード | No（デフォルト: ja） |

> **注**: Spotify for Creators に公式アップロードAPIがない場合は、
> 手動アップロード or GitHub Pages + 自前RSS にフォールバック。
> その場合 `PODCAST_BASE_URL` と `feedgen` が必要になる。

---

## 7. エラーハンドリング戦略

| レベル | 戦略 |
|--------|------|
| **コンテンツ収集** | フィード単位でエラーキャッチ、取得できたフィードで続行 |
| **台本生成** | Gemini API失敗 → 記事テキストをそのまま読み上げテキストとして使用 |
| **音声生成** | Gemini TTS失敗 → Google Cloud TTS WaveNet（無料枠）にフォールバック |
| **アップロード** | 失敗 → ローカル保存 + 次回リトライキューに追加 |
| **レート制限** | Gemini無料枠の制限に到達 → ログ出力して次回実行にスキップ |

---

## 8. セキュリティ

| 項目 | 対策 |
|------|------|
| APIキー | 環境変数で管理。コードに平文保存しない |
| Git管理 | `.env`, `audio_files/`, `content/` は `.gitignore` に追加 |
| 通信 | 全てHTTPS経由 |
| GitHub Actions | Secrets で API キー管理。リポジトリは Private 推奨 |
