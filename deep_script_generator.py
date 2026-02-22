"""
深掘りポッドキャスト台本生成モジュール
Gemini Flash APIを使い、厳選した記事について深い分析・考察を含む対話台本を生成する

ScriptGeneratorを継承し、PRONUNCIATION_MAP・_parse_response・_apply_pronunciation_fixes を再利用する。
"""

import json
import logging
import re
from typing import List, Optional

from google import genai
from google.genai import types

import config
from script_generator import (
    ScriptGenerator,
    ScriptLine,
    Script,
)

logger = logging.getLogger(__name__)


DEEP_SYSTEM_PROMPT_TEMPLATE = """\
あなたはポッドキャストの台本ライターです。
以下のニュース記事群の中から最も重要・注目すべき{max_topics}件を選び、
それぞれについて深い洞察と分析を含む対話形式のポッドキャスト台本を作成してください。

話者設定:
- 話者A: ホスト（進行役）。名前は「{host_name}」
- 話者B: ゲスト（解説役・テック専門家）。名前は「{guest_name}」
- 台本中の speaker は "A" "B" を使用する（名前はテキスト内で自然に使う）

記事選定の基準:
- 社会的インパクトが大きいもの
- 技術的に革新的・興味深いもの
- 複数ソース（国内外）で報じられている注目度の高いもの
- リスナーにとって実用的な知見が得られるもの

各トピックで必ず含めること:
1. 背景・経緯: なぜこのニュースが生まれたのか、これまでの流れ
2. 技術的な解説: 関連する技術の仕組みや原理をわかりやすく説明
3. 業界・社会への影響: この出来事が及ぼす具体的なインパクト
4. 異なる視点: 賛否両論や異なる立場からの見方
5. 日本と海外の比較: 国内外の動向の違いがあれば言及
6. 今後の展望: この先どうなるかの考察・予測

要件:
- 10〜15分程度の会話になるボリューム（合計3000〜5000文字程度）
- 1トピックあたり5〜8往復の深い議論
- 冒頭の挨拶は「おはようございます、{host_name}です」「{guest_name}です、よろしくお願いします」のように名乗りする
- 冒頭で「この番組はAIによって自動生成されています」と必ず述べる
- 冒頭で「このコーナーでは最新ニュースを深掘りして解説していきます」と趣旨を説明
- 会話中、相手を名前で呼ぶことがある（「{guest_name}さん、それは〜」など）
- 自然な相槌・質問・感想・反論を含める
- ホストが素朴な疑問を投げかけ、ゲストが専門知識で答える形式を基本にする
- 各トピックを紹介する際にソース名を明示する
- トピック間の切り替えには自然な橋渡しを入れる
- 末尾にまとめと「今日も聞いてくれてありがとうございました、また明日お会いしましょう」という締めの挨拶を入れる

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
    - 記事選定: 全記事から重要な2-3件をAIが選定
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

    def _build_prompt(self, articles: List[dict]) -> str:
        """記事情報からプロンプトテキストを構築する（深掘り版）

        全記事を提示し、AIに重要な記事の選定と深掘り台本の生成を任せる。
        """
        lines = [
            f"以下の{len(articles)}件のニュース記事から、"
            f"最も重要な{self.max_topics}件を選んで深掘り台本を作成してください。\n",
            "選ばなかった記事は無視してください。",
            "同じテーマで複数の記事がある場合は統合して扱ってください。\n",
        ]

        for i, article in enumerate(articles, 1):
            lines.append(f"--- 記事{i} ---")
            lines.append(f"タイトル: {article.get('title', '不明')}")
            lines.append(f"ソース: {article.get('source', '不明')}")
            summary = article.get('summary', '')
            if summary:
                summary = re.sub(r'<[^>]+>', '', summary)
                lines.append(f"要約: {summary}")
            lines.append(f"URL: {article.get('link', '')}")
            lines.append("")

        return "\n".join(lines)


def deep_fallback_script(articles: List[dict],
                         host_name: str = "アオイ",
                         guest_name: str = "タクミ") -> Script:
    """深掘り版台本生成失敗時のフォールバック"""
    from datetime import datetime

    script: Script = []
    script.append(ScriptLine(
        speaker=host_name,
        text=f"おはようございます、{host_name}です。"
             f"{datetime.now().strftime('%Y年%m月%d日')}、今日の深掘りニュース解説をお届けします。"
             f"この番組はAIによって自動生成されています。"
    ))
    script.append(ScriptLine(
        speaker=guest_name,
        text=f"{guest_name}です。よろしくお願いします。"
             f"このコーナーでは最新ニュースを深掘りして解説していきます。"
    ))

    # フォールバックでは最大3件を少し詳しく紹介
    for i, article in enumerate(articles[:3], 1):
        title = article.get('title', '不明な記事')
        summary = re.sub(r'<[^>]+>', '', article.get('summary', ''))
        source = article.get('source', '')

        script.append(ScriptLine(
            speaker=host_name,
            text=f"それでは{i}つ目のトピックです。{source}が報じたニュースについてです。"
        ))
        script.append(ScriptLine(
            speaker=guest_name,
            text=f"はい。{title}ということですね。{summary}"
        ))
        script.append(ScriptLine(
            speaker=host_name,
            text=f"これはどのような影響があるのでしょうか？"
        ))
        script.append(ScriptLine(
            speaker=guest_name,
            text=f"この件については今後の動向に注目していく必要がありますね。"
        ))

    script.append(ScriptLine(
        speaker=host_name,
        text=f"以上、本日の深掘り解説でした。{guest_name}さん、ありがとうございました。"
    ))
    script.append(ScriptLine(
        speaker=guest_name,
        text="ありがとうございました。また明日お会いしましょう。"
    ))

    return script
