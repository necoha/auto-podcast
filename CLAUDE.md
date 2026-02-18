# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Auto Podcast — 最新ニュースを自動収集し、Gemini AIで台本生成 → TTS音声合成 → GitHub Pages + RSSで配信する完全無料（$0/月）のポッドキャスト自動生成システム。

**採用プラン（Plan α）**: Gemini 2.5 Flash（LLM + TTS）+ GitHub Actions + GitHub Pages + RSS → Spotify/Apple Podcasts

## Technology Stack

- **Python 3.11+** — メイン言語
- **google-genai** — Gemini API（LLM台本生成 + TTS音声合成、1パッケージで両方対応）
- **feedparser** — RSSフィード解析
- **pydub + ffmpeg** — WAV→MP3変換
- **Pillow** — カバーアート生成
- **GitHub Actions** — 定期実行（毎日 06:00 JST）
- **GitHub Pages** — MP3 + RSSホスティング（gh-pagesブランチ）
- **Spotify / Apple Podcasts** — RSS経由で自動配信

## Common Commands

```bash
# 依存関係インストール
uv sync

# ポッドキャスト生成（手動）
uv run python podcast_generator.py

# コンテンツ収集テスト
uv run python -c "from content_manager import ContentManager; cm = ContentManager(); print(cm.create_daily_content(['AI', 'Technology']))"
```

## Architecture

### Pipeline

```
RSS → ContentManager → ScriptGenerator → TTSGenerator → RSSFeedGenerator → gh-pages
         (feedparser)    (Gemini LLM)     (Gemini TTS)   (feed.xml)        (GitHub Pages)
                                                                                ↓
                                                                     Spotify / Apple Podcasts
```

### Core Components

1. **ContentManager** (`content_manager.py`) — RSSフィード収集、記事抽出・整形
2. **ScriptGenerator** (`script_generator.py`) — Gemini 2.5 Flashで対話形式の台本生成
3. **TTSGenerator** (`tts_generator.py`) — Gemini 2.5 Flash Preview TTSで音声合成（Multi-Speaker、曜日ローテーション）
4. **RSSFeedGenerator** (`rss_feed_generator.py`) — ポッドキャスト配信用RSS XML生成・更新
5. **PodcastUploader** (`podcast_uploader.py`) — メタデータ保存
6. **PodcastGenerator** (`podcast_generator.py`) — 全体オーケストレーション（曜日ローテーション含む）

### Key Design Decisions

- **Single API Key**: `GEMINI_API_KEY` のみで LLM + TTS 両方を利用
- **UIスクレイピング禁止**: 全て公式APIベースで安定動作
- **フォールバック**: TTS失敗時はモデル切り替え → リトライ → スキップ

## Configuration

### Environment Variables

| 変数 | 必須 | 説明 |
|------|------|------|
| `GEMINI_API_KEY` | Yes | Google AI Studio APIキー |
| `PODCAST_OWNER_EMAIL` | Yes | RSS/Spotify登録用メールアドレス |

### Key Settings in `config.py`

- `RSS_FEEDS` — 監視するRSSフィード一覧（技術系6 + 経済系4 = 10ソース）
- `TTS_MODEL` — TTSモデル名（default: `gemini-2.5-flash-preview-tts`）
- `TTS_VOICE` — デフォルト音声名（default: `Kore`）
- `DAILY_SPEAKERS` — 曜日ローテーションテーブル（7ペア×14人）
- `AUDIO_OUTPUT_DIR` — 音声ファイル出力先
- `MAX_CONTENT_LENGTH` — コンテンツ文字数制限
- `PODCAST_BASE_URL` — GitHub Pages URL
- `PODCAST_OWNER_EMAIL` — RSS/Spotify登録用メール

## Free Tier Limits

- **Gemini 2.5 Flash（LLM）**: 500 req/日、入出力無料
- **Gemini 2.5 Flash Preview TTS**: 入出力ともに無料（RPD=10）
- **GitHub Actions**: 2000分/月
- **GitHub Pages**: 1GB推奨、帯域100GB/月

## Episode Retention

- **保持期間**: 60日（`config.EPISODE_RETENTION_DAYS`）
- **自動削除**: デプロイ時に `cleanup_old_episodes()` が60日超のMP3とfeed.xmlエントリを削除
- **想定最大容量**: ~600MB（1GB制限内）

## Deployment

- **スケジュール**: GitHub Actions cron `0 21 * * *` (06:00 JST)
- **ホスティング**: GitHub Pages (gh-pagesブランチ)
- **RSS URL**: `https://necoha.github.io/auto-podcast/feed.xml`
- **Spotify**: RSSインポート済み。新エピソード自動反映

## Speaker Rotation

14人のスピーカーが曜日ごとにローテーション（`config.DAILY_SPEAKERS`）。
`tts_generator.get_daily_speakers()` が当日のペアを返す。

## Documentation

- `docs/CRD.md` — 構想・要件定義書（技術選定比較、プラン比較）
- `docs/HLD.md` — 概要設計書（アーキテクチャ、Mermaidフロー図）
- `docs/LLD.md` — 詳細設計書（クラス設計、API仕様、Mermaidクラス図）