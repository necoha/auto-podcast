#!/usr/bin/env python3
"""
Chrome WebDriver デバッグ - 最小構成テスト
段階的にオプションを追加して問題箇所を特定
"""

import os
import sys
import time
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions

def run_system_info():
    """システム情報を取得"""
    print("=== システム情報 ===")
    try:
        # メモリ情報
        result = subprocess.run(['free', '-h'], capture_output=True, text=True)
        print(f"メモリ使用量:\n{result.stdout}")
        
        # Chrome情報
        result = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
        print(f"Chrome バージョン: {result.stdout.strip()}")
        
        # ChromeDriver情報
        chromedriver_path = '/usr/local/bin/chromedriver'
        if os.path.exists(chromedriver_path):
            result = subprocess.run([chromedriver_path, '--version'], capture_output=True, text=True)
            print(f"ChromeDriver バージョン: {result.stdout.strip()}")
        
        # プロセス情報
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        chrome_processes = [line for line in result.stdout.split('\n') if 'chrome' in line.lower()]
        if chrome_processes:
            print(f"既存Chromeプロセス: {len(chrome_processes)}個")
            for proc in chrome_processes[:3]:  # 最初の3つだけ表示
                print(f"  {proc}")
    except Exception as e:
        print(f"システム情報取得エラー: {e}")

def test_chrome_minimal():
    """最小構成でChromeをテスト"""
    print("\n=== テスト1: 最小構成Chrome ===")
    
    chrome_options = ChromeOptions()
    
    # CI環境の場合のみ最小限のオプション
    if os.getenv('GITHUB_ACTIONS'):
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        print("最小オプション適用: --headless --disable-dev-shm-usage --no-sandbox")
    else:
        print("ローカル環境: ヘッドレスなし")
    
    # ChromeDriverサービス設定
    chromedriver_path = '/usr/local/bin/chromedriver'
    if os.getenv('GITHUB_ACTIONS') and os.path.exists(chromedriver_path):
        service = ChromeService(chromedriver_path)
        print(f"システムChromeDriver使用: {chromedriver_path}")
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = ChromeService(ChromeDriverManager().install())
        print("WebDriverManager使用")
    
    driver = None
    try:
        # Chrome起動
        print("Chrome起動中...")
        start_time = time.time()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        init_time = time.time() - start_time
        print(f"✅ Chrome起動成功 ({init_time:.2f}秒)")
        
        # 基本テスト
        print("基本動作テスト中...")
        
        # 1. 空ページテスト
        driver.get("data:text/html,<html><body><h1>Test</h1></body></html>")
        time.sleep(2)
        
        # 2. タイトル確認
        title = driver.title
        print(f"ページタイトル: '{title}'")
        
        # 3. URL確認
        current_url = driver.current_url
        print(f"現在URL: {current_url}")
        
        # 4. ページソース確認
        page_source = driver.page_source
        print(f"ページソース長: {len(page_source)} 文字")
        
        if "Test" in page_source:
            print("✅ 最小構成テスト完全成功")
            return True
        else:
            print("⚠️ ページ内容が期待と異なります")
            return False
            
    except Exception as e:
        print(f"❌ 最小構成テスト失敗: {e}")
        print(f"エラータイプ: {type(e).__name__}")
        return False
    finally:
        if driver:
            try:
                driver.quit()
                print("Chrome正常終了")
            except:
                print("Chrome終了時にエラー")

def test_chrome_step_by_step():
    """段階的にオプションを追加してテスト"""
    print("\n=== テスト2: 段階的オプション追加 ===")
    
    if not os.getenv('GITHUB_ACTIONS'):
        print("ローカル環境では段階テストをスキップ")
        return
    
    base_options = ['--headless', '--disable-dev-shm-usage', '--no-sandbox']
    additional_options = [
        '--disable-gpu',
        '--disable-software-rasterizer', 
        '--window-size=1280,720',
        '--single-process',
        '--no-zygote',
        '--disable-web-security',
        '--disable-background-timer-throttling',
        '--disable-renderer-backgrounding',
        '--disable-extensions',
        '--log-level=3'
    ]
    
    chromedriver_path = '/usr/local/bin/chromedriver'
    service = ChromeService(chromedriver_path)
    
    current_options = base_options.copy()
    
    for i, new_option in enumerate(additional_options):
        current_options.append(new_option)
        print(f"\n--- ステップ {i+1}: {new_option} 追加 ---")
        
        chrome_options = ChromeOptions()
        for opt in current_options:
            chrome_options.add_argument(opt)
        
        driver = None
        success = False
        
        try:
            print(f"現在のオプション: {current_options}")
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.get("data:text/html,<html><body>Step Test</body></html>")
            time.sleep(1)
            
            if "Step Test" in driver.page_source:
                print(f"✅ ステップ {i+1} 成功")
                success = True
            else:
                print(f"⚠️ ステップ {i+1} ページ内容異常")
                
        except Exception as e:
            print(f"❌ ステップ {i+1} 失敗: {e}")
            print(f"問題のオプション: {new_option}")
            # このオプションが問題なら除去
            current_options.remove(new_option)
            break
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        
        if not success:
            break

def check_system_logs():
    """システムログを確認"""
    print("\n=== テスト3: システムログ確認 ===")
    
    if not os.getenv('GITHUB_ACTIONS'):
        print("ローカル環境ではログ確認をスキップ")
        return
    
    try:
        # dmesgでOOM killerやkernel trapを確認
        print("dmesgログ確認中...")
        result = subprocess.run(['dmesg', '-T'], capture_output=True, text=True)
        dmesg_lines = result.stdout.split('\n')
        
        # 関連キーワードでフィルタ
        keywords = ['killed', 'oom', 'chrome', 'trap', 'segfault', 'memory']
        relevant_lines = []
        
        for line in dmesg_lines[-100:]:  # 最後の100行のみ
            if any(keyword in line.lower() for keyword in keywords):
                relevant_lines.append(line)
        
        if relevant_lines:
            print("🔍 関連するdmesgエントリ:")
            for line in relevant_lines[-10:]:  # 最後の10件のみ
                print(f"  {line}")
        else:
            print("✅ dmesgに問題となるエントリなし")
            
        # プロセス情報
        print("\n現在のプロセス状況:")
        result = subprocess.run(['ps', 'aux', '--sort=-%mem'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        print("メモリ使用量TOP5:")
        for line in lines[1:6]:  # ヘッダー除く最初の5つ
            if line.strip():
                print(f"  {line}")
                
    except Exception as e:
        print(f"システムログ確認エラー: {e}")

def main():
    """メイン実行"""
    print("Chrome WebDriver デバッグ開始")
    print("=" * 50)
    
    # システム情報
    run_system_info()
    
    # テスト1: 最小構成
    success1 = test_chrome_minimal()
    
    # テスト2: 段階的追加（CI環境のみ）
    if os.getenv('GITHUB_ACTIONS'):
        test_chrome_step_by_step()
    
    # テスト3: システムログ
    check_system_logs()
    
    print("\n" + "=" * 50)
    if success1:
        print("✅ 最小構成テストは成功しました")
        print("問題は追加オプションにある可能性があります")
    else:
        print("❌ 最小構成テストも失敗しました") 
        print("基本的なChrome/ChromeDriverの問題の可能性があります")

if __name__ == "__main__":
    main()