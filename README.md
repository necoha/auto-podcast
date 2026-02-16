# AI Auto Podcast

最新ニュースを自動収集し、Gemini AIでポッドキャスト台本を生成、TTS音声合成でエピソードを作成・配信するシステムです。

## 特徴

- **完全無料（$0/月）**: Gemini 2.5 Flash無料枠のみで運用
- **公式APIベース**: UIスクレイピング不要、安定動作
- **自動化**: Cloud Scheduler + Cloud Functionsで定期実行
- **高品質TTS**: Gemini 2.5 Flash Preview TTSによる自然な音声
- **ポッドキャスト配信**: Spotify for Creatorsで主要アプリに配信

## アーキテクチャ

```
RSSフィード → ContentManager → ScriptGenerator → TTSGenerator → PodcastUploader
                                  (Gemini LLM)     (Gemini TTS)   (Spotify for Creators)
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
pip install -r requirements.txt
```

### 4. ポッドキャスト生成（手動実行）

```bash
python podcast_generator.py
```

### 5. 自動実行（Cloud Functions）

```bash
gcloud functions deploy generate_podcast \
  --runtime python311 \
  --trigger-http \
  --set-env-vars GEMINI_API_KEY=your-key
```

Cloud Schedulerでcronジョブを設定し定期実行。

## プロジェクト構成

```
auto-podcast/
├── config.py              # 設定（APIキー、RSSフィード、TTS設定）
├── content_manager.py     # RSSフィード収集・コンテンツ管理
├── script_generator.py    # Gemini LLMでポッドキャスト台本生成
├── tts_generator.py       # Gemini TTSで音声合成
├── podcast_uploader.py    # Spotify for Creatorsへアップロード
├── podcast_generator.py   # メインオーケストレーション
├── rss_feed_generator.py  # RSS生成（レガシー）
├── requirements.txt       # Python依存関係
├── docs/
│   ├── CRD.md             # 構想・要件定義書
│   ├── HLD.md             # 概要設計書
│   └── LLD.md             # 詳細設計書
└── audio_files/           # 生成された音声ファイル
```

## 設定オプション

### `config.py`

| 設定 | 説明 | デフォルト |
|------|------|-----------|
| `GEMINI_API_KEY` | Google AI Studio APIキー | 環境変数 |
| `RSS_FEEDS` | 監視するRSSフィード一覧 | NHK, ITmedia等 |
| `TTS_MODEL` | TTS使用モデル | `gemini-2.5-flash-preview-tts` |
| `TTS_VOICE` | TTS音声名 | `Kore` |
| `AUDIO_OUTPUT_DIR` | 音声出力ディレクトリ | `./audio_files` |
| `MAX_CONTENT_LENGTH` | 入力コンテンツ文字数制限 | `10000` |

## 無料枠の制限

| サービス | 無料枠 |
|----------|--------|
| Gemini 2.5 Flash（LLM） | 500 req/日 |
| Gemini 2.5 Flash Preview TTS | 入出力ともに無料 |
| Cloud Functions | 200万回/月 |
| Cloud Scheduler | 3ジョブ無料 |
| Spotify for Creators | 完全無料 |

## トラブルシューティング

| 問題 | 対処 |
|------|------|
| APIキーエラー | `.env` の `GEMINI_API_KEY` を確認 |
| TTS生成失敗 | Gemini TTS Preview の利用可能リージョンを確認 |
| コンテンツ収集失敗 | RSSフィードURLの有効性を確認 |
| Cloud Functions失敗 | ログを `gcloud functions logs read` で確認 |

## ドキュメント

- [CRD（構想・要件定義書）](docs/CRD.md) — 技術選定比較、プラン比較
- [HLD（概要設計書）](docs/HLD.md) — システムアーキテクチャ、フロー図
- [LLD（詳細設計書）](docs/LLD.md) — クラス設計、API仕様、デプロイ手順

## ライセンス

MIT License