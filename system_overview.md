---
marp: true
theme: default
class: lead
paginate: true
backgroundColor: #fff
---

# 🎙️ AI Auto Podcast System
## Notebook LM Audio Overview を活用した自動ポッドキャスト配信システム

**完全無料 × 自動化 × 高品質音声**

---

## 📋 システム概要

### 🎯 目的
- RSSフィードから最新ニュースを自動収集
- Notebook LMのAudio Overview機能で高品質な対話音声を生成
- RSS配信でポッドキャストアプリに自動配信

### 💰 コスト
- **完全無料** で運用可能
- GitHub Actions + GitHub Pages + Notebook LM無料版

---

## 🏗️ システム構成図

```mermaid
graph TB
    subgraph "コンテンツ収集"
        A1[NHKニュース<br/>RSS]
        A2[ITmedia<br/>RSS]
        A3[TechCrunch<br/>RSS]
        A4[GitHub Blog<br/>RSS]
        A1 --> B[Content Manager]
        A2 --> B
        A3 --> B
        A4 --> B
    end
    
    subgraph "音声生成"
        B --> C[Podcast Generator]
        C --> D[OAuth認証]
        D --> E[Notebook LM<br/>Audio Overview]
        E --> F[MP3音声ファイル]
    end
    
    subgraph "配信システム"
        F --> G[RSS Feed Generator]
        G --> H[GitHub Pages<br/>ホスティング]
        H --> I1[Apple Podcasts]
        H --> I2[Spotify]
        H --> I3[Google Podcasts]
    end
    
    subgraph "自動化"
        J[GitHub Actions<br/>スケジューラー] --> C
        K[GitHub Secrets] --> D
    end
    
    style A1 fill:#e1f5fe
    style A2 fill:#e1f5fe
    style A3 fill:#e1f5fe
    style A4 fill:#e1f5fe
    style E fill:#f3e5f5
    style H fill:#e8f5e8
    style J fill:#fff3e0
```

---

## 📊 データフロー

```mermaid
sequenceDiagram
    participant GHA as GitHub Actions
    participant CM as Content Manager
    participant RSS as RSS Sources
    participant NLM as Notebook LM
    participant GHP as GitHub Pages
    
    Note over GHA: 毎日9時に自動実行
    GHA->>CM: コンテンツ収集開始
    CM->>RSS: RSS記事取得
    RSS-->>CM: 最新記事データ
    CM->>CM: テキスト処理・要約
    
    Note over CM,NLM: OAuth認証
    CM->>NLM: 処理済みテキスト送信
    NLM->>NLM: Audio Overview生成
    NLM-->>GHA: MP3音声ファイル
    
    GHA->>GHA: RSS Feed生成
    GHA->>GHP: 静的ファイルデプロイ
    
    Note over GHP: ポッドキャスト配信開始
```

---

## 🔄 自動化ワークフロー

### ⏰ **スケジュール実行**
```yaml
# 毎日日本時間9時に自動実行
schedule:
  - cron: '0 0 * * *'
```

### 🔧 **実行ステップ**
1. **コンテンツ収集** - RSS記事取得
2. **OAuth認証** - Notebook LMアクセス
3. **音声生成** - Audio Overview作成
4. **RSS更新** - 配信フィード更新
5. **GitHub Pages** - 自動デプロイ

---

## 🎵 コンテンツソース

### 📰 **現在の設定**
- **NHKニュース** - 一般ニュース
- **ITmedia** - テクノロジー
- **TechCrunch** - スタートアップ
- **Ars Technica** - 技術詳細
- **GitHub Blog** - 開発者情報

### ⚙️ **カスタマイズ可能**
```python
RSS_FEEDS = [
    "https://your-favorite-news.com/rss",
    "https://custom-blog.com/feed.xml"
]
```

---

## 🔐 認証システム

### 🎫 **OAuth 2.0 認証**
```mermaid
sequenceDiagram
    participant GA as GitHub Actions
    participant GC as Google Cloud
    participant NL as Notebook LM
    
    GA->>GC: OAuth認証情報
    GC->>GA: アクセストークン
    GA->>NL: 認証済みアクセス
    NL->>GA: Audio Overview
```

