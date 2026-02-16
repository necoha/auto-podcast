"""
ポッドキャスト台本生成モジュール
Gemini Flash APIを使い、記事情報から対話形式の台本を生成する
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Optional

from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)


@dataclass
class ScriptLine:
    """台本の1行（1発話）"""
    speaker: str  # "A" (ホスト) or "B" (ゲスト)
    text: str     # 発話テキスト


# Script型 = ScriptLineのリスト
Script = List[ScriptLine]


SYSTEM_PROMPT = """\
あなたはポッドキャストの台本ライターです。
以下のニュース記事をもとに、2人の話者（ホストとゲスト）による
自然な日本語の対話形式でポッドキャスト台本を作成してください。

要件:
- 10〜15分程度の会話になるボリューム（合計3000〜5000文字程度）
- 各記事について分かりやすく解説
- 話者Aはホスト（進行役）、話者Bはゲスト（解説役・テック専門家）
- 話者に固有の名前を付けない。台本中では "A:" "B:" のみ使用する
- 自然な相槌・質問・感想を含める
- 冒頭で「この番組はAIによって自動生成されています」と必ず述べる
- 各記事を紹介する際にソース名（NHK、TechCrunchなど）を明示する
- 末尾にまとめと「詳しくは概要欄のリンクをご覧ください」という案内を入れる

出力形式: JSON配列
[{"speaker": "A", "text": "..."}, {"speaker": "B", "text": "..."}, ...]
"""


class ScriptGenerator:
    """Gemini Flash APIでポッドキャスト対話台本を生成する"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")
        self.client = genai.Client(api_key=self.api_key)
        self.model = config.LLM_MODEL
        self.system_prompt = SYSTEM_PROMPT

    def generate_script(self, articles: List[dict]) -> Script:
        """記事リストから対話形式の台本を生成する"""
        if not articles:
            raise ValueError("記事リストが空です")

        prompt = self._build_prompt(articles)
        logger.info("台本生成を開始 (モデル: %s, 記事数: %d)", self.model, len(articles))

        response = self.client.models.generate_content(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                response_mime_type="application/json",
            ),
            contents=prompt,
        )

        script = self._parse_response(response.text)
        logger.info("台本生成完了: %d行", len(script))
        return script

    def _build_prompt(self, articles: List[dict]) -> str:
        """記事情報からプロンプトテキストを構築する"""
        lines = [f"以下の{len(articles)}件のニュース記事をもとに台本を作成してください。\n"]

        for i, article in enumerate(articles, 1):
            lines.append(f"--- 記事{i} ---")
            lines.append(f"タイトル: {article.get('title', '不明')}")
            lines.append(f"ソース: {article.get('source', '不明')}")
            summary = article.get('summary', '')
            if summary:
                # HTMLタグを簡易除去
                import re
                summary = re.sub(r'<[^>]+>', '', summary)
                lines.append(f"要約: {summary}")
            lines.append(f"URL: {article.get('link', '')}")
            lines.append("")

        return "\n".join(lines)

    def _parse_response(self, response_text: str) -> Script:
        """Geminiレスポンス（JSON文字列）をScript型に変換する"""
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error("台本JSONパースエラー: %s", e)
            raise ValueError(f"台本のJSON解析に失敗しました: {e}")

        if not isinstance(data, list):
            raise ValueError("台本が配列形式ではありません")

        script: Script = []
        for item in data:
            speaker = item.get("speaker", "A")
            text = item.get("text", "")
            if text.strip():
                script.append(ScriptLine(speaker=speaker, text=text.strip()))

        if not script:
            raise ValueError("台本が空です")

        return script


def fallback_script(articles: List[dict]) -> Script:
    """台本生成失敗時のフォールバック: 記事をそのまま読み上げテキスト化"""
    from datetime import datetime

    script: Script = []
    script.append(ScriptLine(
        speaker="A",
        text=f"こんにちは。{datetime.now().strftime('%Y年%m月%d日')}のニュースをお届けします。"
    ))

    for i, article in enumerate(articles, 1):
        title = article.get('title', '不明な記事')
        summary = article.get('summary', '')
        source = article.get('source', '')

        import re
        summary = re.sub(r'<[^>]+>', '', summary)

        script.append(ScriptLine(
            speaker="A",
            text=f"続いて{i}つ目のニュースです。{source}からお伝えします。"
        ))
        script.append(ScriptLine(
            speaker="A",
            text=f"{title}。{summary}"
        ))

    script.append(ScriptLine(
        speaker="A",
        text="以上、本日のニュースでした。ご視聴ありがとうございました。"
    ))

    return script


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # テスト用ダミー記事
    test_articles = [
        {
            "title": "AIが医療診断を変革する",
            "summary": "最新のAI技術が医療分野で活用され、画像診断の精度が向上している。",
            "link": "https://example.com/ai-medical",
            "source": "テック新聞",
        },
        {
            "title": "量子コンピュータの商用化が加速",
            "summary": "大手IT企業が量子コンピュータの商用利用に向けた取り組みを発表した。",
            "link": "https://example.com/quantum",
            "source": "サイエンスニュース",
        },
    ]

    gen = ScriptGenerator()
    script = gen.generate_script(test_articles)
    for line in script:
        print(f"[{line.speaker}] {line.text}")
