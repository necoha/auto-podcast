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
            
            # Step 1: 最新記事URLを取得
            print("1. 最新記事URLを取得中...")
            article_urls = self.content_manager.get_latest_article_urls(limit=3)
            
            if not article_urls:
                print("記事URLの取得に失敗しました。従来方式でコンテンツ生成します。")
                return self.generate_from_content(topic_keywords, custom_prompt)
            
            # Step 2: 最適な記事を選択（最初の記事を使用）
            selected_article = article_urls[0]
            print(f"選択記事: {selected_article['title']} - {selected_article['source']}")
            print(f"URL: {selected_article['url']}")
            
            # Step 3: Audio Overview生成
            print("2. Notebook LMでURL音声生成中...")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_filename = f"podcast_episode_{timestamp}.mp3"
            audio_path = os.path.join(config.AUDIO_OUTPUT_DIR, audio_filename)
            
            # デフォルトのプロンプト
            if not custom_prompt:
                custom_prompt = """
                このWebページの内容を基に、以下の形式でポッドキャストを作成してください：
                
                1. 親しみやすい挨拶で始める
                2. 記事の要約を分かりやすく紹介
                3. 重要なポイントを詳しく解説
                4. 聞き手との対話を意識した自然な会話
                5. 今後の展望やまとめで終了
                
                トーン：友好的で親しみやすく、専門用語は分かりやすく説明
                長さ：10-15分程度のポッドキャスト
                """
            
            # OAuth NotebookLM自動化実行（URL指定）
            automator = OAuthNotebookLMAutomator()
            success = automator.create_audio_from_url(
                source_url=selected_article['url'],
                output_path=audio_path,
                custom_prompt=custom_prompt
            )
            
            if success and os.path.exists(audio_path):
                print(f"3. 音声ファイル生成完了: {audio_path}")
                
                # 生成カウント更新
                self.daily_generation_count += 1
                
                # メタデータ保存（URL情報も含める）
                self.save_episode_metadata_from_url(audio_filename, selected_article, topic_keywords)
                
                return {
                    'audio_file': audio_path,
                    'source_article': selected_article,
                    'timestamp': timestamp,
                    'episode_number': self.get_next_episode_number()
                }
            else:
                print("URL音声生成に失敗しました。従来方式を試します。")
                return self.generate_from_content(topic_keywords, custom_prompt)
                
        except Exception as e:
            print(f"ポッドキャスト生成エラー: {e}")
            return None
    
    def generate_from_content(self, topic_keywords=None, custom_prompt=None):
        """従来方式：テキストコンテンツから音声生成"""
        try:
            print("従来方式でコンテンツから音声生成...")
            
            # コンテンツ収集
            content_file = self.content_manager.create_daily_content(topic_keywords)
            
            if not content_file:
                print("コンテンツの生成に失敗しました。")
                return None
            
            # コンテンツ読み込み
            content_text = self.content_manager.load_content(os.path.basename(content_file))
            
            if len(content_text) < 100:
                print("コンテンツが短すぎます。")
                return None
            
            # 音声生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_filename = f"podcast_episode_{timestamp}.mp3"
            audio_path = os.path.join(config.AUDIO_OUTPUT_DIR, audio_filename)
            
            automator = OAuthNotebookLMAutomator()
            success = automator.create_audio_from_content(
                content_text=content_text,
                output_path=audio_path,
                custom_prompt=custom_prompt
            )
            
            if success and os.path.exists(audio_path):
                print(f"従来方式音声生成完了: {audio_path}")
                
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
                print("従来方式音声生成も失敗しました。")
                return None
                
        except Exception as e:
            print(f"従来方式生成エラー: {e}")
            return None
    
    def save_episode_metadata(self, audio_filename, content_file, topic_keywords):
        """エピソードのメタデータを保存"""
        metadata = {
            'audio_file': audio_filename,
            'content_file': os.path.basename(content_file),
            'generated_at': datetime.now().isoformat(),
            'topic_keywords': topic_keywords or [],
            'episode_number': self.get_next_episode_number(),
            'generation_method': 'content_based'
        }
        
        metadata_file = os.path.join(config.CONTENT_DIR, f"metadata_{audio_filename.replace('.mp3', '.json')}")
        
        try:
            import json
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"メタデータ保存エラー: {e}")
    
    def save_episode_metadata_from_url(self, audio_filename, article_info, topic_keywords):
        """URL音声生成のメタデータを保存"""
        metadata = {
            'audio_file': audio_filename,
            'source_url': article_info['url'],
            'source_title': article_info['title'],
            'source_name': article_info['source'],
            'published_date': article_info.get('published', ''),
            'generated_at': datetime.now().isoformat(),
            'topic_keywords': topic_keywords or [],
            'episode_number': self.get_next_episode_number(),
            'generation_method': 'url_based'
        }
        
        metadata_file = os.path.join(config.CONTENT_DIR, f"metadata_{audio_filename.replace('.mp3', '.json')}")
        
        try:
            import json
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"URLメタデータ保存エラー: {e}")
    
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
    
    # 環境変数からパラメータを取得
    keywords_str = os.getenv('KEYWORDS', 'AI,Technology,Programming')
    custom_prompt = os.getenv('CUSTOM_PROMPT', None)
    
    # キーワードをリストに変換
    keywords = [k.strip() for k in keywords_str.split(',') if k.strip()] if keywords_str else None
    
    print(f"ポッドキャストエピソードを生成します...")
    print(f"キーワード: {keywords}")
    print(f"カスタムプロンプト: {custom_prompt if custom_prompt else 'なし'}")
    
    result = generator.generate_podcast_episode(keywords, custom_prompt)
    
    if result:
        print(f"生成完了!")
        print(f"音声ファイル: {result['audio_file']}")
        print(f"エピソード番号: {result['episode_number']}")
        exit(0)
    else:
        print("ポッドキャスト生成に失敗しました")
        exit(1)
    
    # スケジューラー実行（コメントアウトして必要に応じて有効化）
    # generator.start_scheduler()