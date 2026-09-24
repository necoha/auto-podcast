"""
台本セルフレビューモジュール
生成された台本をURL Contextで元記事と照合してレビューし、
事実確認できない台本を配信経路へ通さない。
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlparse

from google import genai
from google.genai import types

import config
from script_generator import Script, ScriptLine

logger = logging.getLogger(__name__)

MAX_REVIEW_ATTEMPTS = 2
MAX_URL_CONTEXT_URLS = 20
URL_CONTEXT_MODEL_INTERVAL_SECONDS = 12.0
TRANSIENT_REVIEW_ERROR_MARKERS = (
    "500",
    "502",
    "503",
    "504",
    "unavailable",
    "timed out",
    "timeout",
)


@dataclass(frozen=True)
class ArticleFactCard:
        """URL Contextの引用で裏付けられた速報記事の要点。"""

        title: str
        source: str
        url: str
        summary: str
        key_facts: List[str]
        background: str
        impact: str

        def as_prompt_data(self) -> Dict[str, Any]:
                return {
                        "summary": self.summary,
                        "key_facts": self.key_facts,
                        "background": self.background,
                        "impact": self.impact,
                }


FACT_CARD_SYSTEM_PROMPT = """\
あなたはニュースの事実抽出担当です。
指定された各URLをURL Contextで取得し、速報ポッドキャスト用の短い事実カードを作成してください。

ルール:
- 取得に成功した記事だけを出力する
- 記事本文で確認できる情報だけを使う
- 推測、一般知識、別記事の情報を補わない
- 原文を長く引用せず、日本語で簡潔に言い換える
- summary、key_facts、background、impactの各文字列に元記事の引用を付ける
- 数値、年月、価格、割合、制度情報は元記事と完全一致させる
- backgroundまたはimpactを確認できない場合は空文字にせず、その項目を裏付けられる短い事実に限定する

出力は次のJSON配列だけにする:
[
    {
        "article_number": 1,
        "summary": "何が起きたかを1文で説明",
        "key_facts": ["重要な事実1", "重要な事実2"],
        "background": "確認できた背景を1文で説明",
        "impact": "確認できた影響を1文で説明"
    }
]
"""

FACT_CARD_RESPONSE_FORMAT = {
    "type": "text",
    "mime_type": "application/json",
    "schema": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "article_number": {"type": "integer"},
                "summary": {"type": "string"},
                "key_facts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 3,
                },
                "background": {"type": "string"},
                "impact": {"type": "string"},
            },
            "required": [
                "article_number",
                "summary",
                "key_facts",
                "background",
                "impact",
            ],
            "additionalProperties": False,
        },
    },
}
HIGH_RISK_FACT_PATTERN = re.compile(
    r"\d+(?:[.,]\d+)?(?:[%％年月日円ドル人件倍兆億万])?"
    r"|施行|導入|開始|解除|引き上げ|引き下げ|利上げ|利下げ"
    r"|創設|廃止|決定|発表|成立|公布|発効"
)
NON_FACTUAL_LINE_PATTERNS = (
    re.compile(r".*この番組はAIによって自動生成されています.*"),
    re.compile(
        r"(?:おはようございます、[^。]+です。)?"
        r"20\d{2}年\d{1,2}月\d{1,2}日の"
        r"(?:ニュース|テック速報)(?:をお届けします|です)[。 ]*"
    ),
    re.compile(r".*おはようございます.*(?:です|お願いします)[。！! ]*"),
    re.compile(r".*(?:ありがとう|どういたしまして).*"),
    re.compile(r".*また明日お会いしましょう.*"),
    re.compile(r".*以上、本日の.*(?:ニュース|見出し).*でした.*"),
    re.compile(r"(?:なるほど|そうですね|たしかに|驚きですね|興味深いですね)[。！! ]*"),
    re.compile(r"(?:では|それでは|続いて|次に|最後に).{0,40}(?:お願いします|見ていきましょう)[。?？ ]*"),
    re.compile(r".*\d+つのテーマです[。 ]*"),
)

REVIEW_SYSTEM_PROMPT = """\
あなたはポッドキャスト台本の品質レビュアーです。
与えられた台本を以下の6項目でチェックし、問題があれば修正してください。

