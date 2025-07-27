"""
コンテンツソース管理システム
RSSフィード、ニュースサイト、テキストファイルからコンテンツを収集・処理
"""

import requests
from bs4 import BeautifulSoup
import feedparser
import json
import os
from datetime import datetime, timedelta
import config


class ContentManager:
    def __init__(self):
        self.content_dir = config.CONTENT_DIR
        os.makedirs(self.content_dir, exist_ok=True)
    
    def fetch_rss_feeds(self, max_articles=5):
        """RSSフィードから最新記事を取得"""
        all_articles = []
        
        for feed_url in config.RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                articles = []
                
                for entry in feed.entries[:max_articles]:
                    article = {
                        'title': entry.get('title', ''),
                        'summary': entry.get('summary', ''),
                        'link': entry.get('link', ''),
                        'published': entry.get('published', ''),
                        'source': feed.feed.get('title', feed_url)
                    }
                    articles.append(article)
                
                all_articles.extend(articles)
                print(f"取得完了: {feed.feed.get('title', feed_url)} - {len(articles)}記事")
                
            except Exception as e:
                print(f"RSS取得エラー ({feed_url}): {e}")
        
        return all_articles
    
    def fetch_web_content(self, url):
        """Webページからコンテンツを取得"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # メインコンテンツを抽出
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            # 記事本文を取得（一般的なセレクターを試行）
            content_selectors = [
                'article', 
                '.content', 
                '.article-content',
                '.post-content',
                'main',
                '#content'
            ]
            
            content = ""
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content = elements[0].get_text(strip=True)
                    break
            
            if not content:
                content = soup.get_text(strip=True)
            
            return content[:config.MAX_CONTENT_LENGTH]
            
        except Exception as e:
            print(f"Webコンテンツ取得エラー ({url}): {e}")
            return ""
    
    def process_articles_for_podcast(self, articles, topic_focus=None):
        """記事をポッドキャスト用に処理・要約"""
        if not articles:
            return ""
        
        # 記事を日付順でソート
        sorted_articles = sorted(articles, 
                               key=lambda x: x.get('published', ''), 
                               reverse=True)
        
        # トピック絞り込み
        if topic_focus:
            filtered_articles = []
            for article in sorted_articles:
                title_summary = f"{article['title']} {article['summary']}".lower()
                if any(keyword.lower() in title_summary for keyword in topic_focus):
                    filtered_articles.append(article)
            sorted_articles = filtered_articles
        
        # ポッドキャスト用テキスト生成
        podcast_script = []
        podcast_script.append(f"今日は{datetime.now().strftime('%Y年%m月%d日')}です。")
        podcast_script.append("本日のニュースをお届けします。\n")
        
        for i, article in enumerate(sorted_articles[:5], 1):
            script_part = f"""
記事{i}: {article['title']}

{article['summary']}

ソース: {article['source']}
詳細: {article['link']}

"""
            podcast_script.append(script_part)
        
        return "\n".join(podcast_script)
    
    def save_content(self, content, filename=None):
        """コンテンツをファイルに保存"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"content_{timestamp}.txt"
        
        filepath = os.path.join(self.content_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return filepath
        except Exception as e:
            print(f"コンテンツ保存エラー: {e}")
            return None
    
    def load_content(self, filename):
        """保存されたコンテンツを読み込み"""
        filepath = os.path.join(self.content_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"コンテンツ読み込みエラー: {e}")
            return ""
    
    def create_daily_content(self, topic_keywords=None):
        """日次コンテンツを作成"""
        print("RSSフィードから記事を取得中...")
        articles = self.fetch_rss_feeds()
        
        if not articles:
            print("記事が取得できませんでした。")
            return None
        
        print(f"{len(articles)}記事を取得しました。")
        
        # ポッドキャスト用に処理
        podcast_content = self.process_articles_for_podcast(articles, topic_keywords)
        
        # 保存
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"daily_podcast_{timestamp}.txt"
        filepath = self.save_content(podcast_content, filename)
        
        if filepath:
            print(f"コンテンツを保存しました: {filepath}")
            return filepath
        else:
            return None
    
    def get_trending_topics(self, articles):
        """記事からトレンドトピックを抽出"""
        from collections import Counter
        import re
        
        # 簡単なキーワード抽出
        all_text = " ".join([f"{a['title']} {a['summary']}" for a in articles])
        
        # 日本語の場合は単語分割が必要（簡易版）
        words = re.findall(r'\b\w+\b', all_text.lower())
        
        # ストップワードを除外
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'は', 'が', 'を', 'に', 'で', 'と', 'の'}
        filtered_words = [w for w in words if len(w) > 2 and w not in stop_words]
        
        # 頻出語をカウント
        word_counts = Counter(filtered_words)
        return word_counts.most_common(10)


# 使用例とテスト
if __name__ == "__main__":
    content_manager = ContentManager()
    
    # 日次コンテンツ作成
    content_file = content_manager.create_daily_content(['AI', 'テクノロジー', 'プログラミング'])
    
    if content_file:
        # 生成されたコンテンツを確認
        content = content_manager.load_content(os.path.basename(content_file))
        print("生成されたポッドキャストコンテンツ:")
        print(content[:500] + "..." if len(content) > 500 else content)