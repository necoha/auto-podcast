"""
ポッドキャスト台本生成モジュール
Gemini Flash APIを使い、記事情報から対話形式の台本を生成する
"""

import json
import logging
import re
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


SYSTEM_PROMPT_TEMPLATE = """\
あなたはポッドキャストの台本ライターです。
以下のニュース記事をもとに、2人の話者（ホストとゲスト）による
自然な日本語の対話形式でポッドキャスト台本を作成してください。

話者設定:
- 話者A: ホスト（進行役）。名前は「{host_name}」
- 話者B: ゲスト（解説役・テック専門家）。名前は「{guest_name}」
- 台本中の speaker は "A" "B" を使用する（名前はテキスト内で自然に使う）

要件:
- 5〜8分程度の会話になるボリューム（合計1500〜2500文字程度）
- 提供されるすべての記事に触れること（1件も漏らさない）
- ただし同じトピックを扱う重複記事は1つのトピックにまとめて紹介する（例: 同じ事件を複数ソースが報じている場合はまとめて1回で扱う）
- 各トピックについて簡潔に解説（1トピックあたり2〜3往復程度）
- 冒頭の挨拶例: 話者A「おはようございます、{host_name}です。今日も〜」話者B「{guest_name}です、よろしくお願いします！」— この自己紹介は番組冒頭の**1回だけ**
- **厳守: 2行目以降のすべての発話で「〇〇です」「私は〇〇です」などの自己紹介フレーズを使用禁止**。話者は自分の名前を冒頭以外で名乗らない
- 会話中に相手を名前で呼ぶのは可（「{guest_name}さん、それは〜」など）。ただし自分の名前は冒頭1回のみ
- 自然な相槌・質問・感想を含める
- 冒頭で「この番組はAIによって自動生成されています」と必ず述べる
- 各記事を紹介する際にソース名（NHK、GIGAZINEなど）を明示する
- 末尾にまとめと「今日も聞いてくれてありがとうございました、また明日お会いしましょう」という締めの挨拶を入れる

著作権に関する注意:
- 元記事の文章をそのまま引用・転載しないこと
- あなた自身の言葉で独自に要約・解説・分析すること
- 事実の伝達にとどめ、元記事の表現や文体を模倣しないこと
- 英語の記事タイトルはそのまま読まず、内容を日本語で簡潔に言い換えて紹介すること

事実確認に関する注意:
- 提供された記事情報に書かれていない固有名詞・日付・事実を勝手に補完しないこと
- 製品の発売日・価格・スペックなど、記事に明記されていない具体的な情報は推測で述べない
- 確信がない情報は「と見られています」「という見方もあります」のように曖昧に表現すること

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


class ScriptGenerator:
    """ポッドキャスト対話台本を生成する

    曜日ローテーションでホスト名・ゲスト名を切り替える。
    """

    def __init__(self, api_key: Optional[str] = None,
                 host_name: Optional[str] = None,
                 guest_name: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")
        self.client = genai.Client(api_key=self.api_key)
        self.model = config.LLM_MODEL
        self.host_name = host_name or "アオイ"
        self.guest_name = guest_name or "タクミ"
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            host_name=self.host_name,
            guest_name=self.guest_name,
        )

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
        script = self._apply_pronunciation_fixes(script)
        logger.info("台本生成完了: %d行", len(script))
        return script

    # TTS 読み替え辞書: {パターン: 読み替え}
    # 正規表現パターンも使用可能（re.sub で適用）
    PRONUNCIATION_MAP = {
        # ===== ニュースソース（RSSフィード元）=====
        "GIGAZINE": "ギガジン",
        "ITmedia": "アイティメディア",
        "Publickey": "パブリッキー",
        "CNET Japan": "シーネットジャパン",
        "CNET": "シーネット",
        "Impress Watch": "インプレスウォッチ",
        "gihyo.jp": "ギヒョー",
        "ASCII.jp": "アスキー",
        "ASCII": "アスキー",
        "NHK": "エヌエイチケー",
        "TechCrunch": "テッククランチ",
        "Ars Technica": "アルステクニカ",
        "Reuters": "ロイター",
        "Yahoo": "ヤフー",
        "The Verge": "ザ ヴァージ",
        "Wired": "ワイアード",
        "ZDNet": "ゼットディーネット",
        "Engadget": "エンガジェット",
        "Bloomberg": "ブルームバーグ",
        "TechRadar": "テックレーダー",
        # ===== テクノロジー企業・サービス =====
        "Google": "グーグル",
        "Microsoft": "マイクロソフト",
        "Apple": "アップル",
        "Amazon": "アマゾン",
        "Meta": "メタ",
        "NVIDIA": "エヌビディア",
        "Nvidia": "エヌビディア",
        "AMD": "エーエムディー",
        "Intel": "インテル",
        "Tesla": "テスラ",
        "SpaceX": "スペースエックス",
        "Netflix": "ネットフリックス",
        "Spotify": "スポティファイ",
        "YouTube": "ユーチューブ",
        "OpenAI": "オープンエーアイ",
        "DeepMind": "ディープマインド",
        "Anthropic": "アンスロピック",
        "Gemini": "ジェミニ",
        "ChatGPT": "チャットジーピーティー",
        "Copilot": "コパイロット",
        "Claude": "クロード",
        "Mistral": "ミストラル",
        "Hugging Face": "ハギングフェイス",
        "Slack": "スラック",
        "Zoom": "ズーム",
        "Teams": "チームズ",
        "Qualcomm": "クアルコム",
        "Huawei": "ファーウェイ",
        "ASUS": "エイスース",
        "Lenovo": "レノボ",
        "Samsung": "サムスン",
        "TSMC": "ティーエスエムシー",
        "Oracle": "オラクル",
        "Salesforce": "セールスフォース",
        "SAP": "エスエーピー",
        "Adobe": "アドビ",
        "Cisco": "シスコ",
        "VMware": "ブイエムウェア",
        "Palantir": "パランティア",
        "Databricks": "データブリックス",
        "Snowflake": "スノーフレーク",
        "Shopify": "ショッピファイ",
        "Stripe": "ストライプ",
        "Twilio": "トゥイリオ",
        "Cloudflare": "クラウドフレア",
        "Vercel": "ヴァーセル",
        "Supabase": "スーパベース",
        "Firebase": "ファイアベース",
        "Redis": "レディス",
        "Elasticsearch": "エラスティックサーチ",
        "MongoDB": "モンゴディービー",
        "PostgreSQL": "ポストグレスキューエル",
        "MySQL": "マイエスキューエル",
        "SQLite": "エスキューライト",
        "Notion": "ノーション",
        "Figma": "フィグマ",
        "Canva": "キャンバ",
        "DeepSeek": "ディープシーク",
        "Perplexity": "パープレキシティ",
        "xAI": "エックスエーアイ",
        "Grok": "グロック",
        "Llama": "ラマ",
        "Stable Diffusion": "ステーブル ディフュージョン",
        "Midjourney": "ミッドジャーニー",
        "DALL-E": "ダリー",
        "Sora": "ソラ",
        # ===== プログラミング・技術用語 =====
        "GitHub": "ギットハブ",
        "GitLab": "ギットラブ",
        "Kubernetes": "クバネティス",
        "Docker": "ドッカー",
        "Python": "パイソン",
        "JavaScript": "ジャバスクリプト",
        "TypeScript": "タイプスクリプト",
        "Rust": "ラスト",
        "React": "リアクト",
        "Linux": "リナックス",
        "Ubuntu": "ウブントゥ",
        "Debian": "デビアン",
        "Fedora": "フェドラ",
        "CentOS": "セントオーエス",
        "Windows": "ウィンドウズ",
        "macOS": "マックオーエス",
        "iOS": "アイオーエス",
        "Android": "アンドロイド",
        "Raspberry Pi": "ラズベリーパイ",
        "Wi-Fi": "ワイファイ",
        "Bluetooth": "ブルートゥース",
        "Terraform": "テラフォーム",
        "Ansible": "アンシブル",
        "Prometheus": "プロメテウス",
        "Grafana": "グラファナ",
        "Nginx": "エンジンエックス",
        "Apache": "アパッチ",
        "GraphQL": "グラフキューエル",
        "gRPC": "ジーアールピーシー",
        "WebSocket": "ウェブソケット",
        "OAuth": "オーオース",
        "JWT": "ジェイダブリューティー",
        "YAML": "ヤムル",
        "JSON": "ジェイソン",
        "XML": "エックスエムエル",
        "TOML": "トムル",
        "npm": "エヌピーエム",
        "Webpack": "ウェブパック",
        "Vite": "ヴィート",
        "Next.js": "ネクストジェイエス",
        "Vue.js": "ビュージェイエス",
        "Svelte": "スベルト",
        "Flutter": "フラッター",
        "Swift": "スウィフト",
        "Kotlin": "コトリン",
        "Go": "ゴー",
        "Scala": "スカラ",
        "Haskell": "ハスケル",
        "Elixir": "エリクサー",
        "Erlang": "アーラン",
        "Zig": "ジグ",
        "RISC-V": "リスクファイブ",
        "ARM": "アーム",
        "FPGA": "エフピージーエー",
        "ASIC": "エーシック",
        "Wasm": "ワズム",
        "WebAssembly": "ウェブアセンブリ",
        # ===== 英語略語 =====
        "LLM": "エルエルエム",
        "API": "エーピーアイ",
        "AWS": "エーダブリューエス",
        "GPU": "ジーピーユー",
        "CPU": "シーピーユー",
        "TPU": "ティーピーユー",
        "NPU": "エヌピーユー",
        "SoC": "エスオーシー",
        "SaaS": "サース",
        "IaaS": "イアース",
        "PaaS": "パース",
        "OSS": "オーエスエス",
        "UI": "ユーアイ",
        "UX": "ユーエックス",
        "CI/CD": "シーアイシーディー",
        "IoT": "アイオーティー",
        "DX": "ディーエックス",
        "RAG": "ラグ",
        "VR": "ブイアール",
        "AR": "エーアール",
        "XR": "エックスアール",
        "MR": "エムアール",
        "EV": "イーブイ",
        "IT": "アイティー",
        "ICT": "アイシーティー",
        "NFT": "エヌエフティー",
        "DAO": "ダオ",
        "DeFi": "ディーファイ",
        "Web3": "ウェブスリー",
        "5G": "ファイブジー",
        "6G": "シックスジー",
        "SDK": "エスディーケー",
        "IDE": "アイディーイー",
        "CLI": "シーエルアイ",
        "CDN": "シーディーエヌ",
        "DNS": "ディーエヌエス",
        "SSL": "エスエスエル",
        "TLS": "ティーエルエス",
        "VPN": "ブイピーエヌ",
        "SSH": "エスエスエイチ",
        "TCP/IP": "ティーシーピーアイピー",
        "HTTP": "エイチティーティーピー",
        "HTTPS": "エイチティーティーピーエス",
        "SMTP": "エスエムティーピー",
        "GDPR": "ジーディーピーアール",
        "CCPA": "シーシーピーエー",
        "KPI": "ケーピーアイ",
        "ROI": "アールオーアイ",
        "OKR": "オーケーアール",
        "MVP": "エムブイピー",
        "PoC": "ピーオーシー",
        "SRE": "エスアールイー",
        "MLOps": "エムエルオプス",
        "DevOps": "デブオプス",
        "DevSecOps": "デブセックオプス",
        "IaC": "アイエーシー",
        "ETL": "イーティーエル",
        "RPA": "アールピーエー",
        "OCR": "オーシーアール",
        "NLP": "エヌエルピー",
        "AGI": "エージーアイ",
        "ASI": "エーエスアイ",
        "RLHF": "アールエルエイチエフ",
        "LoRA": "ローラ",
        "VRAM": "ブイラム",
        "HBM": "エイチビーエム",
        "DRAM": "ディーラム",
        "SSD": "エスエスディー",
        "NVMe": "エヌブイエムイー",
        "PCIe": "ピーシーアイエクスプレス",
        "USB-C": "ユーエスビーシー",
        "USB": "ユーエスビー",
        "HDMI": "エイチディーエムアイ",
        "IEEE": "アイトリプルイー",
        "W3C": "ダブリューサンシー",
        # ===== 漢字の難読語・多義読み =====
        "代替": "だいたい",
        "汎用": "はんよう",
        "脆弱性": "ぜいじゃくせい",
        "脆弱": "ぜいじゃく",
        "施行": "しこう",
        "施策": "しさく",
        "施錠": "せじょう",
        "頒布": "はんぷ",
        "閾値": "しきいち",
        "知見": "ちけん",
        "乖離": "かいり",
        "進捗": "しんちょく",
        "遵守": "じゅんしゅ",
        "拡充": "かくじゅう",
        "暫定": "ざんてい",
        "概要": "がいよう",
        "既存": "きそん",
        "凡例": "はんれい",
        "冗長": "じょうちょう",
        "逼迫": "ひっぱく",
        "漏洩": "ろうえい",
        "情報漫洩": "じょうほうろうえい",
        "停波": "ていは",
        "改竄": "かいざん",
        "完遂": "かんすい",
        "早急": "さっきゅう",
        "重複": "ちょうふく",
        "続柄": "つづきがら",
        "相殺": "そうさい",
        "境界": "きょうかい",
        "依存": "いそん",
        "捏造": "ねつぞう",
        "破綻": "はたん",
        "瑕疵": "かし",
        "齟齬": "そご",
        "顛末": "てんまつ",
        "杜撰": "ずさん",
        "老舗": "しにせ",
        "所謂": "いわゆる",
        "概ね": "おおむね",
        "殆ど": "ほとんど",
        "脅威": "きょうい",
        "享受": "きょうじゅ",
        "寡占": "かせん",
        "斡旋": "あっせん",
        "逸脱": "いつだつ",
        "払拭": "ふっしょく",
        "遡及": "そきゅう",
        "遡る": "さかのぼる",
        "是正": "ぜせい",
        "措置": "そち",
        "網羅": "もうら",
        "恣意的": "しいてき",
        "割愛": "かつあい",
        "簡潔": "かんけつ",
        "端末": "たんまつ",
        "唯一": "ゆいいつ",
        "踏襲": "とうしゅう",
        "予め": "あらかじめ",
        "著しい": "いちじるしい",
        "甚大": "じんだい",
        "鑑みる": "かんがみる",
        "先駆": "せんく",
        "一端": "いったん",
        "更迭": "こうてつ",
        "体裁": "ていさい",
        "刷新": "さっしん",
        "拘泥": "こうでい",
        "微増": "びぞう",
        "微減": "びげん",
        "潜在的": "せんざいてき",
        "残念": "ざんねん",
        "滑走路": "かっそうろ",
        "地産地消": "ちさんちしょう",
        "否定的": "ひていてき",
        # ===== ニュース頻出表現・基本語 =====
        "浮き彫り": "うきぼり",
        "相次ぐ": "あいつぐ",
        "相次いで": "あいついで",
        "牽引": "けんいん",
        "台頭": "たいとう",
        "頓挫": "とんざ",
        "拮抗": "きっこう",
        "淘汰": "とうた",
        "萎縮": "いしゅく",
        "停滞": "ていたい",
        "堅調": "けんちょう",
        "顕著": "けんちょ",
        "顕在化": "けんざいか",
        "示唆": "しさ",
        "懸念": "けねん",
        "懸案": "けんあん",
        "波及": "はきゅう",
        "惹起": "じゃっき",
        "趨勢": "すうせい",
        "真摯": "しんし",
        "促す": "うながす",
        "担う": "になう",
        "携わる": "たずさわる",
        "培う": "つちかう",
        "築く": "きずく",
        "覆す": "くつがえす",
        "凌ぐ": "しのぐ",
        "委ねる": "ゆだねる",
        "費やす": "ついやす",
        "賄う": "まかなう",
        "遮る": "さえぎる",
        "際立つ": "きわだつ",
        "見据える": "みすえる",
        "紐づく": "ひもづく",
        "紐付け": "ひもづけ",
        "市場": "しじょう",
        "競合": "きょうごう",
        "独占禁止法": "どくせんきんしほう",
        "知的財産": "ちてきざいさん",
        "規制緩和": "きせいかんわ",
        "景気後退": "けいきこうたい",
        "円安": "えんやす",
        "円高": "えんだか",
        "株価": "かぶか",
        "時価総額": "じかそうがく",
        "黒字": "くろじ",
        "赤字": "あかじ",
        "出資": "しゅっし",
        "買収": "ばいしゅう",
        "合併": "がっぺい",
        "提携": "ていけい",
        "上場": "じょうじょう",
        "新興": "しんこう",
        "躍進": "やくしん",
        "急騰": "きゅうとう",
        "急落": "きゅうらく",
        "暴落": "ぼうらく",
        "前年比": "ぜんねんひ",
        "前年同期比": "ぜんねんどうきひ",
        "前月比": "ぜんげつひ",
        "過去最高": "かこさいこう",
        "過去最大": "かこさいだい",
        "一翼": "いちよく",
        "一環": "いっかん",
        "一巡": "いちじゅん",
        "一律": "いちりつ",
        "一斉": "いっせい",
        "一因": "いちいん",
        "一貫": "いっかん",
        "見通し": "みとおし",
        "見込み": "みこみ",
        "見直し": "みなおし",
        "先行き": "さきゆき",
        "行方": "ゆくえ",
        "様相": "ようそう",
        "様々": "さまざま",
        "所以": "ゆえん",
        "外貨": "がいか",
        "為替": "かわせ",
        "利率": "りりつ",
        "金利": "きんり",
        "物価": "ぶっか",
        "賃金": "ちんぎん",
        "雇用": "こよう",
        "就任": "しゅうにん",
        "辞任": "じにん",
        # ===== 政治・行政・国際機関 =====
        "国防総省": "こくぼうそうしょう",
        "国務省": "こくむしょう",
        "国務長官": "こくむちょうかん",
        "国防長官": "こくぼうちょうかん",
        "国家安全保障局": "こっかあんぜんほしょうきょく",
        "連邦準備制度理事会": "れんぽうじゅんびせいどりじかい",
        "連邦取引委員会": "れんぽうとりひきいいんかい",
        "証券取引委員会": "しょうけんとりひきいいんかい",
        "司法省": "しほうしょう",
        "商務省": "しょうむしょう",
        "財務省": "ざいむしょう",
        "経済産業省": "けいざいさんぎょうしょう",
        "総務省": "そうむしょう",
        "文部科学省": "もんぶかがくしょう",
        "厚生労働省": "こうせいろうどうしょう",
        "国土交通省": "こくどこうつうしょう",
        "防衛省": "ぼうえいしょう",
        "デジタル庁": "デジタルちょう",
        "公正取引委員会": "こうせいとりひきいいんかい",
        "金融庁": "きんゆうちょう",
        "内閣府": "ないかくふ",
        "欧州委員会": "おうしゅういいんかい",
        "欧州連合": "おうしゅうれんごう",
        "NATO": "ナトー",
        "FBI": "エフビーアイ",
        "CIA": "シーアイエー",
        "NSA": "エヌエスエー",
        "FRB": "エフアールビー",
        "FTC": "エフティーシー",
        "SEC": "エスイーシー",
        "IMF": "アイエムエフ",
        "WHO": "ダブリューエイチオー",
        "WTO": "ダブリューティーオー",
        "OECD": "オーイーシーディー",
        "IAEA": "アイエーイーエー",
        "DARPA": "ダーパ",
        "NIST": "ニスト",
        "CISA": "シーアイエスエー",
        "EU": "イーユー",
        "GDP": "ジーディーピー",
        "CPI": "シーピーアイ",
        # ===== 人名 =====
        "Elon Musk": "イーロン マスク",
        "Tim Cook": "ティム クック",
        "Satya Nadella": "サティア ナデラ",
        "Sundar Pichai": "サンダー ピチャイ",
        "Mark Zuckerberg": "マーク ザッカーバーグ",
        "Sam Altman": "サム アルトマン",
        "Jensen Huang": "ジェンスン フアン",
        "Jeff Bezos": "ジェフ ベゾス",
        "Lisa Su": "リサ スー",
        "Dario Amodei": "ダリオ アモデイ",
        "Demis Hassabis": "デミス ハサビス",
        "Linus Torvalds": "ライナス トーバルズ",
        "Donald Trump": "ドナルド トランプ",
        "Joe Biden": "ジョー バイデン",
        "Xi Jinping": "しゅうきんぺい",
        # ===== IT・テック系の日本語 =====
        "生成AI": "せいせいエーアイ",
        "機械学習": "きかいがくしゅう",
        "深層学習": "しんそうがくしゅう",
        "強化学習": "きょうかがくしゅう",
        "量子": "りょうし",
        "量子コンピュータ": "りょうしコンピュータ",
        "仮想化": "かそうか",
        "仮想通貨": "かそうつうか",
        "暗号資産": "あんごうしさん",
        "自律": "じりつ",
        "自律型": "じりつがた",
        "自動運転": "じどううんてん",
        "半導体": "はんどうたい",
        "微細化": "びさいか",
        "電子署名": "でんししょめい",
        "多要素認証": "たようそにんしょう",
        "秘密鍵": "ひみつかぎ",
        "公開鍵": "こうかいかぎ",
    }

    def _apply_pronunciation_fixes(self, script: Script) -> Script:
        """台本テキストに読み替え辞書を適用する

        1. LLMが付けた間違った読みを正しい読みで上書き
        2. 読みが未付与の語句に正しい読みを追加
        3. プレースホルダーで長い語の再マッチを防止
        """
        # 長い語句から先にマッチさせ、部分一致の二重置換を防ぐ
        sorted_words = sorted(self.PRONUNCIATION_MAP.keys(), key=len, reverse=True)
        fixed: Script = []
        for line in script:
            text = line.text
            placeholders: dict = {}
            for idx, word in enumerate(sorted_words):
                reading = self.PRONUNCIATION_MAP[word]
                placeholder = f"\x00PH{idx}\x00"
                # 1. 既に読みが付いている場合: プレースホルダーに置換（間違った読みも上書き）
                wrong_pattern = re.compile(
                    re.escape(word) + r'（[ぁ-ゟァ-ヴーｰA-Za-z\s]+）'
                )
                text = wrong_pattern.sub(placeholder, text)
                # 2. 読みが未付与の場合: プレースホルダーに置換
                bare_pattern = re.compile(re.escape(word) + r'(?!（)')
                text = bare_pattern.sub(placeholder, text)
                placeholders[placeholder] = f"{word}（{reading}）"
            # プレースホルダーを正しいアノテーションに復元
            for ph, annotated in placeholders.items():
                text = text.replace(ph, annotated)
            fixed.append(ScriptLine(speaker=line.speaker, text=text))
        return fixed

    def _build_prompt(self, articles: List[dict]) -> str:
        """記事情報からプロンプトテキストを構築する"""
        lines = [f"以下の{len(articles)}件のニュース記事をもとに台本を作成してください。\n"]

        for i, article in enumerate(articles, 1):
            lines.append(f"--- 記事{i} ---")
            lines.append(f"タイトル: {article.get('title', '不明')}")
            lines.append(f"ソース: {article.get('source', '不明')}")
            lines.append(f"URL: {article.get('link', '')}")
            lines.append("")

        return "\n".join(lines)

    def _parse_response(self, response_text: str) -> Script:
        """Geminiレスポンス（JSON文字列）をScript型に変換する"""
        import re as _re
        text = response_text.strip()

        # markdownコードブロックを除去 (```json ... ``` or ``` ... ```)
        text = _re.sub(r'^```(?:json)?\s*', '', text, flags=_re.MULTILINE)
        text = _re.sub(r'```\s*$', '', text, flags=_re.MULTILINE)
        text = text.strip()

        # JSON配列部分を抽出（前後に余分なテキストがある場合）
        m = _re.search(r'(\[.*\])', text, flags=_re.DOTALL)
        if m:
            text = m.group(1)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("台本JSONパースエラー: %s", e)
            # 最終行を削って切り詰めを回復する試み
            try:
                lines = text.splitlines()
                for i in range(len(lines) - 1, 0, -1):
                    candidate = '\n'.join(lines[:i])
                    # 末尾のカンマを除去して閉じ括弧を補う
                    candidate = candidate.rstrip().rstrip(',')
                    for closing in [']', '}]']:
                        try:
                            data = json.loads(candidate + closing)
                            logger.warning("台本JSON部分回復: 末尾 %d 行をスキップ", len(lines) - i)
                            break
                        except json.JSONDecodeError:
                            continue
                    else:
                        continue
                    break
                else:
                    raise ValueError(f"台本のJSON解析に失敗しました: {e}")
            except ValueError:
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


def fallback_script(articles: List[dict],
                    host_name: str = "アオイ",
                    guest_name: str = "タクミ") -> Script:
    """台本生成失敗時のフォールバック: 記事をそのまま読み上げテキスト化"""
    from datetime import datetime
    import re as _re

    script: Script = []
    script.append(ScriptLine(
        speaker=host_name,
        text=f"おはようございます、{host_name}です。{datetime.now().strftime('%Y年%m月%d日')}のニュースをお届けします。"
    ))
    script.append(ScriptLine(
        speaker=guest_name,
        text=f"{guest_name}です。よろしくお願いします。"
    ))

    for i, article in enumerate(articles, 1):
        title = article.get('title', '不明な記事')
        source = article.get('source', '')

        script.append(ScriptLine(
            speaker=host_name,
            text=f"続いて{i}つ目のニュースです。{source}からお伝えします。"
        ))
        script.append(ScriptLine(
            speaker=guest_name,
            text=f"{title}というニュースです。{source}が報じています。"
        ))

    script.append(ScriptLine(
        speaker=host_name,
        text=f"以上、本日のニュースでした。{guest_name}さん、ありがとうございました。"
    ))
    script.append(ScriptLine(
        speaker=guest_name,
        text="ありがとうございました。また明日お会いしましょう。"
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
