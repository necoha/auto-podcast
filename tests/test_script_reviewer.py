# pyright: reportPrivateUsage=false

import json
import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, patch

import httpx
from google import genai
from google.genai import types
from google.genai._gaos.types import interactions as interaction_types

from script_generator import ScriptLine
from script_reviewer import ArticleFactCard, FactVerificationError, ScriptReviewer


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
    reviewer.fact_card_model_interval_seconds = 0.0
    reviewer.last_verification_urls = []
    cast(Any, reviewer).client = SimpleNamespace(
        models=SimpleNamespace(generate_content=Mock(side_effect=responses))
    )
    cast(Any, reviewer).interactions_client = SimpleNamespace(
        interactions=SimpleNamespace(create=Mock(side_effect=responses))
    )
    return reviewer


def _fact_card_response(
    cards: list[dict[str, Any]],
    url_statuses: list[tuple[str, str]],
    *,
    supported: bool = True,
) -> SimpleNamespace:
    text = json.dumps(cards, ensure_ascii=False)
    successful_urls = [
        url
        for url, status in url_statuses
        if status == "URL_RETRIEVAL_STATUS_SUCCESS"
    ]
    annotations = []
    if supported:
        for card, url in zip(cards, successful_urls):
            card_text = json.dumps(card, ensure_ascii=False)
            start = text.index(card_text)
            annotations.append(SimpleNamespace(
                type="url_citation",
                url=url,
                start_index=start,
                end_index=start + len(card_text),
            ))
    return SimpleNamespace(
        status="completed",
        steps=[
            SimpleNamespace(
                type="url_context_result",
                result=[
                    SimpleNamespace(
                        url=url,
                        status=status.removeprefix("URL_RETRIEVAL_STATUS_").lower(),
                    )
                    for url, status in url_statuses
                ],
            ),
            SimpleNamespace(
                type="model_output",
                content=[SimpleNamespace(
                    type="text",
                    text=text,
                    annotations=annotations,
                )],
            ),
        ],
    )


def _fact_card(article_number: int) -> dict[str, Any]:
    return {
        "article_number": article_number,
        "summary": f"記事{article_number}の要約です。",
        "key_facts": [f"記事{article_number}の重要な事実です。"],
        "background": f"記事{article_number}の背景です。",
        "impact": f"記事{article_number}の影響です。",
    }


