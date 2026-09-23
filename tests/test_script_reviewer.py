# pyright: reportPrivateUsage=false

import json
import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, patch

from google.genai import types

from script_generator import ScriptLine
from script_reviewer import FactVerificationError, ScriptReviewer


def _verified_response(text: str, *, supported: bool = True) -> SimpleNamespace:
    support = []
    if supported:
        claim = json.loads(text)[0]["text"]
        encoded_claim = json.dumps(claim, ensure_ascii=False)[1:-1]
        start = text.index(encoded_claim)
        support = [
            SimpleNamespace(
                segment=SimpleNamespace(
                    start_index=start,
                    end_index=start + len(encoded_claim),
                )
            )
        ]
    metadata = SimpleNamespace(
        grounding_chunks=[
            SimpleNamespace(web=SimpleNamespace(uri="https://example.com/fact"))
        ],
        grounding_supports=support,
    )
    return SimpleNamespace(
        text=text,
        candidates=[
            SimpleNamespace(
                grounding_metadata=metadata,
                url_context_metadata=SimpleNamespace(
                    url_metadata=[
                        SimpleNamespace(
                            retrieved_url="https://example.com/fact",
                            url_retrieval_status=(
                                "URL_RETRIEVAL_STATUS_SUCCESS"
                            ),
                        )
                    ]
                ),
            )
        ],
    )


def _reviewer(*responses: Any) -> ScriptReviewer:
    reviewer = ScriptReviewer.__new__(ScriptReviewer)
    reviewer.model = "test-model"
    reviewer.last_verification_urls = []
    cast(Any, reviewer).client = SimpleNamespace(
        models=SimpleNamespace(generate_content=Mock(side_effect=responses))
    )
    return reviewer