### 🔑 **セキュリティ**
- GitHub Secretsで認証情報を安全に管理
- OAuth認証でアプリパスワード不要
- セッション永続化で効率的な認証

---

## 📁 ファイル構成

```mermaid
graph LR
    subgraph "Repository Root"
        A[auto-podcast/]
    end
    
    subgraph "Python Scripts 🐍"
        B1[podcast_generator.py<br/>メイン生成ロジック]
        B2[oauth_automation.py<br/>OAuth + Selenium]
        B3[content_manager.py<br/>RSS収集・処理]
        B4[rss_feed_generator.py<br/>RSS配信]
    end
    
    subgraph "Configuration ⚙️"
        C1[config.py<br/>設定ファイル]
        C2[requirements.txt<br/>依存関係]
    end
    
    subgraph "GitHub Actions 🚀"
        D1[.github/workflows/<br/>generate_podcast.yml]
    end
    
    subgraph "Generated Content 📁"
        E1[audio_files/<br/>音声ファイル]
        E2[content/<br/>メタデータ]
        E3[static/<br/>配信用ファイル]
    end
    
    A --> B1
    A --> B2
    A --> B3
    A --> B4
    A --> C1
    A --> C2
    A --> D1
    A --> E1
    A --> E2
    A --> E3
    
    style B1 fill:#e3f2fd
    style B2 fill:#e3f2fd
    style B3 fill:#e3f2fd
    style B4 fill:#e3f2fd
    style C1 fill:#f3e5f5
    style C2 fill:#f3e5f5
    style D1 fill:#e8f5e8
    style E1 fill:#fff3e0
    style E2 fill:#fff3e0
    style E3 fill:#fff3e0
```

---

## 🌐 配信システム

### 📡 **RSS配信**
```xml
<rss version="2.0">
  <channel>
    <title>AI Auto Podcast</title>
    <link>https://necoha.github.io/auto-podcast/</link>
    <item>
      <title>第1話 - AI Auto Podcast</title>
      <enclosure url="https://.../episode_001.mp3" 
                 type="audio/mpeg"/>
    </item>
  </channel>
</rss>
```

### 📱 **ポッドキャストアプリ対応**
- Apple Podcasts、Spotify、Google Podcasts
- RSS URL: `https://necoha.github.io/auto-podcast/feed.xml`

---

## 💰 無料サービス活用

```mermaid
pie title 無料サービス構成比
    "Notebook LM" : 25
    "GitHub Actions" : 25
    "GitHub Pages" : 25
    "RSS収集" : 25
```

### 📊 サービス制限とコスト

```mermaid
graph TB
    subgraph "Notebook LM 🎵"
        A1[音声生成: 1日3回まで]
        A2[コスト: 無料]
    end
    
    subgraph "GitHub Actions 🔄"
        B1[CI/CD: 月2000分]
        B2[コスト: 無料]
    end
    
    subgraph "GitHub Pages 🌐"
        C1[ホスティング: 1GB]
        C2[転送量: 100GB/月]
        C3[コスト: 無料]
    end
    
    subgraph "RSS収集 📡"
        D1[記事取得: 無制限]
        D2[コスト: 無料]
    end
    
    E[月額運用コスト: 0円] 
    
    A2 --> E
    B2 --> E
    C3 --> E
    D2 --> E
    
    style E fill:#4caf50,color:#fff
    style A1 fill:#f3e5f5
    style B1 fill:#e3f2fd
    style C1 fill:#e8f5e8
    style C2 fill:#e8f5e8
    style D1 fill:#fff3e0
```

---

## 🔧 技術スタック

```mermaid
mindmap
  root((AI Auto<br/>Podcast))
    Backend 🐍
      Python 3.11+
      Selenium
      feedgen
      feedparser
    Infrastructure ☁️
      GitHub Actions
      GitHub Pages
      OAuth 2.0
    Audio Processing 🎵
      Notebook LM
      MP3 Format
    Frontend 🌐
      HTML/CSS
      JavaScript
      RSS Feed
```

