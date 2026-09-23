"""
深掘りポッドキャスト台本生成モジュール
Gemini Flash APIを使い、厳選した記事について深い分析・考察を含む対話台本を生成する

ScriptGeneratorを継承し、PRONUNCIATION_MAP・_parse_response・_apply_pronunciation_fixes を再利用する。
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

import config
from script_generator import (
    ScriptGenerator,
    ScriptLine,
    Script,
)

logger = logging.getLogger(__name__)


DEEP_SELECTION_SYSTEM_PROMPT = """\
あなたはニュース編集者です。
提供された記事タイトル・媒体名だけを比較し、深掘り解説に適した記事を選んでください。

選定基準:
- 社会的インパクトが大きい
- 技術・経済の重要な変化を扱う
- 一般リスナーに説明する価値がある
- 同じ話題を重複して選ばない

記事本文にない事実を補完せず、出力は選んだ記事番号のJSON配列だけにしてください。
例: [1, 4, 7]
"""


DEEP_SYSTEM_PROMPT_TEMPLATE = """\
あなたはポッドキャストの台本ライターです。
以下の選定済みニュース記事をすべて扱い、深い洞察と分析を含む
対話形式のポッドキャスト台本を作成してください。

話者設定:
- 話者A: ホスト（進行役）。名前は「{host_name}」
- 話者B: ゲスト（解説役・テック専門家）。名前は「{guest_name}」
- 台本中の speaker は "A" "B" を使用する（名前はテキスト内で自然に使う）

記事選定の基準:
- 記事は前段で選定済み。追加選定や除外を行わないこと

各トピックで、記事情報から確認できる範囲だけ含めること:
1. 背景・経緯: なぜこのニュースが生まれたのか、これまでの流れ
2. 技術的な解説: 関連する技術の仕組みや原理をわかりやすく説明
3. 業界・社会への影響: この出来事が及ぼす具体的なインパクト
4. 異なる視点: 賛否両論や異なる立場からの見方
5. 日本と海外の比較: 国内外の動向の違いがあれば言及
6. 今後の展望: この先どうなるかの考察・予測

要件:
- 10〜15分程度の会話になるボリューム（合計3000〜5000文字程度）
- 1トピックあたり5〜8往復の深い議論
- 提供されたトピックはそれぞれ異なるテーマとして扱い、同じ話題を繰り返さない
- 複数の記事が同じニュースを扱っている場合は、それらを統合して1つのトピックとして扱う
- 冒頭の挨拶は「おはようございます、{host_name}です」「{guest_name}です、よろしくお願いします」のように名乗りする（名乗りは冒頭の1回のみ。以降の発話で「〇〇です」と繰り返し名乗らないこと）
- 冒頭で「この番組はAIによって自動生成されています」と必ず述べる
- 冒頭で「このコーナーでは最新ニュースを深掘りして解説していきます」と趣旨を説明
- 会話中は相手を名前で呼ぶことがある（「{guest_name}さん、それは〜」など）が、自分の名前を毎回名乗る必要はない
- 自然な相槌・質問・感想・反論を含める
- ホストが素朴な疑問を投げかけ、ゲストが専門知識で答える形式を基本にする
- 各トピックを紹介する際にソース名を明示する
- トピック間の切り替えには自然な橋渡しを入れる
- 末尾にまとめと「今日も聞いてくれてありがとうございました、また明日お会いしましょう」という締めの挨拶を入れる

著作権に関する注意:
- 元記事の文章をそのまま引用・転載しないこと
- あなた自身の言葉で独自に要約・解説・分析すること
- 事実の伝達にとどめ、元記事の表現や文体を模倣しないこと
- 英語の記事タイトルはそのまま読まず、内容を日本語で簡潔に言い換えて紹介すること

事実確認に関する注意:
- 提供されたタイトル・ソース名・URLだけを事実の根拠とすること
- 記事情報にない固有名詞・数値・年月・価格・割合・因果関係を補完しないこと
- 同じ単位でも主体と指標を混同しないこと。中央銀行の政策金利と民間銀行の預金金利は別の指標である
- 法律・規制・制度の開始時期を記事情報から確認できない場合は、その時期を述べないこと
- 確認できない情報を曖昧表現へ変えて残すことも禁止する
- 6つの分析次元を埋めるために事実を推測してはならない。根拠がない次元は省略すること

発音・表記ルール（TTS読み上げ用）:
- 英語の固有名詞や技術用語にはカタカナ読みを括弧で併記する
  例: GitHub（ギットハブ）、Kubernetes（クバネティス）、AWS（エーダブリューエス）
- 日本語の人名・企業名・地名など固有名詞にもふりがなを括弧で併記する
  例: 孫正義（そんまさよし）、任天堂（にんてんどう）、渋谷（しぶや）
- 多義読みの漢字や難読語にはひらがなで読みを括弧で併記する
  例: 代替（だいたい）、汎用（はんよう）、生成（せいせい）、施行（しこう）、脆弱性（ぜいじゃくせい）
- 数字は自然な日本語読みで書く
  例: "2026年" → "2026年（にせんにじゅうろくねん）"
- 英語略語はカタカナまたはアルファベット読みを併記する
  例: AI（エーアイ）、API（エーピーアイ）、LLM（エルエルエム）
- 記号や特殊文字は使わず、読み上げやすい日本語表現にする

