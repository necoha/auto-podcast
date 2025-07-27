# AI Auto Podcast

Notebook LMのAudio Overview機能を使用して自動でポッドキャストを生成・配信するシステムです。

## 🎯 特徴

- **完全無料**: Notebook LM無料版 + GitHub Actions + GitHub Pages
- **自動化**: RSSフィードからコンテンツを収集し、毎日自動生成
- **高品質**: Notebook LMのAI音声で自然な対話形式
- **RSS配信**: 標準的なポッドキャストアプリで購読可能

## 🚀 セットアップ

### 1. リポジトリをフォーク

このリポジトリをGitHubでフォークします。

### 2. 環境変数の設定

GitHubリポジトリの Settings > Secrets and variables > Actions で以下を設定:

```
GOOGLE_ACCOUNT_EMAIL=your-email@gmail.com
GOOGLE_ACCOUNT_PASSWORD=your-password  
PODCAST_BASE_URL=https://your-username.github.io/auto-podcast
```

### 3. GitHub Pagesの有効化

1. Settings > Pages
2. Source を "GitHub Actions" に設定

### 4. ワークフローの実行

- 自動実行: 毎日日本時間9時
- 手動実行: Actions タブから "Auto Podcast Generation" を実行

## 📁 プロジェクト構成

```
auto-podcast/
├── config.py              # 設定ファイル
├── content_manager.py      # コンテンツ収集・管理
├── notebooklm_automation.py # Notebook LM自動化
├── podcast_generator.py    # メイン生成ロジック
├── rss_feed_generator.py   # RSS配信
├── requirements.txt        # Python依存関係
├── .github/workflows/      # GitHub Actions設定
├── audio_files/           # 生成された音声ファイル
├── content/              # コンテンツとメタデータ
└── static/               # 配信用静的ファイル
```

## 🎮 使い方

### 手動実行

```bash
# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env
# .envファイルを編集

# ポッドキャスト生成
python podcast_generator.py
```

### トピックのカスタマイズ

`config.py`でRSSフィードやキーワードを変更:

```python
RSS_FEEDS = [
    "https://your-favorite-news.com/rss",
    "https://tech-blog.com/feed.xml"
]
```

### プロンプトのカスタマイズ

GitHub Actions手動実行時にカスタムプロンプトを指定可能:

```
テクノロジーニュースについて、初心者向けに優しく解説してください。
専門用語は分かりやすく説明し、具体例を交えてください。
```

## 🔧 設定オプション

### `config.py`

- `MAX_DAILY_GENERATIONS`: 1日の最大生成回数（デフォルト: 3）
- `GENERATION_SCHEDULE`: 生成スケジュール（daily/weekly/hourly）
- `RSS_FEEDS`: 監視するRSSフィード一覧
- `MAX_CONTENT_LENGTH`: コンテンツの最大文字数

### Notebook LM制限

**無料版の制限:**
- 1日3回まで音声生成
- 1ノートブック50ソースまで
- 100ノートブックまで

## 📡 配信

生成されたポッドキャストは以下でアクセス可能:

- **RSS Feed**: `https://your-username.github.io/auto-podcast/feed.xml`
- **Web Player**: `https://your-username.github.io/auto-podcast/`

## 🎵 ポッドキャストアプリでの購読

以下のアプリで購読可能:

- Apple Podcasts
- Spotify
- Google Podcasts
- その他RSS対応アプリ

RSS URLを登録: `https://your-username.github.io/auto-podcast/feed.xml`

## 🔒 セキュリティ

- Google認証情報はGitHub Secretsで管理
- 音声ファイルは自動でクリーンアップ（30日後）
- パスワード等をコードに記載しない

## 🐛 トラブルシューティング

### よくある問題

**1. Notebook LMログインエラー**
- 2要素認証を無効化
- アプリパスワードを使用
- CAPTCHAが表示される場合は手動実行

**2. GitHub Actions失敗**
- Secrets設定を確認
- 実行時間制限（6時間）に注意
- Chrome依存関係エラーの場合はワークフロー再実行

**3. RSS配信エラー**
- PODCAST_BASE_URLが正しく設定されているか確認
- GitHub Pagesが有効化されているか確認

### ログの確認

GitHub Actions > 実行履歴 でエラーログを確認できます。

## 📈 制限と注意事項

- **Notebook LM**: 1日3回まで（無料版）
- **GitHub Actions**: 月2000分まで（無料版）
- **GitHub Pages**: 1GB, 月100GB転送まで
- **音声ファイル**: 大きすぎる場合は外部ストレージ検討

## 🛠 カスタマイズ

### 音声品質向上

Notebook LMのプロンプトをカスタマイズ:

```python
custom_prompt = """
プロのポッドキャスターのように、以下の点を意識して話してください:
1. 聞き取りやすいスピードで話す
2. 重要なポイントは強調する
3. 聞き手との距離感を大切にする
4. 専門用語は必ず解説する
"""
```

### 配信頻度の変更

`config.py`とGitHub Actionsの cron を調整:

```yaml
# 毎日 → 週2回
- cron: '0 0 * * 1,4'  # 月曜と木曜
```

## 📝 ライセンス

MIT License

## 🤝 コントリビューション

プルリクエストやイシューを歓迎します！

## 📞 サポート

問題が発生した場合は、GitHubのIssuesで報告してください。