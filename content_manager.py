"""
コンテンツソース管理システム
RSSフィード、ニュースサイト、テキストファイルからコンテンツを収集・処理
"""

import logging
import os
import json
import re
from datetime import datetime, timedelta, timezone
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import requests
from bs4 import BeautifulSoup
import feedparser

import config

logger = logging.getLogger(__name__)


class ContentManager:
    def __init__(self):
        self.content_dir = config.CONTENT_DIR
        os.makedirs(self.content_dir, exist_ok=True)
    
    def fetch_rss_feeds(self, max_articles=5, hours=24):
        """RSSフィードから最新記事を取得（日付フィルタ＋重複排除付き）

        Args:
            max_articles: フィードあたりの最大取得件数
            hours: 直近N時間以内の記事のみ取得（0で無制限）
        """
        all_articles = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours) if hours > 0 else None

        for feed_url in config.RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                articles = []

                for entry in feed.entries[:max_articles * 2]:  # フィルタ分を多めに取得
                    pub_dt = self._parse_published_date(entry)

                    # 日付フィルタ: cutoff より古い記事はスキップ
                    if cutoff and pub_dt and pub_dt < cutoff:
                        continue

                    article = {
                        'title': entry.get('title', ''),
                        'summary': entry.get('summary', ''),
                        'link': entry.get('link', ''),
                        'published': entry.get('published', ''),
                        'published_dt': pub_dt,
                        'source': feed.feed.get('title', feed_url),
                    }
                    articles.append(article)

                    if len(articles) >= max_articles:
                        break

                all_articles.extend(articles)
                logger.info("取得完了: %s - %d記事", feed.feed.get('title', feed_url), len(articles))

            except Exception as e:
                logger.warning("RSS取得エラー (%s): %s", feed_url, e)

        # 重複排除
        before = len(all_articles)
        all_articles = self._deduplicate_articles(all_articles)
        removed = before - len(all_articles)
        if removed:
            logger.info("重複排除: %d件を除外（%d → %d件）", removed, before, len(all_articles))

        return all_articles

    # ── 日付パース ──────────────────────────────────────────

    def _parse_published_date(self, entry) -> datetime | None:
        """feedparser の entry から公開日時を UTC datetime に変換する"""
        # feedparser が parsed 形式を提供している場合
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                import calendar
                ts = calendar.timegm(entry.published_parsed)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass

        if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            try:
                import calendar
                ts = calendar.timegm(entry.updated_parsed)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass

        # 文字列フォールバック
        raw = entry.get('published') or entry.get('updated', '')
        if not raw:
            return None

        for fmt in (
            "%a, %d %b %Y %H:%M:%S %z",   # RFC 2822
            "%Y-%m-%dT%H:%M:%S%z",          # ISO 8601
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(raw.strip(), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue
        return None

    # ── 重複排除 ──────────────────────────────────────────

    @staticmethod
    def _normalize_url(url: str) -> str:
        """URL を正規化して比較しやすくする"""
        parsed = urlparse(url)
        # クエリパラメータからトラッキング系を除外
        qs = parse_qs(parsed.query)
        tracking_keys = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'ref'}
        cleaned = {k: v for k, v in qs.items() if k not in tracking_keys}
        clean_query = urlencode(cleaned, doseq=True)
        return urlunparse((
            parsed.scheme, parsed.netloc, parsed.path.rstrip('/'),
            parsed.params, clean_query, '',
        ))

    @staticmethod
    def _title_similarity(a: str, b: str) -> float:
        """タイトル同士の類似度を返す (0.0〜1.0)"""
        return SequenceMatcher(None, a, b).ratio()

    def _deduplicate_articles(self, articles: list, threshold: float = 0.75) -> list:
        """URL とタイトル類似度で重複記事を排除する

        Args:
            articles: 記事リスト
            threshold: タイトル類似度の閾値（これ以上で重複とみなす）
        """
        seen_urls: set[str] = set()
        unique: list = []

        for article in articles:
            norm_url = self._normalize_url(article.get('link', ''))

            # URL 完全一致チェック
            if norm_url and norm_url in seen_urls:
                logger.debug("重複(URL): %s", article.get('title', ''))
                continue

            # タイトル類似度チェック
            title = article.get('title', '')
            is_dup = False
            for kept in unique:
                if self._title_similarity(title, kept.get('title', '')) >= threshold:
                    logger.debug(
                        "重複(タイトル): '%s' ≈ '%s'",
                        title, kept.get('title', ''),
                    )
                    is_dup = True
                    break

            if is_dup:
                continue

            if norm_url:
                seen_urls.add(norm_url)
            unique.append(article)

        return unique
    
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
            logger.warning("Webコンテンツ取得エラー (%s): %s", url, e)
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
            logger.error("コンテンツ保存エラー: %s", e)
            return None
    
    def load_content(self, filename):
        """保存されたコンテンツを読み込み"""
        filepath = os.path.join(self.content_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning("コンテンツ読み込みエラー: %s", e)
            return ""
    
    def create_daily_content(self, topic_keywords=None):
        """日次コンテンツを作成"""
        logger.info("RSSフィードから記事を取得中...")
        articles = self.fetch_rss_feeds()

        if not articles:
            logger.warning("記事が取得できませんでした。")
            return None

        logger.info("%d記事を取得しました。", len(articles))
        
        # ポッドキャスト用に処理
        podcast_content = self.process_articles_for_podcast(articles, topic_keywords)
        
        # 保存
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"daily_podcast_{timestamp}.txt"
        filepath = self.save_content(podcast_content, filename)
        
        if filepath:
            logger.info("コンテンツを保存しました: %s", filepath)
            return filepath
        else:
            return None
    
    def get_trending_topics(self, articles):
        """記事からトレンドトピックを抽出"""
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    content_manager = ContentManager()
    
    # 日次コンテンツ作成
    content_file = content_manager.create_daily_content(['AI', 'テクノロジー', 'プログラミング'])
    
    if content_file:
        # 生成されたコンテンツを確認
        content = content_manager.load_content(os.path.basename(content_file))
        print("生成されたポッドキャストコンテンツ:")
        print(content[:500] + "..." if len(content) > 500 else content)