class UrlContextReviewTests(unittest.TestCase):
    def test_fact_cards_keep_partial_url_success(self):
        articles = [
            {
                "title": f"記事{index}",
                "source": f"媒体{index}",
                "link": f"https://example.com/{index}",
            }
            for index in range(1, 4)
        ]
        response = _fact_card_response(
            [_fact_card(1), _fact_card(3)],
            [
                ("https://example.com/1", "URL_RETRIEVAL_STATUS_SUCCESS"),
                ("https://example.com/2", "URL_RETRIEVAL_STATUS_ERROR"),
                ("https://example.com/3", "URL_RETRIEVAL_STATUS_SUCCESS"),
            ],
        )
        reviewer = _reviewer(response)

        cards = reviewer.extract_fact_cards(articles, batch_size=5)

        self.assertEqual(set(cards), {"https://example.com/1", "https://example.com/3"})
        self.assertIsInstance(cards["https://example.com/1"], ArticleFactCard)
        self.assertEqual(
            reviewer.last_retrieval_statuses["https://example.com/2"],
            "URL_RETRIEVAL_STATUS_ERROR",
        )
        self.assertEqual(reviewer.fact_card_request_count, 1)

    def test_sdk_fact_card_metadata_is_supported(self):
        card_data = _fact_card(1)
        text = json.dumps([card_data], ensure_ascii=False)
        card_text = json.dumps(card_data, ensure_ascii=False)
        start = text.index(card_text)
        response = interaction_types.Interaction(
            id="test-interaction",
            status="completed",
            steps=[
                interaction_types.URLContextResultStep(
                    call_id="url-call-1",
                    result=[interaction_types.URLContextResult(
                        url="https://example.com/1",
                        status="success",
                    )],
                ),
                interaction_types.ModelOutputStep(
                    content=[interaction_types.TextContent(
                        text=text,
                        annotations=[interaction_types.URLCitation(
                            url="https://example.com/1",
                            start_index=start,
                            end_index=start + len(card_text),
                        )],
                    )],
                ),
            ],
        )
        reviewer = _reviewer(response)

        cards = reviewer.extract_fact_cards([
            {
                "title": "記事1",
                "source": "媒体1",
                "link": "https://example.com/1",
            }
        ])

        self.assertEqual(set(cards), {"https://example.com/1"})
        self.assertEqual(cards["https://example.com/1"].summary, "記事1の要約です。")

    def test_google_genai_v2_serializes_and_parses_fact_card_interaction(self):
        captured: dict[str, Any] = {}
        card = _fact_card(1)
        text = json.dumps([card], ensure_ascii=False)
        card_text = json.dumps(card, ensure_ascii=False)
        start = text.index(card_text)

        def handle_request(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "id": "test-interaction",
                    "status": "completed",
                    "steps": [
                        {
                            "type": "url_context_result",
                            "call_id": "url-call-1",
                            "result": [{
                                "url": "https://example.com/1",
                                "status": "success",
                            }],
                        },
                        {
                            "type": "model_output",
                            "content": [{
                                "type": "text",
                                "text": text,
                                "annotations": [{
                                    "type": "url_citation",
                                    "url": "https://example.com/1",
                                    "start_index": start,
                                    "end_index": start + len(card_text),
                                }],
                            }],
                        },
                    ],
                },
            )

        reviewer = ScriptReviewer.__new__(ScriptReviewer)
        reviewer.models = ("gemini-3.8-flash",)
        reviewer.model = reviewer.models[0]
        cast(Any, reviewer).interactions_client = genai.Client(
            api_key="test-key",
            http_options=types.HttpOptions(
                httpx_client=httpx.Client(
                    transport=httpx.MockTransport(handle_request)
                ),
                retry_options=types.HttpRetryOptions(attempts=-1),
            ),
        )

        cards = reviewer.extract_fact_cards([{
            "title": "記事1",
            "source": "媒体1",
            "link": "https://example.com/1",
        }])

        self.assertEqual(set(cards), {"https://example.com/1"})
        self.assertTrue(captured["url"].endswith("/v1beta/interactions"))
        self.assertEqual(captured["body"]["tools"], [{"type": "url_context"}])
        self.assertEqual(
            captured["body"]["response_format"]["mime_type"],
            "application/json",
        )
        self.assertIn("## 取得対象記事", captured["body"]["input"])

    def test_fact_card_without_citation_is_rejected(self):
        articles = [
            {
                "title": "記事1",
                "source": "媒体1",
                "link": "https://example.com/1",
            }
        ]
        response = _fact_card_response(
            [_fact_card(1)],
            [("https://example.com/1", "URL_RETRIEVAL_STATUS_SUCCESS")],
            supported=False,
        )
        reviewer = _reviewer(response)

        cards = reviewer.extract_fact_cards(articles)

        self.assertEqual(cards, {})
        self.assertEqual(
            reviewer.last_retrieval_statuses["https://example.com/1"],
            "CARD_UNVERIFIED",
        )

    def test_fact_card_cannot_use_another_articles_citation(self):
        articles = [
            {
                "title": "記事1",
                "source": "媒体1",
                "link": "https://example.com/1",
            },
            {
                "title": "記事2",
                "source": "媒体2",
                "link": "https://example.com/2",
            },
        ]
        text = json.dumps([_fact_card(1), _fact_card(2)], ensure_ascii=False)
        second_card_text = json.dumps(_fact_card(2), ensure_ascii=False)
        second_start = text.index(second_card_text)
        response = SimpleNamespace(status="completed", steps=[
            SimpleNamespace(
                type="url_context_result",
                result=[
                    SimpleNamespace(url="https://example.com/1", status="success"),
                    SimpleNamespace(url="https://example.com/2", status="success"),
                ],
            ),
            SimpleNamespace(
                type="model_output",
                content=[SimpleNamespace(
                    type="text",
                    text=text,
                    annotations=[SimpleNamespace(
                        type="url_citation",
                        url="https://example.com/2",
                        start_index=second_start,
                        end_index=second_start + len(second_card_text),
                    )],
                )],
            ),
        ])
        reviewer = _reviewer(response)

        cards = reviewer.extract_fact_cards(articles)

        self.assertEqual(set(cards), {"https://example.com/2"})
        self.assertEqual(
            reviewer.last_retrieval_statuses["https://example.com/1"],
            "CARD_UNVERIFIED",
        )

    def test_redirected_url_status_maps_by_request_order(self):
        article = {
            "title": "記事1",
            "source": "媒体1",
            "link": "https://example.com/original",
        }
        response = _fact_card_response(
            [_fact_card(1)],
            [("https://cdn.example.net/final", "URL_RETRIEVAL_STATUS_SUCCESS")],
        )
        reviewer = _reviewer(response)

        cards = reviewer.extract_fact_cards([article])

        self.assertEqual(set(cards), {"https://example.com/original"})
        self.assertEqual(
            reviewer.last_retrieval_statuses["https://example.com/original"],
            "VERIFIED",
        )

    def test_fact_card_batches_preserve_earlier_success(self):
        articles = [
            {
                "title": f"記事{index}",
                "source": f"媒体{index}",
                "link": f"https://example.com/{index}",
            }
            for index in range(1, 7)
        ]
        first_batch = _fact_card_response(
            [_fact_card(1), _fact_card(2), _fact_card(3)],
            [
                (f"https://example.com/{index}", "URL_RETRIEVAL_STATUS_SUCCESS")
                for index in range(1, 4)
            ],
        )
        reviewer = _reviewer(first_batch, RuntimeError("503 UNAVAILABLE"))

        cards = reviewer.extract_fact_cards(articles, batch_size=3)

        self.assertEqual(set(cards), {f"https://example.com/{index}" for index in range(1, 4)})
        self.assertEqual(reviewer.fact_card_request_count, 2)
        for index in range(4, 7):
            self.assertEqual(
                reviewer.last_retrieval_statuses[f"https://example.com/{index}"],
                "BATCH_ERROR",
            )

    def test_twenty_articles_are_split_into_four_batches(self):
        articles = [
            {
                "title": f"記事{index}",
                "source": f"媒体{index}",
                "link": f"https://example.com/{index}",
            }
            for index in range(1, 21)
        ]
        responses = []
        for batch_start in range(1, 21, 5):
            responses.append(_fact_card_response(
                [_fact_card(index) for index in range(batch_start, batch_start + 5)],
                [
                    (f"https://example.com/{index}", "URL_RETRIEVAL_STATUS_SUCCESS")
                    for index in range(batch_start, batch_start + 5)
                ],
            ))
        reviewer = _reviewer(*responses)

        cards = reviewer.extract_fact_cards(articles, batch_size=5)

        self.assertEqual(len(cards), 20)
        self.assertEqual(reviewer.fact_card_request_count, 4)
        self.assertEqual(
            reviewer.interactions_client.interactions.create.call_count,
            4,
        )

    def test_fact_card_requests_are_spaced_per_model(self):
        last_request_at: dict[str, float] = {}

        with (
            patch("script_reviewer.time.monotonic", side_effect=[100.0, 103.0]),
            patch("script_reviewer.time.sleep") as sleep,
        ):
            ScriptReviewer._wait_for_model_interval("gemini-3.8-flash", last_request_at)
            ScriptReviewer._wait_for_model_interval("gemini-3.8-flash", last_request_at)

        sleep.assert_called_once_with(9.0)
        self.assertEqual(last_request_at["gemini-3.8-flash"], 112.0)

    def test_fact_card_prompt_does_not_include_rss_summary(self):
        prompt = ScriptReviewer._build_fact_card_prompt(
            [
                (
                    1,
                    {
                        "title": "記事タイトル",
                        "source": "媒体",
                        "link": "https://example.com/article",
                        "summary": "RSSから取得した本文断片",
                    },
                )
            ]
        )

        self.assertIn("記事タイトル", prompt)
        self.assertIn("https://example.com/article", prompt)
        self.assertNotIn("RSSから取得した本文断片", prompt)

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