出力形式: JSON配列
[{{"speaker": "A", "text": "..."}}, {{"speaker": "B", "text": "..."}}], ...]
"""


class DeepScriptGenerator(ScriptGenerator):
    """深掘りポッドキャスト対話台本を生成する

    ScriptGeneratorを継承し、以下を変更:
    - プロンプト: 深い分析・考察を要求
    - 記事選定: 前段で選定された最大3件だけを使用
    - 台本長: 3000-5000文字（10-15分）
    """

    def __init__(self, api_key: Optional[str] = None,
                 host_name: Optional[str] = None,
                 guest_name: Optional[str] = None,
                 max_topics: int = 3):
        # 親クラスの__init__を呼ぶが、system_promptは上書きする
        super().__init__(api_key=api_key, host_name=host_name, guest_name=guest_name)
        self.max_topics = max_topics
        self.system_prompt = DEEP_SYSTEM_PROMPT_TEMPLATE.format(
            host_name=self.host_name,
            guest_name=self.guest_name,
            max_topics=self.max_topics,
        )

    def select_articles(
        self,
        articles: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """タイトル・媒体名だけから深掘り対象を最大max_topics件選ぶ。"""
        if not articles:
            raise ValueError("記事リストが空です")

        selected_model = model or self.model
        lines = [
            f"以下の{len(articles)}件から{min(self.max_topics, len(articles))}件を選んでください。",
        ]
        for index, article in enumerate(articles, 1):
            lines.append(
                f"{index}. {article.get('title', '不明')}（{article.get('source', '不明')}）"
            )

        response = self.client.models.generate_content(
            model=selected_model,
            config=types.GenerateContentConfig(
                system_instruction=DEEP_SELECTION_SYSTEM_PROMPT,
                response_mime_type="application/json",
                max_output_tokens=256,
            ),
            contents="\n".join(lines),
        )
        selected_indices = self._parse_selected_indices(
            response.text,
            article_count=len(articles),
        )
        logger.info(
            "深掘り記事選定完了 (モデル: %s): %s",
            selected_model,
            selected_indices,
        )
        return [articles[index - 1] for index in selected_indices]

    def _parse_selected_indices(
        self,
        response_text: str,
        *,
        article_count: int,
    ) -> List[int]:
        """選定レスポンスを重複のない1始まりの記事番号へ変換する。"""
        try:
            data = json.loads(response_text.strip())
        except (AttributeError, json.JSONDecodeError) as error:
            raise ValueError("記事選定のJSON解析に失敗しました") from error
        if not isinstance(data, list):
            raise ValueError("記事選定結果が配列ではありません")

        selected: List[int] = []
        for value in data:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError("記事選定結果に整数以外が含まれています")
            if value < 1 or value > article_count:
                raise ValueError(f"記事選定番号が範囲外です: {value}")
            if value not in selected:
                selected.append(value)

        expected_count = min(self.max_topics, article_count)
        if len(selected) != expected_count:
            raise ValueError(
                f"記事選定数が不正です ({len(selected)}/{expected_count})"
            )
        return selected

    def _build_prompt(self, articles: List[Dict[str, Any]]) -> str:
        """記事情報からプロンプトテキストを構築する（深掘り版）

        前段で選定済みの記事だけを提示する。
        """
        lines = [
            f"以下の選定済み{len(articles)}件をすべて扱い、深掘り台本を作成してください。\n",
            "記事の追加・除外や、同じ話題の繰り返しを行わないでください。\n",
        ]

        for i, article in enumerate(articles, 1):
            lines.append(f"--- 記事{i} ---")
            lines.append(f"タイトル: {article.get('title', '不明')}")
            lines.append(f"ソース: {article.get('source', '不明')}")
            lines.append(f"URL: {article.get('link', '')}")
            lines.append("")

        return "\n".join(lines)


def deep_fallback_script(articles: List[Dict[str, Any]],
                         host_name: str = "アオイ",
                         guest_name: str = "タクミ") -> Script:
    """事実確認失敗時のフォールバック: 最大3件のタイトルだけを読む"""
    from datetime import datetime

    script: Script = []
    script.append(ScriptLine(
        speaker="A",
        text=f"おはようございます、{host_name}です。"
             f"{datetime.now().strftime('%Y年%m月%d日')}、今日の深掘りニュース解説をお届けします。"
             f"この番組はAIによって自動生成されています。"
    ))
    script.append(ScriptLine(
        speaker="B",
        text=f"{guest_name}です。本日は確認できた記事の見出しだけをお伝えします。"
    ))

    # フォールバックでは推測を加えず最大3件の見出しだけを紹介
    for i, article in enumerate(articles[:3], 1):
        title = article.get('title', '不明な記事')
        source = article.get('source', '')

        script.append(ScriptLine(
            speaker="A",
            text=f"それでは{i}つ目のトピックです。{source}からお伝えします。"
        ))
        script.append(ScriptLine(
            speaker="B",
            text=f"{title}というニュースです。{source}が報じています。"
        ))

    script.append(ScriptLine(
        speaker="A",
        text=f"以上、本日のニュース見出しでした。{guest_name}さん、ありがとうございました。"
    ))
    script.append(ScriptLine(
        speaker="B",
        text="ありがとうございました。また明日お会いしましょう。"
    ))

    return script
