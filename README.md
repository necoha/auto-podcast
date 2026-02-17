# AI Auto Podcast

最新ニュースを自動収集し、Gemini AIでポッドキャスト台本を生成、TTS音声合成でエピソードを作成・配信するシステムです。

## 特徴

- **完全無料（$0/月）**: Gemini 2.5 Flash無料枠のみで運用
- **公式APIベース**: UIスクレイピング不要、安定動作
- **自動化**: GitHub Actionsで毎日06:00 JSTに自動生成・配信
- **高品質TTS**: Gemini 2.5 Flash Preview TTSによる自然な音声
- **14人日替わりローテーション**: 曜日ごとに異なるホスト＋ゲストペア（7ペア）
- **ポッドキャスト配信**: GitHub Pages + RSS → Spotify / Apple Podcastsで自動配信

## アーキテクチャ

```
RSSフィード → ContentManager → ScriptGenerator → TTSGenerator → RSSFeedGenerator → GitHub Pages
                                  (Gemini LLM)     (Gemini TTS)   (feed.xml)         (gh-pages)
                                                                                         ↓
                                                                              Spotify / Apple Podcasts
```

詳細は [docs/HLD.md](docs/HLD.md) を参照。

## セットアップ

### 1. 前提条件

- Python 3.11+
- Google AI Studio APIキー（無料）
- Spotify for Creatorsアカウント（無料）

### 2. APIキーの取得

1. [Google AI Studio](https://aistudio.google.com/apikey) でAPIキーを作成
2. 環境変数に設定:
   ```bash
   cp .env.example .env
   # .env に GEMINI_API_KEY を記入
   ```

### 3. 依存関係のインストール

```bash
uv sync
```

### 4. ポッドキャスト生成（手動実行）

```bash
uv run podcast_generator.py
```

### 5. 自動実行（GitHub Actions）

GitHub Secrets に `GEMINI_API_KEY` を設定するだけで、毎日 06:00 JST に自動実行されます。
手動実行はActionsタブから `workflow_dispatch` で実行可能です。

## プロジェクト構成

```
auto-podcast/
├── config.py              # 設定（APIキー、RSSフィード、TTS設定、曜日ローテーション）
├── content_manager.py     # RSSフィード収集・コンテンツ管理
├── script_generator.py    # Gemini LLMでポッドキャスト台本生成
├── tts_generator.py       # Gemini TTSで音声合成（Multi-Speaker）
├── rss_feed_generator.py  # ポッドキャスト配信用RSS XML生成
├── podcast_uploader.py    # メタデータ保存
├── podcast_generator.py   # メインオーケストレーション
├── generate_cover.py      # カバーアート生成 (Pillow)
├── pyproject.toml         # プロジェクト設定・依存関係（uv）
├── .github/
│   └── workflows/
│       └── generate-podcast.yml  # GitHub Actions 定期実行
├── docs/
│   ├── CRD.md             # 構想・要件定義書
│   ├── HLD.md             # 概要設計書
│   └── LLD.md             # 詳細設計書
└── audio_files/           # 生成された音声ファイル（Git管理外）
```

## 設定オプション

### `config.py`

| 設定 | 説明 | デフォルト |
|------|------|-----------|
| `GEMINI_API_KEY` | Google AI Studio APIキー | 環境変数 |
| `RSS_FEEDS` | 監視するRSSフィード一覧 | テクノロジー7 + 経済5 |
| `TTS_MODEL` | TTS使用モデル | `gemini-2.5-flash-preview-tts` |
| `TTS_VOICE` | デフォルトTTS音声名 | `Kore` |
| `DAILY_SPEAKERS` | 曜日ローテーションテーブル | 7ペア×14人 |
| `PODCAST_BASE_URL` | GitHub Pages URL | `necoha.github.io/auto-podcast` |
| `PODCAST_OWNER_EMAIL` | RSS/Spotify登録用メール | 設定値 |

## 無料枠の制限

| サービス | 無料枠 |
|----------|--------|
| Gemini 2.5 Flash（LLM） | 500 req/日 |
| Gemini 2.5 Flash Preview TTS | 入出力ともに無料（RPD=10） |
| GitHub Actions | 2000分/月 |
| GitHub Pages | 1GB推奨、1GB以上は外部ストレージ移行を検討 |

## トラブルシューティング

| 問題 | 対処 |
|------|------|
| APIキーエラー | `.env` の `GEMINI_API_KEY` を確認 |
| TTS生成失敗 | Gemini TTS Preview の利用可能リージョンを確認 |
| コンテンツ収集失敗 | RSSフィードURLの有効性を確認 |
| Actions失敗 | Actionsタブのログを確認 |
| GitHub Pages 404 | gh-pagesブランチからのデプロイ設定を確認 |

## ドキュメント

- [CRD（構想・要件定義書）](docs/CRD.md) — 技術選定比較、プラン比較
- [HLD（概要設計書）](docs/HLD.md) — システムアーキテクチャ、フロー図
- [LLD（詳細設計書）](docs/LLD.md) — クラス設計、API仕様、デプロイ手順

## ライセンス

MIT License