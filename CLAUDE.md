# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Auto Podcast — 最新ニュースを自動収集し、Gemini AIで台本生成 → TTS音声合成 → GitHub Pages + RSSで配信する完全無料（$0/月）のポッドキャスト自動生成システム。

**採用プラン（Plan α）**: Gemini 3.8 Flash（LLM）+ Gemini 3.1 Flash TTS Preview + GitHub Actions + GitHub Pages + RSS → Spotify/Apple Podcasts

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

# ポッドキャスト生成（速報版）
uv run python podcast_generator.py

# ポッドキャスト生成（深掘り版）
uv run python deep_podcast_generator.py

# コンテンツ収集テスト
uv run python -c "from content_manager import ContentManager; cm = ContentManager(); print(cm.create_daily_content(['AI', 'Technology']))"
```

## Architecture

### Pipeline

```
【速報版】
RSS(13) → ContentManager → ScriptGenerator     → ScriptReviewer → TTSGenerator → RSSFeedGenerator → ValidateFeeds → gh-pages
             (feedparser)    (Gemini LLM)         (Gemini LLM)     (Gemini TTS)   (feed.xml)        (CI検証)       (GitHub Pages)
                                                                                                                            ↓
【深掘り版】                                                                                                               Spotify / Apple Podcasts
RSS(13) → ContentManager → DeepScriptGenerator → ScriptReviewer → TTSGenerator → RSSFeedGenerator → ValidateFeeds → gh-pages
             (feedparser)    (Gemini LLM)         (Gemini LLM)     (Gemini TTS)   (feed_deep.xml)   (CI検証)       (GitHub Pages)