## チェック項目

1. **フォーマット不正**: speakerは"A"または"B"のみ。textは空でないこと。
2. **不自然な会話**: 同じフレーズの過度な繰り返し、唐突な話題転換、会話のつながりの不自然さを修正。
3. **記事カバレッジ**: ユーザープロンプトのカバレッジ指示に従う。速報版は全記事を確認し、深掘り版は選択済みトピックだけを検証して未選択記事を追加しない。
4. **読み上げ不適切な表現**: URL（https://...）、コードスニペット、過度な括弧表現、記号の羅列など、音声で聞いて不自然になる表現を自然な日本語に置き換える。
5. **長さの偏り**: 特定トピックだけ極端に長い/短い場合、バランスを調整する。
6. **事実整合性**: URL Contextで元記事を確認し、記事タイトル・URL・取得内容で裏付けられない主張を削除または訂正する。

## ルール

- 修正が不要な場合は、元の台本をそのまま返してください。
- 大幅な書き換えは避け、最小限の修正にとどめてください。
- speakerの"A"/"B"は変更しないでください。
- 会話の自然な流れを維持してください。
- 挨拶・相槌・質問と事実説明を同じtextへ混在させず、別々の発話行にしてください。
- モデルの記憶や一般知識を根拠にせず、提供された元記事URLの取得内容だけを根拠にしてください。
- 数値、年月、価格、割合、制度開始時期は元記事の取得内容と完全一致する場合だけ残してください。
- 主体と指標を混同しないでください。中央銀行の政策金利と民間銀行の預金金利は別の指標です。
- 法律・規制・制度の開始時期に触れる場合は年と月を確認してください。確認できない場合はその主張自体を削除してください。
- タイトルから背景・因果関係・海外比較を推測して補完しないでください。
- 裏付けのない情報を「可能性があります」などの曖昧表現へ変えて残すことも禁止します。
- 修正のために新しい事実を追加する場合も、検索結果による裏付けが必要です。
- 出力は必ずJSON配列形式で返してください。
"""


class FactVerificationError(RuntimeError):
    """元記事の引用証跡付き事実確認を完了できなかったことを示す。"""


class ScriptReviewer:
    """生成済み台本をLLMでレビュー・修正するクラス"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.models = (
            (model,)
            if model
            else config.LLM_MODELS
        )
        self.model = self.models[0]
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                timeout=config.GEMINI_LLM_TIMEOUT_MS,
                retry_options=types.HttpRetryOptions(
                    attempts=config.GEMINI_SDK_MAX_ATTEMPTS,
                ),
            ),
        )
        self.interactions_client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                timeout=config.GEMINI_LLM_TIMEOUT_MS,
                retry_options=types.HttpRetryOptions(
                    attempts=config.GEMINI_INTERACTIONS_MAX_RETRIES,
                ),
            ),
        )
        self.last_verification_urls: List[str] = []
        self.last_retrieval_statuses: Dict[str, str] = {}
        self.fact_card_request_count = 0
        self.fact_card_elapsed_seconds = 0.0
        self.fact_card_model_interval_seconds = URL_CONTEXT_MODEL_INTERVAL_SECONDS

    def extract_fact_cards(
        self,
        articles: List[Dict[str, Any]],
        *,
        batch_size: int = config.URL_CONTEXT_BATCH_SIZE,
        preferred_model: Optional[str] = None,
    ) -> Dict[str, ArticleFactCard]:
        """記事URLを小分けに取得し、引用付き事実カードをURL別に返す。"""
        if batch_size < 1:
            raise ValueError("URL Contextのバッチサイズは1以上が必要です")

        article_urls = self._article_urls(articles)
        if len(article_urls) != len(articles):
            raise FactVerificationError(
                "URLがない記事、または重複URLの記事が含まれています"
            )
        if len(article_urls) > MAX_URL_CONTEXT_URLS:
            raise FactVerificationError(
                f"URL Contextの上限を超えています "
                f"({len(article_urls)}/{MAX_URL_CONTEXT_URLS})"
            )

        self.last_verification_urls = []
        self.last_retrieval_statuses = {
            article_url: "NOT_ATTEMPTED" for article_url in article_urls
        }
        self.fact_card_request_count = 0
        started_at = time.monotonic()
        cards: Dict[str, ArticleFactCard] = {}
        indexed_articles = list(enumerate(articles, 1))
        models = self._ordered_models(preferred_model)
        last_request_at_by_model: Dict[str, float] = {}

        for batch_start in range(0, len(indexed_articles), batch_size):
            batch = indexed_articles[batch_start:batch_start + batch_size]
            batch_number = batch_start // batch_size + 1
            batch_cards: Dict[str, ArticleFactCard] = {}

            for attempt, model in enumerate(models):
                try:
                    self._wait_for_model_interval(
                        model,
                        last_request_at_by_model,
                        getattr(
                            self,
                            "fact_card_model_interval_seconds",
                            URL_CONTEXT_MODEL_INTERVAL_SECONDS,
                        ),
                    )
                    self.fact_card_request_count += 1
                    logger.info(
                        "速報事実カード取得 (バッチ%d, %d件, モデル:%s, 試行%d/%d)",
                        batch_number,
                        len(batch),
                        model,
                        attempt + 1,
                        len(models),
                    )
                    response = self.interactions_client.interactions.create(
                        model=model,
                        input=self._build_fact_card_prompt(batch),
                        tools=[{"type": "url_context"}],
                        response_format=FACT_CARD_RESPONSE_FORMAT,
                    )
                    batch_cards = self._parse_fact_card_response(response, batch)
                    break
                except Exception as error:
                    is_transient = any(
                        marker in str(error).lower()
                        for marker in TRANSIENT_REVIEW_ERROR_MARKERS
                    )
                    is_retryable = isinstance(error, FactVerificationError) or is_transient
                    if not is_retryable or attempt >= len(models) - 1:
                        logger.warning(
                            "速報事実カードのバッチ%dを取得できませんでした: %s",
                            batch_number,
                            error,
                        )
                        for _, article in batch:
                            article_url = article.get("link", "")
                            if self.last_retrieval_statuses.get(article_url) == "NOT_ATTEMPTED":
                                self.last_retrieval_statuses[article_url] = "BATCH_ERROR"
                        break
                    logger.warning(
                        "速報事実カード取得失敗 (%s)、次のモデル%sへ切り替え: %s",
                        model,
                        models[attempt + 1],
                        error,
                    )

            cards.update(batch_cards)

        self.last_verification_urls = list(cards)
        self.fact_card_elapsed_seconds = time.monotonic() - started_at
        logger.info(
            "速報事実カード取得完了: %d/%d件、API %d回、%.1f秒",
            len(cards),
            len(articles),
            self.fact_card_request_count,
            self.fact_card_elapsed_seconds,
        )
        return cards

    def _ordered_models(self, preferred_model: Optional[str]) -> tuple[str, ...]:
        configured_models = getattr(self, "models", (self.model,))
        if preferred_model in configured_models:
            preferred_index = configured_models.index(preferred_model)
            return configured_models[preferred_index:]
        if preferred_model:
            return tuple(dict.fromkeys((preferred_model, *configured_models)))
        return tuple(configured_models)

    @staticmethod
    def _wait_for_model_interval(
        model: str,
        last_request_at_by_model: Dict[str, float],
        interval_seconds: float = URL_CONTEXT_MODEL_INTERVAL_SECONDS,
    ) -> None:
        now = time.monotonic()
        previous_request_at = last_request_at_by_model.get(model)
        if previous_request_at is None:
            last_request_at_by_model[model] = now
            return

        next_request_at = previous_request_at + interval_seconds
        wait_seconds = max(0.0, next_request_at - now)
        if wait_seconds > 0:
            logger.info(
                "URL Contextレート制御 (%s): %.1f秒待機",
                model,
                wait_seconds,
            )
            time.sleep(wait_seconds)
        last_request_at_by_model[model] = max(now, next_request_at)

    @staticmethod
    def _build_fact_card_prompt(
        indexed_articles: List[tuple[int, Dict[str, Any]]],
    ) -> str:
        lines = [FACT_CARD_SYSTEM_PROMPT, "## 取得対象記事"]
        for article_number, article in indexed_articles:
            lines.append(
                f"{article_number}. {article.get('title', '不明')}"
                f"（{article.get('source', '不明')}） {article.get('link', '')}"
            )
        lines.append("\n各URLを取得し、取得成功記事だけの事実カードを返してください。")
        return "\n".join(lines)

    def _parse_fact_card_response(
        self,
        response: object,
        indexed_articles: List[tuple[int, Dict[str, Any]]],
    ) -> Dict[str, ArticleFactCard]:
        response_text, support_ranges_by_url = (
            self._extract_interaction_text_and_citations(response)
        )
        if not response_text:
            raise FactVerificationError("事実カード応答が空です")

        attempts = self._extract_interaction_url_results(response)
        articles_by_number = dict(indexed_articles)
        successful_original_urls: set[str] = set()
        retrieved_url_by_original: Dict[str, str] = {}
        for position, (_, article) in enumerate(indexed_articles):
            article_url = article.get("link", "")
            if position >= len(attempts):
                continue
            retrieved_url, status = attempts[position]
            self.last_retrieval_statuses[article_url] = status
            if status == "URL_RETRIEVAL_STATUS_SUCCESS":
                successful_original_urls.add(article_url)
                retrieved_url_by_original[article_url] = retrieved_url

        raw_cards = self._parse_fact_card_json(response_text)
        cards: Dict[str, ArticleFactCard] = {}
        for raw_card in raw_cards:
            article_number = raw_card.get("article_number")
            if not isinstance(article_number, int) or isinstance(article_number, bool):
                continue
            article = articles_by_number.get(article_number)
            if article is None:
                continue

            article_url = article.get("link", "")
            if article_url not in successful_original_urls:
                continue
            retrieved_url = retrieved_url_by_original.get(article_url, article_url)
            article_support_ranges = support_ranges_by_url.get(
                self._normalize_url_for_match(retrieved_url),
                [],
            )
            if not article_support_ranges:
                article_support_ranges = support_ranges_by_url.get(
                    self._normalize_url_for_match(article_url),
                    [],
                )
            try:
                card = self._build_verified_fact_card(
                    raw_card,
                    article,
                    response_text,
                    article_support_ranges,
                )
            except FactVerificationError as error:
                logger.warning("速報事実カードを不採用 (%s): %s", article_url, error)
                self.last_retrieval_statuses[article_url] = "CARD_UNVERIFIED"
                continue
            cards[article_url] = card
            self.last_retrieval_statuses[article_url] = "VERIFIED"

        for _, article in indexed_articles:
            article_url = article.get("link", "")
            if (
                article_url in successful_original_urls
                and article_url not in cards
                and self.last_retrieval_statuses.get(article_url)
                != "CARD_UNVERIFIED"
            ):
                self.last_retrieval_statuses[article_url] = "CARD_MISSING"
        return cards

    @staticmethod
    def _parse_fact_card_json(response_text: str) -> List[Dict[str, Any]]:
        text = response_text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
        match = re.search(r'(\[.*\])', text, flags=re.DOTALL)
        if match:
            text = match.group(1)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise FactVerificationError("事実カードのJSON解析に失敗しました") from error
        if not isinstance(data, list):
            raise FactVerificationError("事実カード結果が配列ではありません")
        return [item for item in data if isinstance(item, dict)]

    def _build_verified_fact_card(
        self,
        raw_card: Dict[str, Any],
        article: Dict[str, Any],
        response_text: str,
        support_ranges: List[tuple[int, int]],
    ) -> ArticleFactCard:
        summary = raw_card.get("summary")
        key_facts = raw_card.get("key_facts")
        background = raw_card.get("background")
        impact = raw_card.get("impact")
        if not all(isinstance(value, str) and value.strip() for value in (summary, background, impact)):
            raise FactVerificationError("必須文字列が不足しています")
        if (
            not isinstance(key_facts, list)
            or not 1 <= len(key_facts) <= 3
            or not all(isinstance(value, str) and value.strip() for value in key_facts)
        ):
            raise FactVerificationError("key_factsが不正です")

        claims = [summary, *key_facts, background, impact]
        for claim in claims:
            if not self._claim_has_citation(response_text, claim, support_ranges):
                raise FactVerificationError(f"引用がない事実があります: {claim}")

        return ArticleFactCard(
            title=article.get("title", "不明"),
            source=article.get("source", "不明"),
            url=article.get("link", ""),
            summary=summary.strip(),
            key_facts=[value.strip() for value in key_facts],
            background=background.strip(),
            impact=impact.strip(),
        )

    @staticmethod
    def _claim_has_citation(
        response_text: str,
        claim: str,
        support_ranges: List[tuple[int, int]],
    ) -> bool:
        encoded_claim = json.dumps(claim, ensure_ascii=False)[1:-1]
        search_offset = 0
        while True:
            start = response_text.find(encoded_claim, search_offset)
            if start < 0:
                start = response_text.find(claim, search_offset)
            if start < 0:
                return False
            end = start + len(encoded_claim)
            if any(
                support_start < end and support_end > start
                for support_start, support_end in support_ranges
            ):
                return True
            search_offset = start + 1

    @staticmethod
    def _normalize_url_for_match(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"

    @staticmethod
    def _interaction_field(value: object, name: str):
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    @classmethod
    def _extract_interaction_url_results(
        cls,
        response: object,
    ) -> List[tuple[str, str]]:
        attempts: List[tuple[str, str]] = []
        for step in cls._interaction_field(response, "steps") or []:
            if cls._interaction_field(step, "type") != "url_context_result":
                continue
            for result in cls._interaction_field(step, "result") or []:
                url = cls._interaction_field(result, "url") or ""
                status = cls._interaction_field(result, "status") or "error"
                attempts.append((url, f"URL_RETRIEVAL_STATUS_{str(status).upper()}"))
        return attempts

    @classmethod
    def _extract_interaction_text_and_citations(
        cls,
        response: object,
    ) -> tuple[str, Dict[str, List[tuple[int, int]]]]:
        text_parts: List[str] = []
        ranges_by_url: Dict[str, List[tuple[int, int]]] = {}
        text_offset = 0
        for step in cls._interaction_field(response, "steps") or []:
            if cls._interaction_field(step, "type") != "model_output":
                continue
            for content in cls._interaction_field(step, "content") or []:
                if cls._interaction_field(content, "type") != "text":
                    continue
                text = cls._interaction_field(content, "text") or ""
                text_parts.append(text)
                for annotation in cls._interaction_field(content, "annotations") or []:
                    if cls._interaction_field(annotation, "type") != "url_citation":
                        continue
                    url = cls._interaction_field(annotation, "url")
                    start = cls._interaction_field(annotation, "start_index")
                    end = cls._interaction_field(annotation, "end_index")
                    if (
                        not isinstance(url, str)
                        or not isinstance(start, int)
                        or not isinstance(end, int)
                        or end <= start
                    ):
                        continue
                    normalized_url = cls._normalize_url_for_match(url)
                    ranges_by_url.setdefault(normalized_url, []).append(
                        (text_offset + start, text_offset + end)
                    )
                text_offset += len(text)
        return "".join(text_parts), ranges_by_url

    def review(
        self,
        script: Script,
        articles: List[Dict[str, Any]],
        *,
        require_all_articles: bool = True,
        preferred_model: Optional[str] = None,
    ) -> Script:
        """台本を検索で検証し、証跡付きの修正版を返す。"""
        logger.info("台本レビュー開始 (%d行, %d記事)", len(script), len(articles))
        self.last_verification_urls = []

        article_urls = self._article_urls(articles)
        for article_url in article_urls:
            logger.info("URL Context検証対象: %s", article_url)
        prompt = self._build_review_prompt(
            script,
            articles,
            require_all_articles=require_all_articles,
        )

        last_error: Optional[Exception] = None
        configured_models = getattr(self, "models", (self.model,))
        if preferred_model in configured_models:
            preferred_index = configured_models.index(preferred_model)
            models = configured_models[preferred_index:]
        elif preferred_model:
            models = (preferred_model, *configured_models)
        else:
            models = configured_models
        for attempt in range(MAX_REVIEW_ATTEMPTS):
            model = models[min(attempt, len(models) - 1)]
            try:
                logger.info(
                    "台本レビューAPI呼び出し (モデル: %s, 試行%d/%d)",
                    model,
                    attempt + 1,
                    MAX_REVIEW_ATTEMPTS,
                )
                response = self.client.models.generate_content(
                    model=model,
                    config=self._review_config(),
                    contents=prompt,
                )
                reviewed = self._parse_verified_response(
                    response,
                    expected_url_count=len(article_urls),
                )
                changes = self._count_changes(script, reviewed)
                logger.info(
                    "台本レビュー完了: %d行を修正、検証ソース%d件",
                    changes,
                    len(self.last_verification_urls),
                )
                return reviewed
            except Exception as error:
                last_error = error
                is_transient = any(
                    marker in str(error).lower()
                    for marker in TRANSIENT_REVIEW_ERROR_MARKERS
                )
                is_retryable = isinstance(error, FactVerificationError) or is_transient
                if not is_retryable or attempt >= MAX_REVIEW_ATTEMPTS - 1:
                    break
                next_model = models[min(attempt + 1, len(models) - 1)]
                logger.warning(
                    "台本の事実確認に失敗 (%s, 試行%d/%d): %s。次のモデル%sで再試行します",
                    model,
                    attempt + 1,
                    MAX_REVIEW_ATTEMPTS,
                    error,
                    next_model,
                )
                if is_transient and next_model == model:
                    time.sleep(30)

        detail = f": {last_error}" if last_error else ""
        raise FactVerificationError(
            f"URL Context付きの台本レビューに"
            f"{MAX_REVIEW_ATTEMPTS}回失敗しました{detail}"
        ) from last_error

    @staticmethod
    def _review_config() -> types.GenerateContentConfig:
        """元記事URL Contextを必須にしたレビュー設定を返す。"""
        return types.GenerateContentConfig(
            system_instruction=REVIEW_SYSTEM_PROMPT,
            temperature=0,
            max_output_tokens=65536,
            tools=[types.Tool(url_context=types.UrlContext())],
        )

    def _parse_verified_response(
        self,
        response: types.GenerateContentResponse,
        *,
        expected_url_count: int,
    ) -> Script:
        """元記事URLの取得証跡を検査してからレビュー済み台本を返す。"""
        response_text = getattr(response, "text", None)
        if not response_text:
            raise FactVerificationError("レビュー応答が空です")

        urls, support_ranges = self._extract_url_context_evidence(response)
        if not urls:
            raise FactVerificationError("レビュー応答に取得済みの元記事URLがありません")
        if len(urls) != expected_url_count:
            raise FactVerificationError(
                f"元記事URLをすべて取得できませんでした "
                f"({len(urls)}/{expected_url_count})"
            )
        if not support_ranges:
            raise FactVerificationError("レビュー応答に元記事の引用範囲がありません")

        reviewed = self._parse_response(response_text)
        self._validate_claim_citations(reviewed, response_text, support_ranges)
        self.last_verification_urls = urls
        return reviewed

    @staticmethod
    def _extract_url_context_evidence(
        response: types.GenerateContentResponse,
    ) -> tuple[List[str], List[tuple[int, int]]]:
        """応答から取得成功した元記事URLと引用文字範囲を抽出する。"""
        urls, support_ranges, _ = ScriptReviewer._extract_url_context_details(
            response
        )
        return urls, support_ranges

    @staticmethod
    def _extract_url_context_details(
        response: types.GenerateContentResponse,
    ) -> tuple[List[str], List[tuple[int, int]], Dict[str, str]]:
        """URL Context応答から成功URL・引用範囲・URL別状態を抽出する。"""
        candidates = response.candidates or []
        if not candidates:
            return [], [], {}

        urls: List[str] = []
        statuses: Dict[str, str] = {}
        url_context_metadata = candidates[0].url_context_metadata
        if url_context_metadata is not None:
            for url_metadata in url_context_metadata.url_metadata or []:
                status = url_metadata.url_retrieval_status
                status_value = (
                    status.value
                    if isinstance(status, types.UrlRetrievalStatus)
                    else status
                )
                logger.info(
                    "URL Context取得結果: status=%s url=%s",
                    status_value or "UNSPECIFIED",
                    url_metadata.retrieved_url or "(URLなし)",
                )
                if url_metadata.retrieved_url:
                    statuses[url_metadata.retrieved_url] = (
                        str(status_value) if status_value else "UNSPECIFIED"
                    )
                if (
                    status
                    == types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS
                    and url_metadata.retrieved_url
                    and url_metadata.retrieved_url not in urls
                ):
                    urls.append(url_metadata.retrieved_url)

        support_ranges: List[tuple[int, int]] = []
        grounding_metadata = candidates[0].grounding_metadata
        if grounding_metadata is not None:
            for support in grounding_metadata.grounding_supports or []:
                segment = support.segment
                start = segment.start_index if segment else None
                end = segment.end_index if segment else None
                if isinstance(start, int) and isinstance(end, int) and end > start:
                    support_ranges.append((start, end))

        return urls, support_ranges, statuses

    @staticmethod
    def _validate_claim_citations(
        script: Script,
        response_text: str,
        support_ranges: List[tuple[int, int]],
    ) -> None:
        """事実行と高リスク語に元記事の引用範囲があることを確認する。"""
        search_offset = 0
        for line in script:
            if any(
                pattern.fullmatch(line.text.strip())
                for pattern in NON_FACTUAL_LINE_PATTERNS
            ):
                continue

            encoded_text = json.dumps(line.text, ensure_ascii=False)[1:-1]
            matched_text = line.text
            line_start = response_text.find(matched_text, search_offset)
            if line_start < 0:
                matched_text = encoded_text
                line_start = response_text.find(matched_text, search_offset)
            if line_start < 0:
                matched_text = line.text
                line_start = response_text.find(matched_text)
            if line_start < 0:
                matched_text = encoded_text
                line_start = response_text.find(matched_text)
            if line_start < 0:
                raise FactVerificationError(
                    f"高リスク主張の引用位置を特定できません: {line.text}"
                )

            line_end = line_start + len(matched_text)
            search_offset = line_end
            if not any(
                support_start < line_end and support_end > line_start
                for support_start, support_end in support_ranges
            ):
                raise FactVerificationError(
                    f"元記事の引用がない事実行があります: {line.text}"
                )

            for high_risk_match in HIGH_RISK_FACT_PATTERN.finditer(line.text):
                matched_prefix = json.dumps(
                    line.text[:high_risk_match.start()],
                    ensure_ascii=False,
                )[1:-1]
                matched_value = json.dumps(
                    high_risk_match.group(),
                    ensure_ascii=False,
                )[1:-1]
                claim_start = line_start + len(matched_prefix)
                claim_end = claim_start + len(matched_value)
                if not any(
                    support_start < claim_end and support_end > claim_start
                    for support_start, support_end in support_ranges
                ):
                    raise FactVerificationError(
                        "元記事の引用がない高リスク主張があります: "
                        f"{high_risk_match.group()} ({line.text})"
                    )

    def _build_review_prompt(
        self,
        script: Script,
        articles: List[Dict[str, Any]],
        *,
        require_all_articles: bool = True,
    ) -> str:
        """レビュー用プロンプトを構築する"""
        article_urls = self._article_urls(articles)
        if len(article_urls) != len(articles):
            raise FactVerificationError(
                "URLがない記事、または重複URLの記事が含まれています"
            )
        if len(article_urls) > MAX_URL_CONTEXT_URLS:
            raise FactVerificationError(
                f"URL Contextの上限を超えています "
                f"({len(article_urls)}/{MAX_URL_CONTEXT_URLS})"
            )

        lines = ["## 提供記事一覧\n"]
        for i, article in enumerate(articles, 1):
            title = article.get("title", "不明")
            source = article.get("source", "")
            link = article.get("link", "")
            lines.append(f"{i}. {title}（{source}） {link}")

        lines.append("\n## レビュー対象の台本\n")
        lines.append("```json")
        script_data = [{"speaker": sl.speaker, "text": sl.text} for sl in script]
        lines.append(json.dumps(script_data, ensure_ascii=False, indent=2))
        lines.append("```")

        if require_all_articles:
            coverage_instruction = "提供記事を漏れなく確認してください。"
        else:
            coverage_instruction = (
                "深掘り版のため、台本で選ばれていない記事を追加しないでください。"
            )
        lines.append(f"\n{coverage_instruction}")
        lines.append(
            "各URLをURL Contextで取得し、6項目で検証した修正版をJSON配列で返してください。"
        )
        return "\n".join(lines)

    @staticmethod
    def _article_urls(articles: List[Dict[str, Any]]) -> List[str]:
        """記事一覧から重複のない検証対象URLを抽出する。"""
        return list(dict.fromkeys(
            article.get("link", "")
            for article in articles
            if article.get("link")
        ))

    def _parse_response(self, response_text: str) -> Script:
        """Geminiレスポンス（JSON文字列）をScript型に変換する"""
        text = response_text.strip()

        # markdownコードブロックを除去
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        # JSON配列部分を抽出
        m = re.search(r'(\[.*\])', text, flags=re.DOTALL)
        if m:
            text = m.group(1)

        raw_data = json.loads(text)

        if not isinstance(raw_data, list):
            raise ValueError("レビュー結果が配列形式ではありません")
        data = cast(List[Dict[str, Any]], raw_data)

        script: Script = []
        for item in data:
            speaker_value = item.get("speaker", "A")
            text_value = item.get("text", "")
            speaker = speaker_value if isinstance(speaker_value, str) else "A"
            reviewed_text = text_value if isinstance(text_value, str) else ""
            if speaker not in ("A", "B"):
                speaker = "A"
            if reviewed_text.strip():
                script.append(
                    ScriptLine(speaker=speaker, text=reviewed_text.strip())
                )

        if not script:
            raise ValueError("レビュー結果が空です")

        return script

    def _count_changes(self, original: Script, reviewed: Script) -> int:
        """元の台本とレビュー後の台本の差分行数を返す"""
        if len(original) != len(reviewed):
            return abs(len(original) - len(reviewed)) + sum(
                1 for a, b in zip(original, reviewed)
                if a.speaker != b.speaker or a.text != b.text
            )
        return sum(
            1 for a, b in zip(original, reviewed)
            if a.speaker != b.speaker or a.text != b.text
        )
