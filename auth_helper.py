"""
Google認証の代替方法
アプリパスワード不要でNotebook LMにアクセス
"""

import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


class GoogleAuthHelper:
    def __init__(self):
        self.session_file = "google_session.json"
        self.driver = None
    
    def setup_persistent_session(self):
        """永続化セッションでChrome設定"""
        chrome_options = Options()
        
        # 本番環境では必要に応じてヘッドレス化
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # ユーザーデータディレクトリを設定（セッション永続化）
        user_data_dir = os.path.abspath("chrome_user_data")
        chrome_options.add_argument(f'--user-data-dir={user_data_dir}')
        chrome_options.add_argument('--profile-directory=Default')
        
        # User-Agentを通常のものに変更
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # WebDriverの自動化検出を回避
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return self.driver
    
    def interactive_login_once(self):
        """
        一度だけ手動ログインしてセッションを保存
        CI/CDでは事前にローカルで実行してセッション情報をSecretに保存
        """
        print("Google認証を開始します...")
        print("ブラウザが開くので手動でログインしてください")
        
        self.setup_persistent_session()
        
        # Google認証画面へ
        self.driver.get("https://accounts.google.com/signin")
        
        # 手動ログイン待機
        print("ブラウザでGoogleアカウントにログインしてください...")
        print("ログイン完了後、何かキーを押してください")
        input("Press Enter after login...")
        
        # NotebookLMアクセステスト
        self.driver.get("https://notebooklm.google.com")
        time.sleep(5)
        
        # セッション情報を保存
        self.save_session_info()
        
        print("認証情報を保存しました")
        self.driver.quit()
    
    def save_session_info(self):
        """認証セッション情報を保存"""
        cookies = self.driver.get_cookies()
        session_data = {
            'cookies': cookies,
            'user_agent': self.driver.execute_script("return navigator.userAgent;")
        }
        
        with open(self.session_file, 'w') as f:
            json.dump(session_data, f)
    
    def load_session_info(self):
        """保存された認証情報を読み込み"""
        try:
            with open(self.session_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
    
    def create_authenticated_driver(self):
        """認証済みドライバーを作成"""
        session_data = self.load_session_info()
        
        if not session_data:
            raise Exception("認証情報が見つかりません。先に interactive_login_once() を実行してください")
        
        driver = self.setup_persistent_session()
        
        # Google.comにアクセスしてCookieを設定
        driver.get("https://google.com")
        
        # 保存されたCookieを復元
        for cookie in session_data['cookies']:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"Cookie設定エラー: {e}")
        
        # NotebookLMにアクセス
        driver.get("https://notebooklm.google.com")
        time.sleep(3)
        
        return driver


# 使用方法
if __name__ == "__main__":
    auth_helper = GoogleAuthHelper()
    
    # 初回のみ実行（ローカル環境で）
    if not os.path.exists("google_session.json"):
        print("初回認証を開始します...")
        auth_helper.interactive_login_once()
    
    # 認証済みドライバーでNotebook LMにアクセス
    driver = auth_helper.create_authenticated_driver()
    print("NotebookLMにアクセス成功!")
    driver.quit()