---

## 🚀 セットアップフロー

```mermaid
gitgraph
    commit id: "1. Repository準備"
    commit id: "2. OAuth設定"
    commit id: "3. GitHub Pages有効化"
    commit id: "4. Secrets設定"
    commit id: "5. 自動実行開始"
```

### セットアップステップ詳細

```mermaid
flowchart TD
    A[リポジトリクローン] --> B[Google Cloud Console設定]
    B --> C[OAuth認証情報作成]
    C --> D[GitHub Secrets設定]
    D --> E[GitHub Pages有効化]
    E --> F[ワークフロー実行テスト]
    F --> G[ポッドキャスト配信開始]
    
    D1[GOOGLE_OAUTH_CREDENTIALS]
    D2[PODCAST_BASE_URL]
    D3[OAUTH_SESSION_DATA]
    
    D --> D1
    D --> D2
    D --> D3
    
    style G fill:#4caf50,color:#fff
    style C fill:#f3e5f5
    style E fill:#e3f2fd
```

---

## 📈 システムの利点

### ✅ **完全自動化**
- 人手不要で継続的なポッドキャスト配信
- スケジュール実行で安定運用

### ✅ **高品質音声**
- Notebook LMの自然な対話形式
- プロフェッショナルなポッドキャスト品質

### ✅ **無料運用**
- 全サービス無料枠内で運用
- スケールアップ時も低コスト

### ✅ **カスタマイズ性**
- RSS源、生成頻度、プロンプト調整可能
- オープンソースで完全カスタマイズ

---

## 🔄 運用フロー（日次）

```mermaid
gantt
    title Daily Podcast Generation Flow
    dateFormat HH:mm
    axisFormat %H:%M
    
    section Morning
    RSS収集        :active, rss, 09:00, 09:05
    コンテンツ処理   :content, after rss, 09:10
    
    section Generation
    OAuth認証      :auth, after content, 09:12
    音声生成       :audio, after auth, 09:25
    
    section Publishing
    RSS更新       :feed, after audio, 09:27
    Pages配信     :deploy, after feed, 09:30
```

**毎朝9時に自動実行 → 30分以内にポッドキャスト配信完了**

---

## 🎯 今後の拡張可能性

```mermaid
graph TB
    subgraph "現在のシステム"
        A[AI Auto Podcast<br/>基本機能]
    end
    
    subgraph "コンテンツ強化 📊"
        B1[多言語対応]
        B2[専門分野別]
        B3[ユーザー投稿]
    end
    
    subgraph "AI機能向上 🤖"
        C1[プロンプト最適化]
        C2[感情表現向上]
        C3[話者個性設定]
    end
    
    subgraph "配信チャネル拡大 📱"
        D1[YouTube連携]
        D2[SNS自動投稿]
        D3[専用Webアプリ]
    end
    
    A --> B1
    A --> B2
    A --> B3
    A --> C1
    A --> C2
    A --> C3
    A --> D1
    A --> D2
    A --> D3
    
    style A fill:#4caf50,color:#fff
    style B1 fill:#e3f2fd
    style B2 fill:#e3f2fd
    style B3 fill:#e3f2fd
    style C1 fill:#f3e5f5
    style C2 fill:#f3e5f5
    style C3 fill:#f3e5f5
    style D1 fill:#fff3e0
    style D2 fill:#fff3e0
    style D3 fill:#fff3e0
```

---

## 🏁 まとめ

### 🎪 **実現できること**
- **完全無料**でプロ品質のポッドキャスト自動配信
- **Notebook LM**の最新AI技術活用
- **GitHub**エコシステムでの安定運用

### 🚀 **次のステップ**
1. OAuth認証情報設定
2. 初回手動実行テスト
3. RSS配信確認
4. ポッドキャストアプリで購読

**Let's start your AI-powered podcast journey! 🎙️**