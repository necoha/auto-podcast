"""
Notebook LMのAudio Overview機能を自動化するモジュール
Seleniumを使用してWebインターフェースを操作
"""

import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import config


class NotebookLMAutomator:
    def __init__(self):
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Chromeドライバーの設定"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # ヘッドレスモード
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
    
    def login_to_google(self):
        """Googleアカウントにログイン"""
        try:
            self.driver.get("https://accounts.google.com/signin")
            
            # メールアドレス入力
            email_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "identifierId"))
            )
            email_input.send_keys(config.GOOGLE_ACCOUNT_EMAIL)
            
            # 次へボタンクリック
            next_button = self.driver.find_element(By.ID, "identifierNext")
            next_button.click()
            
            # パスワード入力
            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_input.send_keys(config.GOOGLE_ACCOUNT_PASSWORD)
            
            # ログインボタンクリック
            login_button = self.driver.find_element(By.ID, "passwordNext")
            login_button.click()
            
            time.sleep(3)
            return True
            
        except Exception as e:
            print(f"ログインエラー: {e}")
            return False
    
    def create_notebook(self, title="Auto Podcast Notebook"):
        """新しいノートブックを作成"""
        try:
            self.driver.get(config.NOTEBOOKLM_URL)
            time.sleep(3)
            
            # 新しいノートブック作成ボタンを探してクリック
            new_notebook_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'New notebook') or contains(text(), '新しいノートブック')]"))
            )
            new_notebook_btn.click()
            
            # タイトル設定（可能であれば）
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"ノートブック作成エラー: {e}")
            return False
    
    def upload_content(self, content_text, file_path=None):
        """コンテンツをアップロード"""
        try:
            # ソース追加ボタンを探してクリック
            add_source_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add sources') or contains(text(), 'ソースを追加')]"))
            )
            add_source_btn.click()
            
            if file_path and os.path.exists(file_path):
                # ファイルアップロード
                file_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.INPUT, "[type='file']"))
                )
                file_input.send_keys(file_path)
            else:
                # テキスト入力（可能であれば）
                # NotebookLMのUIに応じて実装
                pass
            
            time.sleep(5)  # アップロード待機
            return True
            
        except Exception as e:
            print(f"コンテンツアップロードエラー: {e}")
            return False
    
    def generate_audio_overview(self, custom_prompt=None):
        """Audio Overviewを生成"""
        try:
            # Studioパネルを探す
            studio_panel = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'studio') or contains(text(), 'Studio')]"))
            )
            
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
            # ログイン
            if not self.login_to_google():
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
            print(f"音声生成フローエラー: {e}")
            return False
        finally:
            self.close()


# 使用例
if __name__ == "__main__":
    automator = NotebookLMAutomator()
    
    sample_content = """
    今日のテクノロジーニュース:
    1. AIの最新動向について
    2. 新しいプログラミング言語の発表
    3. クラウドサービスのアップデート
    """
    
    custom_prompt = "テクノロジーニュースについて、初心者にもわかりやすく、ポッドキャスト形式で解説してください。"
    
    success = automator.create_audio_from_content(
        content_text=sample_content,
        output_path="./audio_files/podcast_episode_001.mp3",
        custom_prompt=custom_prompt
    )
    
    if success:
        print("音声生成が完了しました！")
    else:
        print("音声生成に失敗しました。")