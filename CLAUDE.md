# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Auto Podcast — 最新ニュースを自動収集し、Gemini AIで台本生成 → TTS音声合成 → Spotify配信する完全無料（$0/月）のポッドキャスト自動生成システム。

**採用プラン（Plan α）**: Gemini 2.5 Flash（LLM + TTS）+ Cloud Scheduler + Spotify for Creators

## Technology Stack

- **Python 3.11+** — メイン言語
- **google-genai** — Gemini API（LLM台本生成 + TTS音声合成、1パッケージで両方対応）
- **feedparser** — RSSフィード解析
- **Cloud Scheduler + Cloud Functions** — 定期実行
- **Spotify for Creators** — ポッドキャスト配信（無料）

## Common Commands

```bash
# 依存関係インストール
pip install -r requirements.txt

# ポッドキャスト生成（手動）
python podcast_generator.py

# コンテンツ収集テスト
python -c "from content_manager import ContentManager; cm = ContentManager(); print(cm.create_daily_content(['AI', 'Technology']))"

# Cloud Functionsデプロイ
gcloud functions deploy generate_podcast --runtime python311 --trigger-http --set-env-vars GEMINI_API_KEY=your-key
```

## Architecture

### Pipeline

```
RSS → ContentManager → ScriptGenerator → TTSGenerator → PodcastUploader
         (feedparser)    (Gemini LLM)     (Gemini TTS)   (Spotify API)
```

### Core Components

1. **ContentManager** (`content_manager.py`) — RSSフィード収集、記事抽出・整形
2. **ScriptGenerator** (`script_generator.py`) — Gemini 2.5 Flashで対話形式の台本生成
3. **TTSGenerator** (`tts_generator.py`) — Gemini 2.5 Flash Preview TTSで音声合成（WAV→MP3）
4. **PodcastUploader** (`podcast_uploader.py`) — Spotify for Creatorsへアップロード
5. **PodcastGenerator** (`podcast_generator.py`) — 全体オーケストレーション

### Key Design Decisions

- **Single API Key**: `GEMINI_API_KEY` のみで LLM + TTS 両方を利用
- **UIスクレイピング禁止**: 全て公式APIベースで安定動作
- **フォールバック**: TTS失敗時はモデル切り替え → リトライ → スキップ

## Configuration

### Environment Variables

| 変数 | 必須 | 説明 |
|------|------|------|
| `GEMINI_API_KEY` | Yes | Google AI Studio APIキー |

### Key Settings in `config.py`

- `RSS_FEEDS` — 監視するRSSフィード一覧
- `TTS_MODEL` — TTSモデル名（default: `gemini-2.5-flash-preview-tts`）
- `TTS_VOICE` — 音声名（default: `Kore`）
- `AUDIO_OUTPUT_DIR` — 音声ファイル出力先
- `MAX_CONTENT_LENGTH` — コンテンツ文字数制限

## Free Tier Limits

- **Gemini 2.5 Flash（LLM）**: 500 req/日、入出力無料
- **Gemini 2.5 Flash Preview TTS**: 入出力ともに無料
- **Cloud Functions**: 200万回/月
- **Cloud Scheduler**: 3ジョブ無料

## Documentation

- `docs/CRD.md` — 構想・要件定義書（技術選定比較、プラン比較）
- `docs/HLD.md` — 概要設計書（アーキテクチャ、Mermaidフロー図）
- `docs/LLD.md` — 詳細設計書（クラス設計、API仕様、Mermaidクラス図）