"""
メインのポッドキャスト生成システム
コンテンツ管理、音声生成、ファイル管理を統合
"""

import os
import schedule
import time
from datetime import datetime
from content_manager import ContentManager
from oauth_automation import OAuthNotebookLMAutomator
import config


class PodcastGenerator:
    def __init__(self):
        self.content_manager = ContentManager()
        self.daily_generation_count = 0
        self.last_generation_date = None
        
        # ディレクトリ作成
        os.makedirs(config.AUDIO_OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.CONTENT_DIR, exist_ok=True)
    
    def check_daily_limit(self):
        """1日の生成回数制限をチェック"""
        today = datetime.now().date()
        
        if self.last_generation_date != today:
            self.daily_generation_count = 0
            self.last_generation_date = today
        
        if self.daily_generation_count >= config.MAX_DAILY_GENERATIONS:
            print(f"本日の生成上限に達しました ({config.MAX_DAILY_GENERATIONS}回)")
            return False
        
        return True
    
    def generate_podcast_episode(self, topic_keywords=None, custom_prompt=None):
        """ポッドキャストエピソードを生成"""
        try:
            # 制限チェック
            if not self.check_daily_limit():
                return None
            
            print("ポッドキャストエピソード生成を開始...")
            
            # Step 1: コンテンツ収集
            print("1. コンテンツを収集中...")
            content_file = self.content_manager.create_daily_content(topic_keywords)
            
            if not content_file:
                print("コンテンツの生成に失敗しました。")
                return None
            
            # Step 2: コンテンツ読み込み
            content_text = self.content_manager.load_content(os.path.basename(content_file))
            
            if len(content_text) < 100:
                print("コンテンツが短すぎます。")
                return None
            
            # Step 3: Audio Overview生成
            print("2. Notebook LMでAudio Overviewを生成中...")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_filename = f"podcast_episode_{timestamp}.mp3"
            audio_path = os.path.join(config.AUDIO_OUTPUT_DIR, audio_filename)
            
            # デフォルトのプロンプト
            if not custom_prompt:
                custom_prompt = """
                このコンテンツを基に、以下の形式でポッドキャストを作成してください：
                
                1. 親しみやすい挨拶で始める
                2. 今日の主要なトピックを簡潔に紹介
                3. 各ニュースを分かりやすく解説
                4. 聞き手との対話を意識した自然な会話
                5. 最後にまとめと次回予告
                
                トーン：友好的で親しみやすく、専門用語は分かりやすく説明
                長さ：10-15分程度のポッドキャスト
                """
            
            # OAuth NotebookLM自動化実行
            automator = OAuthNotebookLMAutomator()
            success = automator.create_audio_from_content(
                content_text=content_text,
                output_path=audio_path,
                custom_prompt=custom_prompt
            )
            
            if success and os.path.exists(audio_path):
                print(f"3. 音声ファイル生成完了: {audio_path}")
                
                # 生成カウント更新
                self.daily_generation_count += 1
                
                # メタデータ保存
                self.save_episode_metadata(audio_filename, content_file, topic_keywords)
                
                return {
                    'audio_file': audio_path,
                    'content_file': content_file,
                    'timestamp': timestamp,
                    'episode_number': self.get_next_episode_number()
                }
            else:
                print("Audio Overview生成に失敗しました。")
                return None
                
        except Exception as e:
            print(f"ポッドキャスト生成エラー: {e}")
            return None
    
    def save_episode_metadata(self, audio_filename, content_file, topic_keywords):
        """エピソードのメタデータを保存"""
        metadata = {
            'audio_file': audio_filename,
            'content_file': os.path.basename(content_file),
            'generated_at': datetime.now().isoformat(),
            'topic_keywords': topic_keywords or [],
            'episode_number': self.get_next_episode_number()
        }
        
        metadata_file = os.path.join(config.CONTENT_DIR, f"metadata_{audio_filename.replace('.mp3', '.json')}")
        
        try:
            import json
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"メタデータ保存エラー: {e}")
    
    def get_next_episode_number(self):
        """次のエピソード番号を取得"""
        try:
            audio_files = [f for f in os.listdir(config.AUDIO_OUTPUT_DIR) if f.endswith('.mp3')]
            return len(audio_files) + 1
        except:
            return 1
    
    def cleanup_old_files(self, days_to_keep=30):
        """古いファイルをクリーンアップ"""
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        
        for directory in [config.AUDIO_OUTPUT_DIR, config.CONTENT_DIR]:
            try:
                for filename in os.listdir(directory):
                    filepath = os.path.join(directory, filename)
                    if os.path.getctime(filepath) < cutoff_time:
                        os.remove(filepath)
                        print(f"古いファイルを削除: {filepath}")
            except Exception as e:
                print(f"クリーンアップエラー: {e}")
    
    def run_scheduled_generation(self):
        """スケジュール実行用のメソッド"""
        print(f"定期実行開始: {datetime.now()}")
        
        # 話題のキーワード（カスタマイズ可能）
        topic_keywords = ['AI', 'テクノロジー', 'プログラミング', 'スタートアップ']
        
        result = self.generate_podcast_episode(topic_keywords)
        
        if result:
            print(f"エピソード {result['episode_number']} 生成完了")
            
            # 古いファイルのクリーンアップ
            self.cleanup_old_files()
        else:
            print("定期生成に失敗しました")
    
    def start_scheduler(self):
        """スケジューラーを開始"""
        if config.GENERATION_SCHEDULE == "daily":
            schedule.every().day.at("09:00").do(self.run_scheduled_generation)
        elif config.GENERATION_SCHEDULE == "weekly":
            schedule.every().monday.at("09:00").do(self.run_scheduled_generation)
        elif config.GENERATION_SCHEDULE == "hourly":
            schedule.every().hour.do(self.run_scheduled_generation)
        
        print(f"スケジューラー開始: {config.GENERATION_SCHEDULE}")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 1分ごとにチェック
        except KeyboardInterrupt:
            print("スケジューラーを停止しました")


# メイン実行部分
if __name__ == "__main__":
    generator = PodcastGenerator()
    
    # 手動実行の例
    print("手動でポッドキャストエピソードを生成します...")
    result = generator.generate_podcast_episode(['AI', 'テクノロジー'])
    
    if result:
        print(f"生成完了!")
        print(f"音声ファイル: {result['audio_file']}")
        print(f"エピソード番号: {result['episode_number']}")
    
    # スケジューラー実行（コメントアウトして必要に応じて有効化）
    # generator.start_scheduler()