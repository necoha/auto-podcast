# AI Auto Podcast

最新ニュースを自動収集し、Gemini AIでポッドキャスト台本を生成、TTS音声合成でエピソードを作成・配信するシステムです。

## 特徴

- **無料枠・有料枠に対応**: Gemini APIの利用料金・制限はプロジェクトのプランによる
- **公式APIベース**: UIスクレイピング不要、安定動作
- **自動化**: GitHub Actionsで毎日03:17 JSTに生成開始予定、完了後に配信
- **音声合成**: Gemini 2.5 Flash Preview TTSを0.8倍速で配信
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

現在の台本生成はRSS記事のタイトル・媒体名・URLを入力とし、元記事本文との事実照合は行いません。配信前に原稿の内容を確認してください。

## セットアップ

### 1. 前提条件

- Python 3.11+
- Google AI Studio APIキー（無料枠・有料枠）
- Spotify for Creatorsアカウント（無料）

### 2. APIキーの取得

1. [Google AI Studio](https://aistudio.google.com/apikey) でAPIキーを作成
2. 環境変数に設定:
   ```bash
   cp .env.example .env
   # .env に GEMINI_API_KEY と PODCAST_OWNER_EMAIL を記入
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

GitHub Secrets に `GEMINI_API_KEY` と `PODCAST_OWNER_EMAIL` を設定すると、毎日 03:17 JST（前日18:17 UTC、cron: `17 18 * * *`）に生成開始予定となります。
毎時0分の混雑を避ける設定ですが、GitHub側の混雑や障害による開始遅延は起こり得ます。公開は生成完了・デプロイ後です。
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
| `RSS_FEEDS` | 監視するRSSフィード一覧 | 国内技術5 + 海外技術3 + 国内経済3 = 11 |
| `LLM_MODEL` | 台本生成・セルフレビュー用モデル | `gemini-3.8-flash` |
| `LLM_FALLBACK_MODELS` | 503継続時に試す予備モデル（カンマ区切り、優先順） | `gemini-2.5-flash` |
| `TTS_MODEL` | TTS使用モデル | `gemini-2.5-flash-preview-tts` |
| `TTS_TEMPO` | 音程を保った音声再生速度 | `0.8`（元の速さは`1.0`） |
| `TTS_VOICE` | デフォルトTTS音声名 | `Kore` |
| `TTS_MAX_REQUESTS_PER_PODCAST` | 1番組あたりのTTS API呼び出し上限 | `5` |
| `DAILY_SPEAKERS` | 曜日ローテーションテーブル | 7ペア×14人 |
| `PODCAST_BASE_URL` | GitHub Pages URL | `necoha.github.io/auto-podcast` |
| `PODCAST_OWNER_EMAIL` | RSS/Spotify登録用メール | 環境変数 |

ローカルでは `.env` に `LLM_MODEL`、`LLM_FALLBACK_MODELS`、`TTS_MODEL`、`TTS_TEMPO` を設定できます。
GitHub Actionsでは同名のRepository Variablesを設定します。未設定または空欄なら上記の既定値を使用します。
台本生成は各モデルを最大5回試し、503の再試行上限時だけ予備モデルへ自動切り替えします。待機は60/120/180/240秒で、既定の2候補では最大10試行・待機合計20分/番組です。両版の実行と音声生成のため、Actionsのジョブ上限は60分です。
認証・設定エラーや429では切り替えません。短すぎる台本は同じモデルで再試行します。全候補で失敗した場合はお休み告知を配信し、台本生成に成功した場合は同じモデルでセルフレビューします。
候補の重複は除き、次の生成では主モデルから開始します。自動切り替えを無効にする場合は `LLM_FALLBACK_MODELS` に `LLM_MODEL` と同じモデル名だけを指定します。
既定の2.5 TTSはgenerateContent API、`gemini-3.1-flash-tts-preview` はInteractions APIで音声を生成します。
音声はWAV保存前にffmpegで減速するため、MP3変換に失敗した場合も同じ速度です。
TTSモデルの切り替えは引き続き手動設定です。主モデルと予備モデルの利用可否・料金・制限はAI Studioで確認してください。

## 利用枠と料金

| サービス | 条件 |
|----------|--------|
| Gemini 3.8 Flash（主LLM）/ Gemini 2.5 Flash（予備LLM） | 無料枠または有料枠。実際の制限・料金はAI Studioで確認 |
| Gemini 2.5 Flash Preview TTS | 無料枠または有料枠。実際の制限・料金はAI Studioで確認 |
| GitHub Actions | 2000分/月 |
| GitHub Pages | 1GB推奨、1GB以上は外部ストレージ移行を検討 |

TTSは通常、速報版2チャンク＋深掘り版2チャンクの合計4リクエストです。
一時障害時も各番組5リクエスト、定期実行1回あたり合計10リクエストを上限とします。
手動再実行も同じプロジェクトの日次枠を消費するため、実行前に
[Google AI Studio](https://aistudio.google.com/rate-limit?timeRange=last-28-days) で残量を確認してください。
実際の上限はAI Studioに表示されるプロジェクト単位の割り当てが優先されます。

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