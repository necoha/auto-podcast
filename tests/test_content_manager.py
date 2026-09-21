import unittest
from datetime import datetime, timedelta, timezone

from content_manager import ContentManager


class ContentManagerTests(unittest.TestCase):
    def test_limit_articles_keeps_the_newest_items(self):
        base_time = datetime(2026, 9, 21, tzinfo=timezone.utc)
        articles = [
            {
                "title": f"記事{i}",
                "published_dt": base_time + timedelta(minutes=i),
            }
            for i in range(25)
        ]

        limited = ContentManager._limit_articles(articles, 20)

        self.assertEqual(len(limited), 20)
        self.assertEqual(limited[0]["title"], "記事24")
        self.assertEqual(limited[-1]["title"], "記事5")

    def test_limit_articles_preserves_short_lists(self):
        articles = [{"title": "記事A"}, {"title": "記事B"}]

        self.assertIs(ContentManager._limit_articles(articles, 20), articles)


if __name__ == "__main__":
    unittest.main()