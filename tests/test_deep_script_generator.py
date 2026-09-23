# pyright: reportPrivateUsage=false

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from deep_script_generator import DeepScriptGenerator


ARTICLES = [
    {
        "title": f"記事{index}",
        "source": f"媒体{index}",
        "link": f"https://example.com/{index}",
    }
    for index in range(1, 6)
]


class DeepArticleSelectionTests(unittest.TestCase):
    def _generator(self, response_data) -> tuple[DeepScriptGenerator, Mock]:
        generate_content = Mock(
            return_value=SimpleNamespace(text=json.dumps(response_data))
        )
        generator = DeepScriptGenerator.__new__(DeepScriptGenerator)
        generator.client = SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content)
        )
        generator.model = "gemini-3.8-flash"
        generator.max_topics = 3
        return generator, generate_content

    def test_select_articles_returns_only_selected_three(self):
        generator, generate_content = self._generator([4, 1, 3])

        selected = generator.select_articles(
            ARTICLES,
            model="gemini-3.7-flash",
        )

        self.assertEqual(
            [article["link"] for article in selected],
            [
                "https://example.com/4",
                "https://example.com/1",
                "https://example.com/3",
            ],
        )
        self.assertEqual(
            generate_content.call_args.kwargs["model"],
            "gemini-3.7-flash",
        )

    def test_selection_rejects_wrong_count(self):
        generator, _ = self._generator([1, 2])

        with self.assertRaisesRegex(ValueError, "2/3"):
            generator.select_articles(ARTICLES)

    def test_selection_rejects_out_of_range_index(self):
        generator, _ = self._generator([1, 2, 9])

        with self.assertRaisesRegex(ValueError, "範囲外"):
            generator.select_articles(ARTICLES)


if __name__ == "__main__":
    unittest.main()