```

### Core Components

1. **ContentManager** (`content_manager.py`) — RSSフィード収集、記事抽出・整形（速報版/深掘り版共有）
2. **ScriptGenerator** (`script_generator.py`) — Gemini 3.8 Flashで速報版台本生成（PRONUNCIATION_MAP 306エントリ）
3. **DeepScriptGenerator** (`deep_script_generator.py`) — ScriptGenerator継承、6次元分析の深掘り台本生成
4. **ScriptReviewer** (`script_reviewer.py`) — URL Contextで元記事と台本を6項目レビュー（フォーマット/会話品質/記事カバレッジ/TTS適合性/長さ/事実整合性）
5. **TTSGenerator** (`tts_generator.py`) — Gemini 3.1 Flash TTS PreviewのInteractions APIで音声合成（Multi-Speaker、曜日ローテーション）
6. **RSSFeedGenerator** (`rss_feed_generator.py`) — RSS XML生成・更新（速報版/深掘り版共用、`_sync_channel_metadata`でconfig値自動同期）
7. **PodcastUploader** (`podcast_uploader.py`) — メタデータ保存
8. **PodcastGenerator** (`podcast_generator.py`) — 速報版オーケストレーション
9. **DeepDivePodcastGenerator** (`deep_podcast_generator.py`) — 深掘り版オーケストレーション
10. **ValidateFeeds** (`validate_feeds.py`) — デプロイ前のfeed.xml/feed_deep.xml自動検証（CIでconfig値との整合性保証）

### Key Design Decisions

- **Single API Key**: `GEMINI_API_KEY` のみで LLM + TTS 両方を利用
- **UIスクレイピング禁止**: 全て公式APIベースで安定動作
- **LLMリトライ**: 台本生成で503エラー時に最大2回リトライ（30秒/60秒間隔）。失敗時は記事タイトル限定台本を配信
- **台本事実検証**: 生成後にURL Contextで元記事と照合して6項目を検査。数値・年月・制度変更などに引用範囲がない場合は不合格とし、検証失敗時は元台本ではなく記事タイトル限定台本を使用
- **通信制御**: Gemini SDK内の暗黙リトライを無効化し、LLMは3分、TTSは5分でタイムアウト。アプリ側の回数・予算内だけで再試行
- **フォールバック**: 事実検証失敗時は速報最大5件・深掘り最大3件の見出し限定台本へ縮退。TTS失敗時は生成中止
- **重複記事統合**: 速報版プロンプトで全記事に触れつつ同一トピックの重複は統合して紹介
- **発音正規化**: LLMが付けた漢字語の未検証ルビを除去後、`PRONUNCIATION_MAP`の承認済み読みを再適用。単独の「国」は「くに」と読む
- **TTS反復対策**: 台本を一度だけ読む指示に加え、PCMの先頭再出現を特徴量・波形相関で検出し、重複prefixを除去
- **CI検証**: デプロイ前にfeedメタデータをconfig値と自動照合、不整合時はデプロイ中止
- **著作権対策**: `_build_prompt`でsummary除去、プロンプトに著作権指示、エピソード説明にソースURL、disclaimer明示
- **RSSソース審査**: `RSS_FEEDS`・`CUSTOM_RSS_FEEDS`の追加前に `docs/CRD.md` の「4.1.1 RSSニュースソース採用・除外基準」に従う。既知の除外判断も同節を正本とする

## Configuration

### Environment Variables

| 変数 | 必須 | 説明 |
|------|------|------|
| `GEMINI_API_KEY` | Yes | Google AI Studio APIキー |
| `PODCAST_OWNER_EMAIL` | Yes | RSS/Spotify登録用メールアドレス |
| `LLM_MODEL` | No | 台本生成モデル。既定値`gemini-3.8-flash`。障害時は旧モデルへロールバック可能 |
| `TTS_MODEL` | No | 音声生成モデル。既定値`gemini-3.1-flash-tts-preview`。障害時は旧モデルへロールバック可能 |

### Key Settings in `config.py`

- `RSS_FEEDS` — 監視するRSSフィード一覧（技術系JP 6 + 技術系EN 3 + 経済系JP 4 = 13ソース）
- `MAX_ARTICLES` — 1フィードあたりの取得上限（default: `2`）
- `MAX_TOTAL_ARTICLES` — 全フィード合計の取得上限（default: `20`、URL Contextの20 URL制限内）
- `LLM_MODEL` — 台本生成・URL Contextモデル名（default: `gemini-3.8-flash`）
- `TTS_MODEL` — TTSモデル名（default: `gemini-3.1-flash-tts-preview`）
- `TTS_VOICE` — デフォルト音声名（default: `Kore`）
- `DAILY_SPEAKERS` — 曜日ローテーションテーブル（7ペア×14人）
- `AUDIO_OUTPUT_DIR` — 音声ファイル出力先
- `MAX_CONTENT_LENGTH` — コンテンツ文字数制限
- `PODCAST_BASE_URL` — GitHub Pages URL
- `PODCAST_OWNER_EMAIL` — RSS/Spotify登録用メール

## Free Tier Limits

- **Gemini 3.8 Flash（LLM）**: 入出力無料（実際の上限はAI Studio参照）
- **URL Context**: 無料（通常2回/日、取得内容はGemini入力トークンに算入）
- **Gemini 3.1 Flash TTS Preview**: 入出力無料（実際の上限はAI Studio参照）
- **GitHub Actions**: 2000分/月
- **GitHub Pages**: 1GB推奨、帯域100GB/月

## Episode Retention

- **保持期間**: 60日（`config.EPISODE_RETENTION_DAYS`）
- **自動削除**: デプロイ時に `cleanup_old_episodes()` が60日超のMP3とfeed.xmlエントリを削除
- **想定最大容量**: ~600MB（1GB制限内）

## Deployment

- **スケジュール**: GitHub Actions cron `0 14 * * *` (23:00 JST)
- **ホスティング**: GitHub Pages (gh-pagesブランチ)
- **速報版 RSS URL**: `https://necoha.github.io/auto-podcast/feed.xml`
- **深掘り版 RSS URL**: `https://necoha.github.io/auto-podcast/feed_deep.xml`
- **Spotify**: 速報版RSSインポート済み。深掘り版は別途登録が必要
- **CI検証**: デプロイ前に `validate_feeds.py` が feed.xml / feed_deep.xml のメタデータを自動検証

## Speaker Rotation

14人のスピーカーが曜日ごとにローテーション（`config.DAILY_SPEAKERS`）。
`tts_generator.get_daily_speakers()` が当日のペアを返す。

## Documentation

- `docs/CRD.md` — 構想・要件定義書（技術選定比較、プラン比較）
- `docs/HLD.md` — 概要設計書（アーキテクチャ、Mermaidフロー図）
- `docs/LLD.md` — 詳細設計書（クラス設計、API仕様、CI検証仕様）
- `docs/LLD.md` — 詳細設計書（クラス設計、API仕様、Mermaidクラス図）