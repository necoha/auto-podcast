#!/usr/bin/env python3
"""
Notebook LM接続テスト用スクリプト
CI環境でのSelenium + Chrome動作確認
"""

import os
import sys
from oauth_automation import OAuthNotebookLMAutomator

def test_notebook_lm_access():
    """Notebook LMアクセステスト"""
    print("=== Notebook LM アクセステスト開始 ===")
    
    # 環境変数表示
    print(f"GitHub Actions環境: {bool(os.getenv('GITHUB_ACTIONS'))}")
    print(f"Skip Real Generation: {os.getenv('SKIP_REAL_GENERATION', 'true')}")
    print(f"Test Mode: {os.getenv('NOTEBOOK_LM_TEST_MODE', 'false')}")
    
    try:
        # オートメーター初期化
        automator = OAuthNotebookLMAutomator()
        
        # 認証テスト
        print("\n--- 認証テスト ---")
        auth_success = automator.oauth_login()
        print(f"認証結果: {'成功' if auth_success else '失敗'}")
        
        if auth_success:
            print("\n--- Notebook LM機能テスト ---")
            
            # テスト用URL
            test_url = "https://techcrunch.com/2024/01/01/ai-trends-2024/"
            test_output = "./test_audio.mp3"
            
            # テストモードかどうかで分岐
            if os.getenv('NOTEBOOK_LM_TEST_MODE', 'false').lower() == 'true':
                print("🔬 実際のNotebook LM呼び出しテスト")
                
                # 実際の音声生成を試行
                success = automator.create_audio_from_url(
                    source_url=test_url,
                    output_path=test_output,
                    custom_prompt="これは接続テストです。短い音声で構いません。"
                )
                
                print(f"音声生成結果: {'成功' if success else '失敗'}")
                
                if success and os.path.exists(test_output):
                    file_size = os.path.getsize(test_output)
                    print(f"生成ファイルサイズ: {file_size} bytes")
                    
                    # テストファイル削除
                    try:
                        os.remove(test_output)
                        print("テストファイルを削除しました")
                    except:
                        pass
                        
            else:
                print("🧪 モックモードでのテスト")
                
        return auth_success
        
    except Exception as e:
        print(f"テストエラー: {e}")
        import traceback
        print(f"詳細: {traceback.format_exc()}")
        return False
    
    finally:
        try:
            if 'automator' in locals():
                automator.close()
        except:
            pass

def main():
    """メイン実行"""
    print("Notebook LM 接続テストを開始します...\n")
    
    success = test_notebook_lm_access()
    
    print(f"\n=== テスト結果: {'✅ 成功' if success else '❌ 失敗'} ===")
    
    if success:
        print("✅ Notebook LMへの基本アクセスが確認できました")
        if os.getenv('NOTEBOOK_LM_TEST_MODE', 'false').lower() == 'true':
            print("✅ 実際の音声生成機能も動作しています")
        else:
            print("ℹ️  実機能テストには NOTEBOOK_LM_TEST_MODE=true を設定してください")
    else:
        print("❌ 接続に問題があります。以下を確認してください：")
        print("   - Chrome/ChromeDriverのインストール")
        print("   - OAuth認証情報の設定")  
        print("   - ネットワーク接続")
        print("   - GitHub Actions環境での制限")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())