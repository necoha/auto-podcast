"""
Google OAuth認証のセットアップヘルパー
Google Cloud Consoleでの設定手順とCredentials生成
"""

import json
import base64
import webbrowser
import os


def create_oauth_credentials():
    """OAuth認証情報を作成"""
    
    print("=== Google OAuth 認証設定 ===")
    print()
    
    print("1. Google Cloud Console設定")
    print("   以下の手順でOAuth認証を設定してください:")
    print()
    print("   a) Google Cloud Console (https://console.cloud.google.com/) にアクセス")
    print("   b) 新しいプロジェクトを作成または既存プロジェクトを選択")
    print("   c) 「APIとサービス」> 「認証情報」に移動")
    print("   d) 「認証情報を作成」> 「OAuthクライアントID」を選択")
    print("   e) アプリケーションタイプ: 「デスクトップアプリケーション」")
    print("   f) 名前: 「Auto Podcast OAuth」")
    print("   g) 「作成」をクリック")
    print()
    
    # ブラウザで開く
    open_browser = input("Google Cloud Consoleを開きますか？ (y/n): ")
    if open_browser.lower() == 'y':
        webbrowser.open("https://console.cloud.google.com/")
    
    print()
    print("2. OAuth認証情報の入力")
    print("   作成されたOAuthクライアントIDの情報を入力してください:")
    print()
    
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()
    
    if not client_id or not client_secret:
        print("エラー: Client IDとClient Secretは必須です")
        return None
    
    # OAuth認証情報を構築
    oauth_creds = {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob"
    }
    
    # ローカルファイルに保存
    with open('google_oauth_credentials.json', 'w') as f:
        json.dump(oauth_creds, f, indent=2)
    
    print()
    print("✅ OAuth認証情報を 'google_oauth_credentials.json' に保存しました")
    
    # GitHub Secrets用のエンコード
    oauth_json = json.dumps(oauth_creds)
    encoded_oauth = base64.b64encode(oauth_json.encode()).decode()
    
    print()
    print("3. GitHub Secrets設定")
    print("   以下の値をGitHub Secretsに設定してください:")
    print()
    print("   Secret名: GOOGLE_OAUTH_CREDENTIALS")
    print("   値:")
    print(f"   {encoded_oauth}")
    print()
    
    return oauth_creds


def test_oauth_setup():
    """OAuth設定をテスト"""
    
    print("=== OAuth設定テスト ===")
    
    if not os.path.exists('google_oauth_credentials.json'):
        print("エラー: OAuth認証情報ファイルが見つかりません")
        print("先に create_oauth_credentials() を実行してください")
        return False
    
    try:
        with open('google_oauth_credentials.json', 'r') as f:
            oauth_creds = json.load(f)
        
        required_fields = ['client_id', 'client_secret', 'auth_uri', 'token_uri']
        
        for field in required_fields:
            if field not in oauth_creds:
                print(f"エラー: 必須フィールド '{field}' が見つかりません")
                return False
        
        print("✅ OAuth認証情報の検証が完了しました")
        print()
        print("設定情報:")
        print(f"  Client ID: {oauth_creds['client_id'][:20]}...")
        print(f"  Client Secret: {oauth_creds['client_secret'][:10]}...")
        print(f"  Auth URI: {oauth_creds['auth_uri']}")
        print(f"  Token URI: {oauth_creds['token_uri']}")
        
        return True
        
    except Exception as e:
        print(f"エラー: OAuth認証情報の検証に失敗しました: {e}")
        return False


def setup_github_secrets_guide():
    """GitHub Secrets設定ガイド"""
    
    print("=== GitHub Secrets 設定ガイド ===")
    print()
    print("OAuth認証を使用するには、以下のSecretsを設定してください:")
    print()
    
    print("1. GOOGLE_OAUTH_CREDENTIALS")
    print("   - OAuth認証情報のBase64エンコード文字列")
    print("   - create_oauth_credentials() で生成された値を使用")
    print()
    
    print("2. PODCAST_BASE_URL")
    print("   - GitHub Pagesの公開URL")
    print("   - 例: https://your-username.github.io/auto-podcast")
    print()
    
    print("設定手順:")
    print("1. GitHubリポジトリ → Settings → Secrets and variables → Actions")
    print("2. 'New repository secret' をクリック")
    print("3. 上記のSecret名と値を入力")
    print("4. 'Add secret' をクリック")
    print()
    
    print("注意事項:")
    print("- OAuthは初回実行時に手動認証が必要です")
    print("- 認証後はセッション情報が自動保存されます")
    print("- CI/CD環境では事前に認証済みセッションが必要です")


def interactive_setup():
    """対話的セットアップ"""
    
    print("🔐 Google OAuth 認証セットアップ")
    print("=" * 50)
    print()
    
    while True:
        print("選択してください:")
        print("1. OAuth認証情報を作成")
        print("2. OAuth設定をテスト")
        print("3. GitHub Secrets設定ガイド")
        print("4. 終了")
        print()
        
        choice = input("選択 (1-4): ").strip()
        
        if choice == '1':
            create_oauth_credentials()
        elif choice == '2':
            test_oauth_setup()
        elif choice == '3':
            setup_github_secrets_guide()
        elif choice == '4':
            print("セットアップを終了します")
            break
        else:
            print("無効な選択です")
        
        print()
        input("Enterキーで続行...")
        print()


if __name__ == "__main__":
    interactive_setup()