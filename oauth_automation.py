"""
OAuth認証を使用したNotebook LM自動化
アプリパスワード不要、セキュアな認証方式
"""

import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import base64
import config


class OAuthNotebookLMAutomator:
    def __init__(self):
        self.driver = None
        self.oauth_token = None
        self.setup_driver()
    
    def setup_driver(self):
        """Chromeドライバーの設定"""
        chrome_options = Options()
        
        # GitHub Actions環境での設定
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--remote-debugging-port=9222')
            
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # GitHub Actions環境ではユーザーデータディレクトリを無効化
        if not os.getenv('GITHUB_ACTIONS'):
            user_data_dir = os.path.abspath("chrome_oauth_profile")
            chrome_options.add_argument(f'--user-data-dir={user_data_dir}')
        
        try:
            # ChromeDriverManagerの設定を改善
            if os.getenv('GITHUB_ACTIONS'):
                # GitHub Actions環境では最新バージョンを使用
                service = Service(ChromeDriverManager().install())
            else:
                # ローカル環境では特定パスを指定
                service = Service(ChromeDriverManager(path="/tmp").install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"ChromeDriver設定エラー: {e}")
            # フォールバック: システムのChromeDriverを使用
            try:
                service = Service("/usr/bin/chromedriver")
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e2:
                print(f"フォールバックも失敗: {e2}")
                raise Exception("ChromeDriverの初期化に失敗しました")
        
        # WebDriver検出回避
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    
    def load_oauth_credentials(self):
        """OAuth認証情報を読み込み"""
        # GitHub Secretsから読み込み
        oauth_data = os.getenv('GOOGLE_OAUTH_CREDENTIALS')
        if oauth_data:
            try:
                decoded_data = base64.b64decode(oauth_data).decode()
                return json.loads(decoded_data)
            except Exception as e:
                print(f"OAuth認証情報デコードエラー: {e}")
                return None
        
        # ローカルファイルから読み込み
        oauth_file = 'google_oauth_credentials.json'
        if os.path.exists(oauth_file):
            try:
                with open(oauth_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"ローカルOAuth認証情報読み込みエラー: {e}")
                return None
        
        return None
    
    def oauth_login(self):
        """OAuth認証でGoogleにログイン"""
        try:
            # GitHub Actions環境では直接NotebookLMにアクセス
            if os.getenv('GITHUB_ACTIONS'):
                print("GitHub Actions環境: 事前設定された認証を使用")
                return self.ci_login()
            
            # 保存された認証情報があるかチェック
            if self.restore_oauth_session():
                print("保存されたOAuth セッションでログイン成功")
                return True
            
            print("新しいOAuth認証を開始...")
            
            # Google OAuth認証画面へ
            oauth_url = self.build_oauth_url()
            self.driver.get(oauth_url)
            
            print("ブラウザでGoogleアカウント認証を完了してください...")
            print("認証完了後、Enter キーを押してください")
            input("Press Enter after OAuth authorization...")
            
            # 認証後のCallbackを処理
            return self.handle_oauth_callback()
            
        except Exception as e:
            print(f"OAuth認証エラー: {e}")
            return False
    
    def ci_login(self):
        """CI環境用の簡単ログイン"""
        try:
            # NotebookLMに直接アクセス
            self.driver.get("https://notebooklm.google.com")
            time.sleep(10)
            
            # CI環境では認証なしで進行（デモモード）
            print("CI環境: デモモードで実行")
            return True
            
        except Exception as e:
            print(f"CI環境ログインエラー: {e}")
            return False
    
    def build_oauth_url(self):
        """Google OAuth認証URLを構築"""
        oauth_creds = self.load_oauth_credentials()
        
        if not oauth_creds:
            # デフォルトのOAuth設定（実際のプロジェクトでは適切な値を設定）
            client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID', 'your-client-id')
            redirect_uri = 'http://localhost:8080/oauth/callback'
        else:
            client_id = oauth_creds['client_id']
            redirect_uri = oauth_creds.get('redirect_uri', 'http://localhost:8080/oauth/callback')
        
        scope = 'https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile'
        
        oauth_url = (
            f"https://accounts.google.com/oauth/authorize?"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"scope={scope}&"
            f"response_type=code&"
            f"access_type=offline&"
            f"prompt=consent"
        )
        
        return oauth_url
    
    def handle_oauth_callback(self):
        """OAuth認証後のコールバック処理"""
        try:
            # 認証成功を待機
            WebDriverWait(self.driver, 300).until(
                lambda driver: "accounts.google.com" not in driver.current_url
            )
            
            # セッション情報を保存
            self.save_oauth_session()
            
            # NotebookLMにアクセス
            self.driver.get("https://notebooklm.google.com")
            time.sleep(5)
            
            # ログイン成功確認
            if "notebooklm" in self.driver.current_url.lower():
                print("OAuth認証とNotebookLMアクセス成功")
                return True
            else:
                print("NotebookLMアクセス失敗")
                return False
                
        except Exception as e:
            print(f"OAuthコールバック処理エラー: {e}")
            return False
    
    def save_oauth_session(self):
        """OAuth認証セッションを保存"""
        try:
            # Cookieとセッション情報を保存
            cookies = self.driver.get_cookies()
            local_storage = self.driver.execute_script("return window.localStorage;")
            session_storage = self.driver.execute_script("return window.sessionStorage;")
            
            session_data = {
                'cookies': cookies,
                'local_storage': local_storage,
                'session_storage': session_storage,
                'current_url': self.driver.current_url,
                'timestamp': time.time()
            }
            
            # ローカルファイルに保存
            with open('oauth_session.json', 'w') as f:
                json.dump(session_data, f)
            
            print("OAuth セッション情報を保存しました")
            
        except Exception as e:
            print(f"OAuth セッション保存エラー: {e}")
    
    def restore_oauth_session(self):
        """保存されたOAuth認証セッションを復元"""
        try:
            session_file = 'oauth_session.json'
            if not os.path.exists(session_file):
                return False
            
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            # セッションの有効期限チェック（24時間）
            if time.time() - session_data.get('timestamp', 0) > 86400:
                print("保存されたOAuthセッションが期限切れです")
                return False
            
            # Googleにアクセス
            self.driver.get("https://google.com")
            time.sleep(2)
            
            # Cookieを復元
            for cookie in session_data.get('cookies', []):
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    print(f"Cookie復元警告: {e}")
            
            # ローカルストレージを復元
            for key, value in session_data.get('local_storage', {}).items():
                try:
                    self.driver.execute_script(
                        f"window.localStorage.setItem('{key}', '{value}');"
                    )
                except Exception as e:
                    print(f"LocalStorage復元警告: {e}")
            
            # NotebookLMアクセステスト
            self.driver.get("https://notebooklm.google.com")
            time.sleep(5)
            
            # ログイン状態確認
            if "notebooklm" in self.driver.current_url.lower():
                # ログイン画面が表示されていないかチェック
                try:
                    login_elements = self.driver.find_elements(By.XPATH, "//input[@type='email'] | //input[@type='password']")
                    if login_elements:
                        print("ログイン画面が表示されています - セッション無効")
                        return False
                except:
                    pass
                
                print("OAuth セッション復元成功")
                return True
            else:
                print("OAuth セッション復元失敗")
                return False
                
        except Exception as e:
            print(f"OAuth セッション復元エラー: {e}")
            return False
    
    def create_notebook(self, title="Auto Podcast Notebook"):
        """新しいノートブックを作成"""
        try:
            # 新しいノートブック作成ボタンを探してクリック
            new_notebook_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'New notebook') or contains(text(), '新しいノートブック')]"))
            )
            new_notebook_btn.click()
            
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"ノートブック作成エラー: {e}")
            return False
    
    def upload_content(self, content_text):
        """コンテンツをアップロード"""
        try:
            # テキストコンテンツを一時ファイルとして保存
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(content_text)
                temp_file_path = temp_file.name
            
            # ソース追加ボタンを探してクリック
            add_source_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add sources') or contains(text(), 'ソースを追加')]"))
            )
            add_source_btn.click()
            
            # ファイルアップロード
            file_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            file_input.send_keys(temp_file_path)
            
            time.sleep(5)  # アップロード待機
            
            # 一時ファイル削除
            os.unlink(temp_file_path)
            
            return True
            
        except Exception as e:
            print(f"コンテンツアップロードエラー: {e}")
            return False
    
    def generate_audio_overview(self, custom_prompt=None):
        """Audio Overviewを生成"""
        try:
            # Audio Overviewボタンを探してクリック
            audio_overview_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Audio Overview') or contains(text(), '音声概要')]"))
            )
            audio_overview_btn.click()
            
            # カスタムプロンプトがある場合
            if custom_prompt:
                try:
                    customize_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Customize')]")
                    customize_btn.click()
                    
                    prompt_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.TAG_NAME, "textarea"))
                    )
                    prompt_input.clear()
                    prompt_input.send_keys(custom_prompt)
                except:
                    pass  # カスタマイズが利用できない場合はスキップ
            
            # 生成ボタンクリック
            generate_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Generate') or contains(text(), '生成')]"))
            )
            generate_btn.click()
            
            # 生成完了を待機（最大5分）
            WebDriverWait(self.driver, 300).until(
                EC.presence_of_element_located((By.XPATH, "//audio | //button[contains(text(), 'Download') or contains(text(), 'ダウンロード')]"))
            )
            
            return True
            
        except Exception as e:
            print(f"Audio Overview生成エラー: {e}")
            return False
    
    def download_audio(self, output_path):
        """生成された音声ファイルをダウンロード"""
        try:
            # ダウンロードボタンを探してクリック
            download_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Download') or contains(text(), 'ダウンロード')] | //a[contains(@href, '.mp3')]"))
            )
            download_btn.click()
            
            time.sleep(10)  # ダウンロード完了待機
            
            # ダウンロードフォルダから最新のmp3ファイルを取得して移動
            downloads_path = os.path.expanduser("~/Downloads")
            mp3_files = [f for f in os.listdir(downloads_path) if f.endswith('.mp3')]
            
            if mp3_files:
                latest_file = max([os.path.join(downloads_path, f) for f in mp3_files], 
                                key=os.path.getctime)
                
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                os.rename(latest_file, output_path)
                return True
            
            return False
            
        except Exception as e:
            print(f"音声ダウンロードエラー: {e}")
            return False
    
    def close(self):
        """ドライバーを閉じる"""
        if self.driver:
            self.driver.quit()
    
    def create_audio_from_content(self, content_text, output_path, custom_prompt=None):
        """コンテンツから音声を生成する完全なフロー"""
        try:
            # OAuth認証
            if not self.oauth_login():
                return False
            
            # ノートブック作成
            if not self.create_notebook():
                return False
            
            # コンテンツアップロード
            if not self.upload_content(content_text):
                return False
            
            # Audio Overview生成
            if not self.generate_audio_overview(custom_prompt):
                return False
            
            # 音声ダウンロード
            if not self.download_audio(output_path):
                return False
            
            return True
            
        except Exception as e:
            print(f"OAuth音声生成フローエラー: {e}")
            return False
        finally:
            self.close()


# 使用例
if __name__ == "__main__":
    automator = OAuthNotebookLMAutomator()
    
    sample_content = """
    今日のテクノロジーニュース:
    1. AIの最新動向について
    2. 新しいプログラミング言語の発表
    3. クラウドサービスのアップデート
    """
    
    custom_prompt = "テクノロジーニュースについて、初心者にもわかりやすく、ポッドキャスト形式で解説してください。"
    
    success = automator.create_audio_from_content(
        content_text=sample_content,
        output_path="./audio_files/oauth_podcast_episode_001.mp3",
        custom_prompt=custom_prompt
    )
    
    if success:
        print("OAuth認証による音声生成が完了しました！")
    else:
        print("OAuth認証による音声生成に失敗しました。")