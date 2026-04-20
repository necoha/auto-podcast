"""
台本セルフレビューモジュール
生成された台本をGemini LLMでレビューし、問題があれば修正版を返す。
レビュー失敗時は元の台本をそのまま返す（フォールバック）。
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

import config
from script_generator import Script, ScriptLine

logger = logging.getLogger(__name__)

REVIEW_SYSTEM_PROMPT = """\
あなたはポッドキャスト台本の品質レビュアーです。
与えられた台本を以下の5項目でチェックし、問題があれば修正してください。

## チェック項目

1. **フォーマット不正**: speakerは"A"または"B"のみ。textは空でないこと。
2. **不自然な会話**: 同じフレーズの過度な繰り返し、唐突な話題転換、会話のつながりの不自然さを修正。
3. **記事カバレッジ**: 提供された記事タイトル一覧と照合し、言及されていない記事があれば会話に自然に組み込む。ただし同一トピックの重複記事は1つにまとめてよい。
4. **読み上げ不適切な表現**: URL（https://...）、コードスニペット、過度な括弧表現、記号の羅列など、音声で聞いて不自然になる表現を自然な日本語に置き換える。
5. **長さの偏り**: 特定トピックだけ極端に長い/短い場合、バランスを調整する。

## ルール

- 修正が不要な場合は、元の台本をそのまま返してください。
- 大幅な書き換えは避け、最小限の修正にとどめてください。
- speakerの"A"/"B"は変更しないでください。
- 会話の自然な流れを維持してください。
- 出力は必ずJSON配列形式で返してください。
"""


class ScriptReviewer:
    """生成済み台本をLLMでレビュー・修正するクラス"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = config.LLM_MODEL,
    ):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.model = model
        self.client = genai.Client(api_key=self.api_key)

    def review(
        self,
        script: Script,
        articles: List[Dict[str, Any]],
    ) -> Script:
        """台本をレビューし、修正版を返す。失敗時は元の台本を返す。"""
        logger.info("台本レビュー開始 (%d行, %d記事)", len(script), len(articles))

        prompt = self._build_review_prompt(script, articles)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                config=types.GenerateContentConfig(
                    system_instruction=REVIEW_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
                contents=prompt,
            )
            reviewed = self._parse_response(response.text)

            changes = self._count_changes(script, reviewed)
            if changes == 0:
                logger.info("台本レビュー完了: 修正なし")
            else:
                logger.info("台本レビュー完了: %d行を修正", changes)
            return reviewed

        except Exception as e:
            is_503 = "503" in str(e) or "UNAVAILABLE" in str(e)
            if is_503:
                logger.warning("台本レビュー: 503エラー、30秒後にリトライ: %s", e)
                time.sleep(30)
                try:
                    response = self.client.models.generate_content(
                        model=self.model,
                        config=types.GenerateContentConfig(
                            system_instruction=REVIEW_SYSTEM_PROMPT,
                            response_mime_type="application/json",
                        ),
                        contents=prompt,
                    )
                    reviewed = self._parse_response(response.text)
                    changes = self._count_changes(script, reviewed)
                    logger.info("台本レビュー完了 (リトライ成功): %d行を修正", changes)
                    return reviewed
                except Exception as retry_e:
                    logger.warning("台本レビュー: リトライも失敗、元の台本を使用: %s", retry_e)
                    return script
            else:
                logger.warning("台本レビュー失敗、元の台本を使用: %s", e)
                return script

    def _build_review_prompt(
        self,
        script: Script,
        articles: List[Dict[str, Any]],
    ) -> str:
        """レビュー用プロンプトを構築する"""
        lines = ["## 提供記事一覧\n"]
        for i, article in enumerate(articles, 1):
            title = article.get("title", "不明")
            source = article.get("source", "")
            lines.append(f"{i}. {title}（{source}）")

        lines.append("\n## レビュー対象の台本\n")
        lines.append("```json")
        script_data = [{"speaker": sl.speaker, "text": sl.text} for sl in script]
        lines.append(json.dumps(script_data, ensure_ascii=False, indent=2))
        lines.append("```")

        lines.append("\n上記の台本を5項目でチェックし、修正版をJSON配列で返してください。")
        return "\n".join(lines)

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

        data = json.loads(text)

        if not isinstance(data, list):
            raise ValueError("レビュー結果が配列形式ではありません")

        script: Script = []
        for item in data:
            speaker = item.get("speaker", "A")
            t = item.get("text", "")
            if speaker not in ("A", "B"):
                speaker = "A"
            if t.strip():
                script.append(ScriptLine(speaker=speaker, text=t.strip()))

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
