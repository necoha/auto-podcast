"""
GitHub Actions用の認証セットアップ
ローカルで認証情報を生成してSecretsに保存
"""

import json
import base64
import os
from auth_helper import GoogleAuthHelper


def setup_github_auth():
    """GitHub Actions用の認証情報を準備"""
    print("=== GitHub Actions用認証セットアップ ===")
    
    auth_helper = GoogleAuthHelper()
    
    # Step 1: ローカルで手動認証
    print("\nStep 1: ローカル認証")
    if not os.path.exists("google_session.json"):
        print("ブラウザが開きます。Googleアカウントでログインしてください。")
        auth_helper.interactive_login_once()
    else:
        print("既存の認証情報を使用します。")
    
    # Step 2: 認証情報をBase64エンコード
    print("\nStep 2: 認証情報エンコード")
    with open("google_session.json", 'r') as f:
        session_data = f.read()
    
    encoded_session = base64.b64encode(session_data.encode()).decode()
    
    # Step 3: GitHub Secrets設定指示
    print("\n=== GitHub Secrets設定 ===")
    print("以下の値をGitHub Secretsに設定してください:")
    print("\n1. Secret名: GOOGLE_SESSION_DATA")
    print("   値:")
    print(f"   {encoded_session}")
    
    print(f"\n2. Secret名: PODCAST_BASE_URL")
    print(f"   値: https://necoha.github.io/auto-podcast")
    
    # Step 4: セットアップ確認用ファイル作成
    setup_info = {
        "setup_completed": True,
        "auth_method": "session_cookies",
        "requires_secrets": ["GOOGLE_SESSION_DATA", "PODCAST_BASE_URL"]
    }
    
    with open("auth_setup_info.json", 'w') as f:
        json.dump(setup_info, f, indent=2)
    
    print("\n✅ セットアップ完了!")
    print("認証情報は google_session.json に保存されました。")
    print("この情報を絶対に公開リポジトリにcommitしないでください。")


if __name__ == "__main__":
    setup_github_auth()