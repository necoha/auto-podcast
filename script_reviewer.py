"""
台本セルフレビューモジュール
生成された台本をURL Contextで元記事と照合してレビューし、
事実確認できない台本を配信経路へ通さない。
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, cast

from google import genai
from google.genai import types

import config
from script_generator import Script, ScriptLine

logger = logging.getLogger(__name__)

MAX_REVIEW_ATTEMPTS = 2
MAX_URL_CONTEXT_URLS = 20
TRANSIENT_REVIEW_ERROR_MARKERS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "resource_exhausted",
    "unavailable",
    "timed out",
    "timeout",
)
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
        model: str = config.LLM_MODEL,
    ):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.model = model
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                timeout=config.GEMINI_LLM_TIMEOUT_MS,
                retry_options=types.HttpRetryOptions(
                    attempts=config.GEMINI_SDK_MAX_ATTEMPTS,
                ),
            ),
        )
        self.last_verification_urls: List[str] = []

    def review(
        self,
        script: Script,
        articles: List[Dict[str, Any]],
        *,
        require_all_articles: bool = True,
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
        for attempt in range(MAX_REVIEW_ATTEMPTS):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
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
                logger.warning(
                    "台本の事実確認に失敗 (試行%d/%d): %s。再試行します",
                    attempt + 1,
                    MAX_REVIEW_ATTEMPTS,
                    error,
                )
                if is_transient:
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
        candidates = response.candidates or []
        if not candidates:
            return [], []

        urls: List[str] = []
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

        return urls, support_ranges

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
