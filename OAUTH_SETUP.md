# Google OAuth認証セットアップガイド

## 🔐 OAuth認証とは

OAuth認証は、アプリパスワードよりも安全で現代的な認証方式です。Googleが推奨するセキュアな方法で、2要素認証を有効にしたままでも安全にアクセスできます。

## 🎯 OAuth認証のメリット

- ✅ **高セキュリティ**: アプリパスワードより安全
- ✅ **細かい権限制御**: 必要最小限の権限のみ
- ✅ **トークンの自動更新**: 長期間利用可能
- ✅ **監査ログ**: アクセス履歴の追跡可能
- ✅ **即座の無効化**: 必要に応じて即座にアクセス取り消し

## 📋 セットアップ手順

### Step 1: Google Cloud Console設定

1. **Google Cloud Console** にアクセス
   - URL: https://console.cloud.google.com/

2. **プロジェクト作成**
   - 新しいプロジェクトを作成または既存プロジェクトを選択
   - プロジェクト名: `Auto Podcast`

3. **API有効化**
   - 「APIとサービス」→ 「ライブラリ」
   - 「Google Drive API」を検索して有効化
   - 「Gmail API」も有効化（オプション）

4. **OAuth同意画面設定**
   - 「APIとサービス」→ 「OAuth同意画面」
   - User Type: 「外部」を選択
   - アプリ名: `Auto Podcast`
   - ユーザーサポートメール: あなたのメールアドレス
   - 開発者の連絡先情報: あなたのメールアドレス
   - 「保存して次へ」

5. **認証情報作成**
   - 「APIとサービス」→ 「認証情報」
   - 「認証情報を作成」→ 「OAuthクライアントID」
   - アプリケーションタイプ: 「デスクトップアプリケーション」
   - 名前: `Auto Podcast OAuth`
   - 「作成」をクリック

6. **認証情報をダウンロード**
   - 作成された認証情報の「Client ID」と「Client Secret」をメモ

### Step 2: 認証情報の設定

#### 自動セットアップ（推奨）

```bash
# OAuth設定ヘルパーを実行
python oauth_setup.py
```

このスクリプトが以下を自動実行します：
- 対話式でClient IDとClient Secretを入力
- OAuth認証情報ファイルを生成
- GitHub Secrets用のBase64エンコード文字列を出力

#### 手動セットアップ

1. **認証情報ファイル作成**
   ```json
   {
     "client_id": "your-client-id.apps.googleusercontent.com",
     "client_secret": "your-client-secret",
     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
     "token_uri": "https://oauth2.googleapis.com/token",
     "redirect_uri": "urn:ietf:wg:oauth:2.0:oob"
   }
   ```

2. **Base64エンコード**
   ```bash
   # Linux/macOS
   cat google_oauth_credentials.json | base64 -w 0
   
   # または Python
   python -c "import json, base64; print(base64.b64encode(open('google_oauth_credentials.json').read().encode()).decode())"
   ```

### Step 3: GitHub Secrets設定

GitHubリポジトリの **Settings** → **Secrets and variables** → **Actions** で以下を設定:

#### Secret 1: GOOGLE_OAUTH_CREDENTIALS
- **Name**: `GOOGLE_OAUTH_CREDENTIALS`
- **Secret**: Step 2で生成したBase64エンコード文字列

#### Secret 2: PODCAST_BASE_URL
- **Name**: `PODCAST_BASE_URL`
- **Secret**: `https://your-username.github.io/auto-podcast`

### Step 4: 初回認証

#### ローカル環境での初回認証

```bash
# OAuth認証をテスト
python oauth_automation.py
```

1. ブラウザが自動で開きます
2. Googleアカウントでログイン
3. アプリケーションへのアクセス許可
4. 認証完了後、Enterキーを押す
5. セッション情報が自動保存される

#### CI/CD環境での認証

初回はローカルで認証を完了し、生成された `oauth_session.json` をGitHub Secretsに追加:

```bash
# セッション情報をBase64エンコード
cat oauth_session.json | base64 -w 0
```

GitHub Secretsに `OAUTH_SESSION_DATA` として保存

## 🔧 設定確認

### 必要なSecretsの確認

以下のSecretsが設定されていることを確認:

- ✅ `GOOGLE_OAUTH_CREDENTIALS` (OAuth認証情報)
- ✅ `PODCAST_BASE_URL` (ホスティングURL)
- ✅ `OAUTH_SESSION_DATA` (CI/CD用、オプション)

### テスト実行

```bash
# 手動テスト
python podcast_generator.py

# GitHub Actions手動実行
# Actions タブから "Auto Podcast Generation" を実行
```

## 🔒 セキュリティベストプラクティス

### ✅ 推奨事項

- **最小権限の原則**: 必要最小限のスコープのみ要求
- **定期的なトークン更新**: 自動更新機能を活用
- **アクセスログの監視**: Google Cloud Consoleでアクセス履歴確認
- **不要な認証情報は削除**: 使用しなくなった認証情報は即座に削除

### ❌ 避けるべきこと

- **認証情報の平文保存**: 必ずBase64エンコードやSecrets使用
- **広すぎる権限**: 必要以上の権限を要求しない
- **長期間の未更新**: 定期的にセキュリティレビュー実施

## 🚨 トラブルシューティング

### よくある問題

**1. OAuth認証エラー**
```
Error: invalid_client
```
- Client IDとClient Secretを再確認
- OAuth同意画面の設定を確認

**2. 権限エラー**
```
Error: insufficient_scope
```
- OAuth同意画面でスコープを追加
- 再認証が必要

**3. セッション期限切れ**
```
Error: invalid_grant
```
- `oauth_session.json` を削除して再認証
- CI/CD環境では `OAUTH_SESSION_DATA` を更新

### デバッグ手順

1. **ローカルでのテスト**
   ```bash
   # デバッグモードで実行
   python oauth_setup.py
   # "2. OAuth設定をテスト" を選択
   ```

2. **ログの確認**
   ```bash
   # GitHub Actions のログを確認
   # エラーメッセージから原因を特定
   ```

3. **認証情報の再生成**
   ```bash
   # 必要に応じて認証情報を完全に再作成
   python oauth_setup.py
   # "1. OAuth認証情報を作成" を選択
   ```

## 📞 サポートとヘルプ

### 公式ドキュメント
- [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)

### トラブル報告
問題が解決しない場合は、GitHub Issuesで以下の情報とともに報告:
- エラーメッセージの全文
- 実行環境（ローカル/GitHub Actions）
- 設定した認証情報の種類

## 🔄 メンテナンス

### 定期的なタスク

- **月次**: OAuth認証情報の利用状況確認
- **四半期**: セキュリティレビューとアクセス権限見直し
- **年次**: 認証情報の完全更新

### バックアップ戦略

- **認証情報のバックアップ**: 安全な場所に暗号化して保存
- **複数環境対応**: 開発用と本番用で別々の認証情報を使用
- **緊急時対応**: 迅速にアクセスを無効化できる体制を整備