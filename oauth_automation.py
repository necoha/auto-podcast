"""
OAuth認証を使用したNotebook LM自動化
アプリパスワード不要、セキュアな認証方式
"""

import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
        # GitHub Actions環境でFirefoxフォールバックを使用
        if os.getenv('GITHUB_ACTIONS'):
            print("GitHub Actions環境: Firefox自動化を使用")
            try:
                from firefox_automation import FirefoxNotebookLMAutomator
                self.firefox_automator = FirefoxNotebookLMAutomator()
                self.driver = self.firefox_automator.driver
            except Exception as e:
                print(f"Firefox自動化初期化エラー: {e}")
                self.firefox_automator = None
        else:
            self.firefox_automator = None
            self.setup_driver()
    
    def setup_driver(self):
        """Chromeドライバーの設定"""
        chrome_options = Options()
        
        # GitHub Actions環境での設定
        if os.getenv('GITHUB_ACTIONS'):
            print("GitHub Actions環境用のChrome設定を適用中...")
            # Chrome/Chromiumバージョン検出とheadlessオプション設定
            try:
                import subprocess
                chrome_version = None
                chrome_command = None
                
                # Chrome or Chromium を検出
                for cmd in ['google-chrome', 'chromium-browser', 'chromium']:
                    try:
                        result = subprocess.run([cmd, '--version'], capture_output=True, text=True)
                        if result.returncode == 0:
                            chrome_version = result.stdout.strip()
                            chrome_command = cmd
                            print(f"検出されたブラウザ: {chrome_command} - {chrome_version}")
                            break
                    except:
                        continue
                
                if chrome_version:
                    # バージョン137以下またはChromiumの場合は古いheadlessオプション
                    if ('137.' in chrome_version or '136.' in chrome_version or 
                        '135.' in chrome_version or 'chromium' in chrome_command.lower()):
                        print("古いheadlessオプションを使用")
                        chrome_options.add_argument('--headless')  # 古い形式
                    else:
                        chrome_options.add_argument('--headless=new')  # 新しい形式
                else:
                    print("ブラウザバージョン検出失敗: デフォルトheadlessを使用")
                    chrome_options.add_argument('--headless')
            except:
                print("ブラウザ検出エラー: デフォルトheadlessを使用")
                chrome_options.add_argument('--headless')
                
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')
            # JavaScriptを有効化（Notebook LMには必要）
            # chrome_options.add_argument('--disable-javascript')  # コメントアウト
            chrome_options.add_argument('--virtual-time-budget=30000')  # 30秒に延長
            chrome_options.add_argument('--run-all-compositor-stages-before-draw')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--remote-debugging-port=9222')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--metrics-recording-only')
            chrome_options.add_argument('--mute-audio')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--safebrowsing-disable-auto-update')
            chrome_options.add_argument('--disable-component-update')
            chrome_options.add_argument('--disable-domain-reliability')
            # ウィンドウクラッシュ防止
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-features=Translate')
            chrome_options.add_argument('--disable-hang-monitor')
            chrome_options.add_argument('--disable-prompt-on-repost')
            chrome_options.add_argument('--disable-client-side-phishing-detection')
            # 追加の安定性オプション
            chrome_options.add_argument('--disable-background-mode')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-permissions-api')
            chrome_options.add_argument('--disable-device-discovery-notifications')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-save-password-bubble')
            chrome_options.add_argument('--disable-translate')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-logging')
            chrome_options.add_argument('--silent')
            chrome_options.add_argument('--log-level=3')  # エラーのみ
            chrome_options.add_argument('--disable-features=VizDisplayCompositor,VizServiceDisplay')
            # メモリ制限を設定
            chrome_options.add_argument('--max-old-space-size=2048')
            chrome_options.add_argument('--memory-pressure-off')
            # 追加の軽量化オプション
            chrome_options.add_argument('--single-process')
            chrome_options.add_argument('--no-zygote')
            chrome_options.add_argument('--disable-gpu-sandbox')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-features=TranslateUI,VizDisplayCompositor')
            chrome_options.add_argument('--force-color-profile=srgb')
            chrome_options.add_argument('--disable-threaded-animation')
            chrome_options.add_argument('--disable-threaded-scrolling')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            # メモリとプロセスの制限
            chrome_options.add_argument('--max_old_space_size=512')
            chrome_options.add_argument('--optimize-for-size')
            # 不要なサービスを無効化
            chrome_options.add_argument('--disable-component-extensions')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--no-default-browser-check')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--disable-default-apps')
            
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # GitHub Actions環境ではユーザーデータディレクトリを無効化
        if not os.getenv('GITHUB_ACTIONS'):
            user_data_dir = os.path.abspath("chrome_oauth_profile")
            chrome_options.add_argument(f'--user-data-dir={user_data_dir}')
        
        try:
            if os.getenv('GITHUB_ACTIONS'):
                # GitHub Actions環境での改善されたChromeDriver設定
                print("GitHub Actions環境でのChromeDriverセットアップ")
                
                # ChromeDriverManagerでパスを取得
                chromedriver_path = ChromeDriverManager().install()
                print(f"ChromeDriverパス: {chromedriver_path}")
                
                # パスの検証と修正
                if 'THIRD_PARTY_NOTICES' in chromedriver_path or not os.access(chromedriver_path, os.X_OK):
                    print("ChromeDriverパスを修正中...")
                    # 正しいchromedriverファイルを探す
                    import glob
                    driver_dir = os.path.dirname(chromedriver_path)
                    root_dir = os.path.dirname(driver_dir)  # 上位ディレクトリも検索
                    
                    search_patterns = [
                        os.path.join(driver_dir, '**', 'chromedriver'),
                        os.path.join(root_dir, '**', 'chromedriver'),
                        os.path.join(driver_dir, 'chromedriver'),
                        os.path.join(root_dir, 'chromedriver'),
                    ]
                    
                    found_driver = None
                    for pattern in search_patterns:
                        possible_drivers = glob.glob(pattern, recursive=True)
                        for path in possible_drivers:
                            if (os.path.isfile(path) and 
                                'THIRD_PARTY_NOTICES' not in path and 
                                'chromedriver' in os.path.basename(path).lower()):
                                # 実行権限を設定
                                try:
                                    import stat
                                    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
                                    if os.access(path, os.X_OK):
                                        found_driver = path
                                        break
                                except:
                                    continue
                        if found_driver:
                            break
                    
                    if found_driver:
                        chromedriver_path = found_driver
                        print(f"修正されたChromeDriverパス: {chromedriver_path}")
                    else:
                        print("有効なChromeDriverが見つかりませんでした")
                
                # 実行権限を確認・設定
                if os.path.exists(chromedriver_path):
                    import stat
                    current_permissions = os.stat(chromedriver_path).st_mode
                    os.chmod(chromedriver_path, current_permissions | stat.S_IEXEC)
                    print(f"ChromeDriver実行権限設定完了: {oct(os.stat(chromedriver_path).st_mode)}")
                
                service = Service(chromedriver_path)
            else:
                # ローカル環境
                service = Service(ChromeDriverManager(path="/tmp").install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("ChromeDriver初期化成功")
            
            # ドライバー動作確認
            try:
                # 基本的な動作テスト
                print("ドライバー動作テスト中...")
                test_url = "data:text/html,<html><body><h1>Test Page</h1></body></html>"
                self.driver.get(test_url)
                time.sleep(2)
                
                # ページタイトル確認
                if self.driver.title:
                    print(f"ドライバーテスト成功: {self.driver.title}")
                else:
                    print("ドライバーテスト: タイトル取得成功")
                
                # GitHub Actions環境ではWebDriver検出回避をスキップ
                if not os.getenv('GITHUB_ACTIONS'):
                    # WebDriver検出回避（ローカルのみ）
                    self.driver.execute_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                    )
                    print("WebDriver検出回避を適用")
                
            except Exception as test_error:
                print(f"ドライバー動作テストエラー: {test_error}")
                # テストに失敗してもメインの処理は続行
            
        except Exception as e:
            print(f"ChromeDriver設定エラー: {e}")
            # フォールバック: システムのChromeDriverを使用
            try:
                print("システムChromeDrawerを試行中...")
                # 複数の可能なパスを試行
                possible_paths = [
                    "/usr/bin/chromedriver", 
                    "/usr/local/bin/chromedriver",
                    "/snap/bin/chromium.chromedriver"
                ]
                
                for path in possible_paths:
                    if os.path.exists(path) and os.access(path, os.X_OK):
                        print(f"システムChromeDriver使用: {path}")
                        service = Service(path)
                        self.driver = webdriver.Chrome(service=service, options=chrome_options)
                        print("システムChromeDriver初期化成功")
                        return
                
                raise Exception("利用可能なChromeDriverが見つかりません")
                
            except Exception as e2:
                print(f"フォールバックも失敗: {e2}")
                
                # 最終手段：Chrome自体の問題をチェック
                try:
                    import subprocess
                    result = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
                    print(f"Chrome version: {result.stdout}")
                except:
                    print("Google Chromeが正しくインストールされていない可能性があります")
                
                raise Exception("ChromeDriverの初期化に失敗しました")
    
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
        """CI環境用の認証テスト"""
        try:
            print("CI環境: Notebook LMアクセステスト開始...")
            
            # ドライバーが初期化されているかチェック
            if not self.driver:
                print("ドライバーが初期化されていません - セットアップを試行")
                self.setup_driver()
            
            # Notebook LMに段階的にアクセス
            print("Notebook LMにアクセス中...")
            
            # まずGoogleのホームページでセッション確認
            try:
                print("1. Googleホームページをテスト...")
                self.driver.get("https://www.google.com")
                time.sleep(5)
                
                google_title = self.driver.title
                print(f"Googleページタイトル: {google_title}")
                
                if not google_title or "Google" not in google_title:
                    print("⚠️ Googleページの読み込みに問題があります")
                    return False
                
            except Exception as e:
                print(f"Googleページアクセスエラー: {e}")
                return False
            
            # 次にNotebook LMにアクセス
            try:
                print("2. Notebook LMページにアクセス...")
                self.driver.get("https://notebooklm.google.com")
                
                # 段階的な待機とチェック
                for i in range(6):
                    time.sleep(5)
                    try:
                        current_url = self.driver.current_url
                        page_title = self.driver.title or "No Title"
                        
                        print(f"  {i+1}/6 - URL: {current_url}")
                        print(f"  {i+1}/6 - Title: {page_title}")
                        
                        # ページが完全に読み込まれたかのチェック
                        if "notebooklm" in current_url.lower():
                            print("✅ Notebook LMページに到達")
                            break
                        elif "accounts.google.com" in current_url:
                            print("🔐 Googleログインページにリダイレクト")
                            break
                        elif current_url != "data:,":  # about:blankではない
                            print(f"🔄 ページ読み込み中... ({current_url})")
                        
                    except Exception as e:
                        print(f"  {i+1}/6 - ページ状態取得エラー: {e}")
                        continue
                
                # 最終的なページ状態を確認
                final_url = self.driver.current_url
                final_title = self.driver.title or "No Title"
                
                print(f"最終URL: {final_url}")
                print(f"最終タイトル: {final_title}")
                
                # ページソースの一部を確認（安全に）
                try:
                    page_source = self.driver.page_source
                    if page_source:
                        page_source_preview = page_source[:500]
                        print(f"ページソース（最初の500文字）: {page_source_preview}")
                    else:
                        print("ページソースが空です")
                except:
                    print("ページソース取得に失敗")
                
            except Exception as e:
                print(f"Notebook LMアクセスエラー: {e}")
                return False
            
            # アクセス可能かどうかの基本判定
            if "notebooklm" in final_url.lower() or "notebooklm" in final_title.lower():
                print("✅ Notebook LMへのアクセス成功")
                
                # ログイン状態をチェック
                if self.check_login_status():
                    print("✅ 認証済み状態を検出")
                    return True
                else:
                    print("⚠️ 未認証状態 - 認証が必要")
                    return self.attempt_ci_authentication()
            else:
                print("❌ Notebook LMへのアクセス失敗")
                return False
            
        except Exception as e:
            print(f"CI環境認証テストエラー: {e}")
            import traceback
            print(f"詳細エラー: {traceback.format_exc()}")
            return False
    
    def check_login_status(self):
        """ログイン状態をチェック"""
        try:
            # ログイン画面の要素があるかチェック
            login_indicators = [
                "//input[@type='email']",
                "//input[@type='password']", 
                "//button[contains(text(), 'Sign in')]",
                "//button[contains(text(), 'ログイン')]",
                "//*[contains(text(), 'Sign in to continue')]"
            ]
            
            for indicator in login_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements:
                        print(f"ログイン要素を検出: {indicator}")
                        return False
                except:
                    continue
            
            # ログイン済みの場合によく表示される要素をチェック
            authenticated_indicators = [
                "//button[contains(text(), 'New notebook')]",
                "//button[contains(text(), '新しいノートブック')]",
                "//*[contains(@class, 'notebook')]",
                "//*[contains(text(), 'Create')]"
            ]
            
            for indicator in authenticated_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements:
                        print(f"認証済み要素を検出: {indicator}")
                        return True
                except:
                    continue
            
            print("ログイン状態が不明確")
            return False
            
        except Exception as e:
            print(f"ログイン状態チェックエラー: {e}")
            return False
    
    def attempt_ci_authentication(self):
        """CI環境での認証試行"""
        try:
            print("CI環境での認証を試行中...")
            
            # GitHub Secretsから認証情報を取得
            oauth_creds = self.load_oauth_credentials()
            if not oauth_creds:
                print("OAuth認証情報が見つかりません")
                return False
            
            # 保存されたセッション情報があるかチェック
            session_data = os.getenv('OAUTH_SESSION_DATA')
            if session_data:
                print("保存されたセッション情報を使用して認証試行...")
                return self.restore_ci_session(session_data)
            
            print("CI環境では自動認証は困難です")
            return False
            
        except Exception as e:
            print(f"CI認証試行エラー: {e}")
            return False
    
    def restore_ci_session(self, session_data_encoded):
        """CI環境でセッション情報を復元"""
        try:
            import base64
            session_json = base64.b64decode(session_data_encoded).decode()
            session_data = json.loads(session_json)
            
            print("セッション情報を復元中...")
            
            # Cookieを復元
            for cookie in session_data.get('cookies', []):
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    print(f"Cookie復元警告: {e}")
            
            # ページを再読み込み
            self.driver.refresh()
            time.sleep(5)
            
            # 認証状態を再確認
            return self.check_login_status()
            
        except Exception as e:
            print(f"CI セッション復元エラー: {e}")
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
            try:
                self.driver.quit()
            except:
                pass  # CI環境では既に閉じている可能性がある
    
    def create_audio_from_content(self, content_text, output_path, custom_prompt=None):
        """コンテンツから音声を生成する完全なフロー"""
        try:            
            # CI環境でのテストモード判定
            if os.getenv('GITHUB_ACTIONS') and os.getenv('SKIP_REAL_GENERATION', 'true') == 'true':
                print("CI環境: テストモードのためモック音声を生成")
                return self.create_mock_audio(content_text, output_path)
            
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
            if not os.getenv('GITHUB_ACTIONS'):
                self.close()
    
    def create_audio_from_url(self, source_url, output_path, custom_prompt=None):
        """URLから直接Audio Overviewを生成"""
        try:
            # GitHub Actions環境でFirefox自動化を使用
            if os.getenv('GITHUB_ACTIONS') and self.firefox_automator:
                print("GitHub Actions環境: Firefox自動化を使用してURL音声生成")
                return self.firefox_automator.create_audio_from_url(source_url, output_path, custom_prompt)
            
            # CI環境でのテストモード判定
            if os.getenv('GITHUB_ACTIONS') and os.getenv('SKIP_REAL_GENERATION', 'true') == 'true':
                print("CI環境: テストモードのためモック音声を生成")
                return self.create_mock_audio(source_url, output_path)
            
            print(f"URL音声生成開始: {source_url}")
            
            # OAuth認証
            if not self.oauth_login():
                return False
            
            # 新しいノートブック作成
            if not self.create_notebook():
                return False
            
            # URLをソースとして追加
            if not self.add_url_source(source_url):
                return False
            
            # Audio Overview生成
            if not self.generate_audio_overview(custom_prompt):
                return False
            
            # 音声ダウンロード
            if not self.download_audio(output_path):
                return False
            
            print(f"URL音声生成完了: {output_path}")
            return True
            
        except Exception as e:
            print(f"URL音声生成エラー: {e}")
            return False
        finally:
            if not os.getenv('GITHUB_ACTIONS'):
                self.close()
    
    def add_url_source(self, source_url):
        """ノートブックにURLソースを追加"""
        try:
            print(f"URLソース追加: {source_url}")
            
            # "Add source" ボタンを探す
            add_source_selectors = [
                "[data-testid='add-source']",
                "button[aria-label*='Add source']",
                "button:contains('Add source')",
                ".add-source-button",
                "[class*='add-source']"
            ]
            
            add_source_btn = None
            for selector in add_source_selectors:
                try:
                    add_source_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
            
            if not add_source_btn:
                # 代替方法：+ボタンやAddボタンを探す
                possible_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for btn in possible_buttons:
                    if any(keyword in btn.text.lower() for keyword in ['add', 'source', '+', 'upload']):
                        add_source_btn = btn
                        break
            
            if not add_source_btn:
                print("Add sourceボタンが見つかりません")
                return False
            
            add_source_btn.click()
            time.sleep(2)
            
            # URL入力フィールドを探す
            url_input_selectors = [
                "input[placeholder*='URL']",
                "input[placeholder*='url']",
                "input[placeholder*='link']",
                "input[type='url']",
                "input[name*='url']"
            ]
            
            url_input = None
            for selector in url_input_selectors:
                try:
                    url_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if not url_input:
                print("URL入力フィールドが見つかりません")
                return False
            
            # URLを入力
            url_input.clear()
            url_input.send_keys(source_url)
            url_input.send_keys(Keys.RETURN)
            
            # ソース処理完了を待機
            print("ソース処理を待機中...")
            try:
                # 処理完了の指標を複数パターンで待機
                WebDriverWait(self.driver, 60).until(
                    lambda driver: any([
                        len(driver.find_elements(By.CSS_SELECTOR, "[data-testid='source-processed']")) > 0,
                        len(driver.find_elements(By.CSS_SELECTOR, ".source-ready")) > 0,
                        len(driver.find_elements(By.CSS_SELECTOR, "[class*='processed']")) > 0,
                        "processed" in driver.page_source.lower(),
                        "ready" in driver.page_source.lower()
                    ])
                )
                print("ソース処理完了")
                return True
                
            except:
                print("ソース処理完了の確認タイムアウト - 継続")
                time.sleep(10)  # 追加待機
                return True
            
        except Exception as e:
            print(f"URLソース追加エラー: {e}")
            return False
    
    def create_mock_audio(self, content_text, output_path):
        """CI環境用のモック音声ファイル生成"""
        try:
            print("CI環境: モック音声ファイルを生成中...")
            
            # 簡単なバイナリファイルを作成（MP3ヘッダー付き）
            # MP3の最小ヘッダー
            mp3_header = b'\xff\xfb\x90\x00'  # MP3フレームヘッダー
            silence_data = b'\x00' * 1024  # サイレンスデータ
            
            with open(output_path, 'wb') as f:
                f.write(mp3_header)
                # 1分間分のサイレンスデータを書き込み（約2MB）
                for _ in range(2048):
                    f.write(silence_data)
            
            print(f"モック音声ファイル生成完了: {output_path}")
            return True
            
        except Exception as e:
            print(f"モック音声生成エラー: {e}")
            # 最終手段：メタデータファイルを作成
            try:
                with open(output_path.replace('.mp3', '.txt'), 'w', encoding='utf-8') as f:
                    f.write(f"# CI環境用モックポッドキャスト\n")
                    f.write(f"生成日時: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"コンテンツ要約: {content_text[:200]}...\n")
                print(f"メタデータファイル生成: {output_path.replace('.mp3', '.txt')}")
                
                # 空のMP3ファイルも作成
                with open(output_path, 'wb') as f:
                    f.write(b'\xff\xfb\x90\x00' + b'\x00' * 100)
                return True
            except:
                return False


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