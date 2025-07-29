#!/usr/bin/env python3
"""
Chrome WebDriver 詳細ログ収集
--enable-logging と --verbose を使用した詳細デバッグ
"""

import os
import sys
import time
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions

def test_chrome_with_verbose_logging():
    """詳細ログ付きでChromeをテスト"""
    print("=== Chrome 詳細ログテスト ===")
    
    # ログファイル準備
    log_dir = tempfile.mkdtemp()
    chrome_log_file = os.path.join(log_dir, 'chrome_debug.log')
    chromedriver_log_file = os.path.join(log_dir, 'chromedriver_debug.log')
    
    print(f"ログディレクトリ: {log_dir}")
    print(f"Chrome ログ: {chrome_log_file}")
    print(f"ChromeDriver ログ: {chromedriver_log_file}")
    
    # Chrome設定
    chrome_options = ChromeOptions()
    
    if os.getenv('GITHUB_ACTIONS'):
        # CI環境: 最小構成 + 詳細ログ
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
    
    # 詳細ログ設定
    chrome_options.add_argument('--enable-logging')
    chrome_options.add_argument(f'--log-file={chrome_log_file}')
    chrome_options.add_argument('--log-level=0')  # 最詳細
    chrome_options.add_argument('--v=1')  # Verbose level
    chrome_options.add_argument('--vmodule=*=3')  # モジュール別詳細レベル
    
    # ChromeDriverサービス（詳細ログ付き）
    chromedriver_path = '/usr/local/bin/chromedriver'
    if os.getenv('GITHUB_ACTIONS') and os.path.exists(chromedriver_path):
        service = ChromeService(
            chromedriver_path,
            log_output=chromedriver_log_file
        )
        # サービス引数に--verboseを追加
        service.service_args = ['--verbose', '--log-path=' + chromedriver_log_file]
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = ChromeService(
            ChromeDriverManager().install(),
            log_output=chromedriver_log_file
        )
        service.service_args = ['--verbose', '--log-path=' + chromedriver_log_file]
    
    driver = None
    try:
        print("\n詳細ログ付きChrome起動中...")
        start_time = time.time()
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        init_time = time.time() - start_time
        print(f"Chrome起動時間: {init_time:.2f}秒")
        
        # 基本テスト
        print("基本テスト実行中...")
        driver.get("data:text/html,<html><body><h1>Verbose Test</h1><p>Detail logging test</p></body></html>")
        time.sleep(3)
        
        title = driver.title
        current_url = driver.current_url
        page_source = driver.page_source
        
        print(f"タイトル: {title}")
        print(f"URL: {current_url}")
        print(f"ページソース長: {len(page_source)}")
        
        if "Verbose Test" in page_source:
            print("✅ 詳細ログテスト成功")
            success = True
        else:
            print("❌ ページ内容に問題")
            success = False
            
    except Exception as e:
        print(f"❌ 詳細ログテスト失敗: {e}")
        print(f"エラータイプ: {type(e).__name__}")
        import traceback
        print(f"スタックトレス:\n{traceback.format_exc()}")
        success = False
        
    finally:
        if driver:
            try:
                driver.quit()
                print("Chrome正常終了")
            except Exception as e:
                print(f"Chrome終了エラー: {e}")
        
        # ログファイル内容を表示
        print("\n" + "=" * 60)
        print("Chrome ログファイル内容:")
        print("=" * 60)
        
        try:
            if os.path.exists(chrome_log_file):
                with open(chrome_log_file, 'r') as f:
                    chrome_log_content = f.read()
                if chrome_log_content.strip():
                    print(chrome_log_content[-2000:])  # 最後の2000文字
                else:
                    print("Chrome ログファイルは空です")
            else:
                print("Chrome ログファイルが作成されませんでした")
        except Exception as e:
            print(f"Chrome ログ読み取りエラー: {e}")
        
        print("\n" + "=" * 60)
        print("ChromeDriver ログファイル内容:")
        print("=" * 60)
        
        try:
            if os.path.exists(chromedriver_log_file):
                with open(chromedriver_log_file, 'r') as f:
                    chromedriver_log_content = f.read()
                if chromedriver_log_content.strip():
                    print(chromedriver_log_content[-2000:])  # 最後の2000文字
                else:
                    print("ChromeDriver ログファイルは空です")
            else:
                print("ChromeDriver ログファイルが作成されませんでした")
        except Exception as e:
            print(f"ChromeDriver ログ読み取りエラー: {e}")
    
    return success

def check_chrome_process_behavior():
    """Chrome プロセスの動作を詳細確認"""
    print("\n" + "=" * 60)
    print("Chrome プロセス動作解析")
    print("=" * 60)
    
    import subprocess
    
    try:
        # Chrome起動前のプロセス状況
        print("Chrome起動前のプロセス状況:")
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        chrome_before = [line for line in result.stdout.split('\n') if 'chrome' in line.lower()]
        print(f"既存Chrome関連プロセス: {len(chrome_before)}個")
        
        # メモリ使用量
        result = subprocess.run(['free', '-m'], capture_output=True, text=True)
        print(f"メモリ状況:\n{result.stdout}")
        
        # Chrome単体実行テスト
        print("\nChrome単体実行テスト:")
        chrome_cmd = [
            'google-chrome',
            '--headless',
            '--disable-dev-shm-usage', 
            '--no-sandbox',
            '--dump-dom',
            'data:text/html,<html><body>Direct Chrome Test</body></html>'
        ]
        
        result = subprocess.run(chrome_cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Chrome単体実行成功")
            if "Direct Chrome Test" in result.stdout:
                print("✅ Chrome単体でページ処理成功")
            else:
                print("❌ Chrome単体でページ処理失敗")
        else:
            print(f"❌ Chrome単体実行失敗 (exit code: {result.returncode})")
            print(f"stderr: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("❌ Chrome単体実行タイムアウト")
    except Exception as e:
        print(f"Chrome プロセス解析エラー: {e}")

def main():
    """メイン実行"""
    print("Chrome WebDriver 詳細ログ収集開始")
    print("=" * 60)
    
    # プロセス動作確認
    check_chrome_process_behavior()
    
    # 詳細ログテスト
    success = test_chrome_with_verbose_logging()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 詳細ログテスト成功")
    else:
        print("❌ 詳細ログテスト失敗 - ログを確認してください")

if __name__ == "__main__":
    main()