class UrlContextReviewTests(unittest.TestCase):
    def test_review_uses_url_context(self):
        config = ScriptReviewer._review_config()
        config_data = config.model_dump(exclude_none=True)
        tools = cast(list[dict[str, Any]], config_data["tools"])

        self.assertIn("url_context", tools[0])
        self.assertEqual(config.temperature, 0)

    def test_sdk_url_context_metadata_is_supported(self):
        response = types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=types.Content(parts=[types.Part(text="[]")]),
                    url_context_metadata=types.UrlContextMetadata(
                        url_metadata=[
                            types.UrlMetadata(
                                retrieved_url="https://example.com/article",
                                url_retrieval_status=(
                                    types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS
                                ),
                            )
                        ]
                    ),
                    grounding_metadata=types.GroundingMetadata(
                        grounding_supports=[
                            types.GroundingSupport(
                                segment=types.Segment(start_index=1, end_index=2)
                            )
                        ]
                    ),
                )
            ]
        )

        urls, ranges = ScriptReviewer._extract_url_context_evidence(response)

        self.assertEqual(urls, ["https://example.com/article"])
        self.assertEqual(ranges, [(1, 2)])

    def test_grounded_numeric_claim_is_accepted(self):
        text = json.dumps(
            [{"speaker": "A", "text": '"預金金利"は0.5%です。'}],
            ensure_ascii=False,
        )
        reviewer = _reviewer(_verified_response(text))

        reviewed = reviewer.review(
            [ScriptLine(speaker="A", text="預金金利は0.5%です。")],
            [{"title": "預金金利は0.5%に", "source": "新聞", "link": "https://example.com"}],
        )

        self.assertEqual(reviewed[0].text, '"預金金利"は0.5%です。')
        self.assertEqual(reviewer.last_verification_urls, ["https://example.com/fact"])

    def test_transient_failure_switches_review_model(self):
        text = json.dumps(
            [{"speaker": "A", "text": "確認済みのニュースです。"}],
            ensure_ascii=False,
        )
        reviewer = _reviewer(
            RuntimeError("503 UNAVAILABLE"),
            _verified_response(text),
        )
        reviewer.models = (
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
        )

        with patch("script_reviewer.time.sleep") as sleep:
            reviewed = reviewer.review(
                [ScriptLine(speaker="A", text="元台本です。")],
                [
                    {
                        "title": "記事",
                        "source": "新聞",
                        "link": "https://example.com/fact",
                    }
                ],
                preferred_model="gemini-3.7-flash",
            )

        generate_content = reviewer.client.models.generate_content
        self.assertEqual(reviewed[0].text, "確認済みのニュースです。")
        self.assertEqual(
            [call.kwargs["model"] for call in generate_content.call_args_list],
            ["gemini-3.7-flash", "gemini-3.6-flash"],
        )
        sleep.assert_not_called()

    def test_rate_limit_does_not_switch_review_model(self):
        reviewer = _reviewer(RuntimeError("429 RESOURCE_EXHAUSTED"))
        reviewer.models = (
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
        )

        with self.assertRaises(FactVerificationError):
            reviewer.review(
                [ScriptLine(speaker="A", text="元台本です。")],
                [
                    {
                        "title": "記事",
                        "source": "新聞",
                        "link": "https://example.com/fact",
                    }
                ],
            )

        generate_content = reviewer.client.models.generate_content
        self.assertEqual(generate_content.call_count, 1)
        self.assertEqual(
            generate_content.call_args.kwargs["model"],
            "gemini-3.8-flash",
        )

    def test_ungrounded_numeric_claim_fails_closed(self):
        text = json.dumps(
            [{"speaker": "A", "text": "政策金利は0.5%です。"}],
            ensure_ascii=False,
        )
        reviewer = _reviewer(
            _verified_response(text, supported=False),
            _verified_response(text, supported=False),
        )

        with patch("script_reviewer.time.sleep"):
            with self.assertRaises(FactVerificationError):
                reviewer.review(
                    [ScriptLine(speaker="A", text="政策金利は0.5%です。")],
                    [
                        {
                            "title": "預金金利は0.5%に",
                            "source": "新聞",
                            "link": "https://example.com/fact",
                        }
                    ],
                )

    def test_unsupported_regulation_claim_fails_even_with_other_citation(self):
        text = json.dumps(
            [
                {"speaker": "A", "text": "確認済みのニュースです。"},
                {"speaker": "B", "text": "日本では規制が導入されました。"},
            ],
            ensure_ascii=False,
        )
        supported_text = "確認済みのニュースです。"
        start = text.index(supported_text)
        response = _verified_response(text)
        response.candidates[0].grounding_metadata.grounding_supports = [
            SimpleNamespace(
                segment=SimpleNamespace(
                    start_index=start,
                    end_index=start + len(supported_text),
                )
            )
        ]
        reviewer = _reviewer(response, response)

        with patch("script_reviewer.time.sleep"):
            with self.assertRaises(FactVerificationError):
                reviewer.review(
                    [ScriptLine(speaker="A", text="元台本です。")],
                    [
                        {
                            "title": "記事",
                            "source": "新聞",
                            "link": "https://example.com/fact",
                        }
                    ],
                )

    def test_citation_on_same_line_must_cover_numeric_value(self):
        claim = "日本銀行の政策金利は0.5%です。"
        text = json.dumps(
            [{"speaker": "A", "text": claim}],
            ensure_ascii=False,
        )
        line_start = text.index(claim)
        response = _verified_response(text)
        response.candidates[0].grounding_metadata.grounding_supports = [
            SimpleNamespace(
                segment=SimpleNamespace(
                    start_index=line_start,
                    end_index=line_start + len("日本銀行の政策金利は"),
                )
            )
        ]
        reviewer = _reviewer(response, response)

        with self.assertRaisesRegex(FactVerificationError, "0.5%"):
            reviewer.review(
                [ScriptLine(speaker="A", text="元台本です。")],
                [
                    {
                        "title": "記事",
                        "source": "新聞",
                        "link": "https://example.com/fact",
                    }
                ],
            )

    def test_generic_factual_line_requires_citation(self):
        text = json.dumps(
            [
                {"speaker": "A", "text": "なるほど。"},
                {"speaker": "B", "text": "世界モデル企業は秘密が多いです。"},
            ],
            ensure_ascii=False,
        )
        conversational_text = "なるほど。"
        start = text.index(conversational_text)
        response = _verified_response(text)
        response.candidates[0].grounding_metadata.grounding_supports = [
            SimpleNamespace(
                segment=SimpleNamespace(
                    start_index=start,
                    end_index=start + len(conversational_text),
                )
            )
        ]
        reviewer = _reviewer(response, response)

        with self.assertRaisesRegex(FactVerificationError, "事実行"):
            reviewer.review(
                [ScriptLine(speaker="A", text="元台本です。")],
                [
                    {
                        "title": "記事",
                        "source": "新聞",
                        "link": "https://example.com/fact",
                    }
                ],
            )

    def test_permanent_api_error_is_not_retried(self):
        reviewer = _reviewer(RuntimeError("400 API_KEY_INVALID"))

        with self.assertRaises(FactVerificationError):
            reviewer.review(
                [ScriptLine(speaker="A", text="元台本です。")],
                [
                    {
                        "title": "記事",
                        "source": "新聞",
                        "link": "https://example.com/fact",
                    }
                ],
            )

        generate_content = cast(
            Mock,
            cast(Any, reviewer).client.models.generate_content,
        )
        self.assertEqual(generate_content.call_count, 1)

    def test_episode_date_does_not_require_article_citation(self):
        text = json.dumps(
            [
                {
                    "speaker": "A",
                    "text": "2026年9月21日のニュースをお届けします。",
                },
                {"speaker": "B", "text": "確認済みのニュースです。"},
            ],
            ensure_ascii=False,
        )
        response = _verified_response(text)
        supported_text = "確認済みのニュースです。"
        start = text.index(supported_text)
        response.candidates[0].grounding_metadata.grounding_supports = [
            SimpleNamespace(
                segment=SimpleNamespace(
                    start_index=start,
                    end_index=start + len(supported_text),
                )
            )
        ]
        reviewer = _reviewer(response)

        reviewed = reviewer.review(
            [ScriptLine(speaker="A", text="元台本です。")],
            [
                {
                    "title": "記事",
                    "source": "新聞",
                    "link": "https://example.com/fact",
                }
            ],
        )

        self.assertEqual(len(reviewed), 2)

    def test_deep_review_does_not_add_unselected_articles(self):
        reviewer = _reviewer()
        prompt = reviewer._build_review_prompt(
            [ScriptLine(speaker="A", text="選んだ記事です。")],
            [{"title": "記事", "source": "新聞", "link": "https://example.com"}],
            require_all_articles=False,
        )
        system_instruction = cast(str, reviewer._review_config().system_instruction)

        self.assertIn("台本で選ばれていない記事を追加しない", prompt)
        self.assertIn("中央銀行の政策金利と民間銀行の預金金利", system_instruction)
        self.assertIn("年と月", system_instruction)

    def test_review_rejects_more_than_twenty_urls(self):
        reviewer = _reviewer()
        articles = [
            {
                "title": f"記事{index}",
                "source": "新聞",
                "link": f"https://example.com/{index}",
            }
            for index in range(21)
        ]

        with self.assertRaisesRegex(FactVerificationError, "21/20"):
            reviewer._build_review_prompt(
                [ScriptLine(speaker="A", text="台本です。")],
                articles,
            )

    def test_review_rejects_article_without_url(self):
        reviewer = _reviewer()

        with self.assertRaisesRegex(FactVerificationError, "URLがない記事"):
            reviewer._build_review_prompt(
                [ScriptLine(speaker="A", text="台本です。")],
                [{"title": "記事", "source": "新聞"}],
            )

    def test_url_retrieval_failure_fails_closed(self):
        text = json.dumps(
            [{"speaker": "A", "text": "確認済みのニュースです。"}],
            ensure_ascii=False,
        )
        response = _verified_response(text)
        response.candidates[0].url_context_metadata.url_metadata[0].url_retrieval_status = (
            "URL_RETRIEVAL_STATUS_ERROR"
        )
        reviewer = _reviewer(response, response)

        with self.assertLogs("script_reviewer", level="INFO") as logs:
            with self.assertRaises(FactVerificationError):
                reviewer.review(
                    [ScriptLine(speaker="A", text="元台本です。")],
                    [
                        {
                            "title": "記事",
                            "source": "新聞",
                            "link": "https://example.com/fact",
                        }
                    ],
                )

        output = "\n".join(logs.output)
        self.assertIn("URL Context検証対象: https://example.com/fact", output)
        self.assertIn("status=URL_RETRIEVAL_STATUS_ERROR", output)
        self.assertIn("url=https://example.com/fact", output)

    def test_partial_url_retrieval_fails_closed(self):
        text = json.dumps(
            [{"speaker": "A", "text": "確認済みのニュースです。"}],
            ensure_ascii=False,
        )
        response = _verified_response(text)
        reviewer = _reviewer(response, response)
        articles = [
            {
                "title": "記事A",
                "source": "新聞",
                "link": "https://example.com/a",
            },
            {
                "title": "記事B",
                "source": "新聞",
                "link": "https://example.com/b",
            },
        ]

        with self.assertRaisesRegex(FactVerificationError, "1/2"):
            reviewer.review(
                [ScriptLine(speaker="A", text="元台本です。")],
                articles,
            )


if __name__ == "__main__":
    unittest.main()