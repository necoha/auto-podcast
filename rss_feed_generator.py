"""
RSS配信システム
生成されたポッドキャストエピソードをRSSフィードとして配信
"""

import os
import json
from datetime import datetime
from feedgen.feed import FeedGenerator
import config


class RSSFeedGenerator:
    def __init__(self):
        self.feed_file = config.RSS_OUTPUT_FILE
        self.audio_dir = config.AUDIO_OUTPUT_DIR
        self.content_dir = config.CONTENT_DIR
        
    def create_feed(self):
        """基本的なRSSフィードを作成"""
        fg = FeedGenerator()
        
        # ポッドキャストの基本情報
        fg.id(config.PODCAST_BASE_URL)
        fg.title(config.PODCAST_TITLE)
        fg.description(config.PODCAST_DESCRIPTION)
        fg.author({'name': config.PODCAST_AUTHOR})
        fg.language(config.PODCAST_LANGUAGE)
        fg.link(href=config.PODCAST_BASE_URL, rel='alternate')
        fg.link(href=f"{config.PODCAST_BASE_URL}/feed.xml", rel='self')
        fg.logo(f"{config.PODCAST_BASE_URL}/logo.png")
        fg.subtitle("AI generated podcast using Notebook LM")
        fg.category('Technology')
        fg.lastBuildDate(datetime.now())
        
        # iTunes用の拡張情報
        fg.podcast.itunes_category('Technology')
        fg.podcast.itunes_author(config.PODCAST_AUTHOR)
        fg.podcast.itunes_summary(config.PODCAST_DESCRIPTION)
        fg.podcast.itunes_owner({'name': config.PODCAST_AUTHOR, 'email': 'noreply@example.com'})
        fg.podcast.itunes_image(f"{config.PODCAST_BASE_URL}/logo.png")
        fg.podcast.itunes_explicit('no')
        
        return fg
    
    def get_episode_metadata(self, audio_filename):
        """エピソードのメタデータを取得"""
        metadata_filename = f"metadata_{audio_filename.replace('.mp3', '.json')}"
        metadata_path = os.path.join(self.content_dir, metadata_filename)
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            # メタデータがない場合のデフォルト値
            return {
                'episode_number': 1,
                'generated_at': datetime.now().isoformat(),
                'topic_keywords': [],
                'content_file': ''
            }
    
    def get_episode_description(self, metadata):
        """エピソードの説明文を生成"""
        description_parts = []
        
        # 生成日時
        try:
            generated_date = datetime.fromisoformat(metadata['generated_at'].replace('Z', '+00:00'))
            description_parts.append(f"配信日: {generated_date.strftime('%Y年%m月%d日')}")
        except:
            description_parts.append(f"配信日: {datetime.now().strftime('%Y年%m月%d日')}")
        
        # URL基盤かコンテンツ基盤かで説明を分ける
        if metadata.get('generation_method') == 'url_based':
            # URL基盤の場合
            if metadata.get('source_title'):
                description_parts.append(f"記事タイトル: {metadata['source_title']}")
            if metadata.get('source_name'):
                description_parts.append(f"ソース: {metadata['source_name']}")
            if metadata.get('source_url'):
                description_parts.append(f"元記事: {metadata['source_url']}")
        else:
            # コンテンツ基盤の場合
            if metadata.get('topic_keywords'):
                keywords = ', '.join(metadata['topic_keywords'])
                description_parts.append(f"主要トピック: {keywords}")
            
            # コンテンツファイルの内容を一部読み込み
            if metadata.get('content_file'):
                content_path = os.path.join(self.content_dir, metadata['content_file'])
                try:
                    with open(content_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 最初の段落を取得
                        first_paragraph = content.split('\n\n')[0] if content else ""
                        if len(first_paragraph) > 200:
                            first_paragraph = first_paragraph[:200] + "..."
                        description_parts.append(f"\n{first_paragraph}")
                except:
                    pass
        
        description_parts.append("\n\nNotebook LMのAudio Overview機能を使用して自動生成されたポッドキャストです。")
        
        return '\n'.join(description_parts)
    
    def add_episode_to_feed(self, fg, audio_filename):
        """エピソードをフィードに追加"""
        metadata = self.get_episode_metadata(audio_filename)
        audio_path = os.path.join(self.audio_dir, audio_filename)
        
        if not os.path.exists(audio_path):
            print(f"音声ファイルが見つかりません: {audio_path}")
            return
        
        # エピソード情報
        fe = fg.add_entry()
        
        episode_num = metadata.get('episode_number', 1)
        title = f"第{episode_num}話 - AI Auto Podcast"
        
        # 日付情報
        try:
            pub_date = datetime.fromisoformat(metadata['generated_at'].replace('Z', '+00:00'))
        except:
            pub_date = datetime.fromtimestamp(os.path.getctime(audio_path))
        
        # エピソード基本情報
        fe.id(f"{config.PODCAST_BASE_URL}/episodes/{episode_num}")
        fe.title(title)
        fe.description(self.get_episode_description(metadata))
        fe.pubDate(pub_date)
        
        # 音声ファイル情報
        audio_url = f"{config.PODCAST_BASE_URL}/audio/{audio_filename}"
        audio_size = os.path.getsize(audio_path)
        
        fe.enclosure(audio_url, str(audio_size), 'audio/mpeg')
        
        # iTunes用情報
        fe.podcast.itunes_duration(self.get_audio_duration(audio_path))
        fe.podcast.itunes_episode(episode_num)
        fe.podcast.itunes_explicit('no')
        
        return fe
    
    def get_audio_duration(self, audio_path):
        """音声ファイルの再生時間を取得"""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_mp3(audio_path)
            duration_seconds = len(audio) // 1000
            
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            seconds = duration_seconds % 60
            
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes:02d}:{seconds:02d}"
        except:
            return "00:00"
    
    def generate_rss_feed(self):
        """完全なRSSフィードを生成"""
        try:
            # フィード作成
            fg = self.create_feed()
            
            # 音声ファイル一覧を取得（新しい順）
            if not os.path.exists(self.audio_dir):
                print(f"音声ディレクトリが存在しません: {self.audio_dir}")
                return self.create_fallback_rss()
            
            audio_files = [f for f in os.listdir(self.audio_dir) if f.endswith('.mp3')]
            print(f"発見された音声ファイル: {audio_files}")
            
            if not audio_files:
                print("音声ファイルが見つかりません - フォールバックRSS生成")
                return self.create_fallback_rss()
            
            audio_files.sort(key=lambda x: os.path.getctime(os.path.join(self.audio_dir, x)), reverse=True)
            
            # 各エピソードをフィードに追加
            for audio_file in audio_files:
                try:
                    self.add_episode_to_feed(fg, audio_file)
                    print(f"エピソード追加成功: {audio_file}")
                except Exception as e:
                    print(f"エピソード追加エラー ({audio_file}): {e}")
            
            # RSSファイル生成
            rss_content = fg.rss_str(pretty=True)
            
            with open(self.feed_file, 'wb') as f:
                f.write(rss_content)
            
            print(f"RSSフィード生成完了: {self.feed_file}")
            return True
            
        except Exception as e:
            print(f"RSS生成エラー: {e}")
            return self.create_fallback_rss()
    
    def create_fallback_rss(self):
        """フォールバック用の基本RSSを生成"""
        try:
            print("フォールバックRSS生成中...")
            fg = self.create_feed()
            
            # デモエピソードを追加
            fe = fg.add_entry()
            fe.id(f"{config.PODCAST_BASE_URL}/episodes/demo")
            fe.title("AI Auto Podcast - システム準備中")
            fe.description("AI Auto Podcastシステムが準備中です。まもなく自動生成されたエピソードが配信開始されます。")
            fe.pubDate(datetime.now())
            
            # RSSファイル生成
            rss_content = fg.rss_str(pretty=True)
            
            with open(self.feed_file, 'wb') as f:
                f.write(rss_content)
            
            print(f"フォールバックRSSフィード生成完了: {self.feed_file}")
            return True
            
        except Exception as e:
            print(f"フォールバックRSS生成エラー: {e}")
            return False
    
    def update_feed_with_new_episode(self, audio_filename):
        """新しいエピソードでフィードを更新"""
        return self.generate_rss_feed()
    
    def validate_feed(self):
        """RSSフィードの妥当性をチェック"""
        try:
            import xml.etree.ElementTree as ET
            
            if not os.path.exists(self.feed_file):
                return False, "RSSファイルが存在しません"
            
            # XML解析テスト
            tree = ET.parse(self.feed_file)
            root = tree.getroot()
            
            # 基本要素の確認
            channel = root.find('channel')
            if channel is None:
                return False, "channelエレメントが見つかりません"
            
            title = channel.find('title')
            if title is None or not title.text:
                return False, "titleエレメントが見つかりません"
            
            # エピソード数確認
            items = channel.findall('item')
            episode_count = len(items)
            
            return True, f"RSS妥当性チェック通過 - {episode_count}エピソード"
            
        except Exception as e:
            return False, f"妥当性チェックエラー: {e}"


# 使用例とテスト
if __name__ == "__main__":
    rss_generator = RSSFeedGenerator()
    
    # フィード生成
    success = rss_generator.generate_rss_feed()
    
    if success:
        # 妥当性チェック
        is_valid, message = rss_generator.validate_feed()
        print(f"妥当性チェック: {message}")
        
        if is_valid:
            print(f"RSSフィードURL: {config.PODCAST_BASE_URL}/feed.xml")
    else:
        print("RSS生成に失敗しました")