"""
Google Text-to-Speech APIを使用した代替音声生成
Notebook LM不要で認証問題を完全回避
"""

import os
import json
from google.cloud import texttospeech
from pydub import AudioSegment
from datetime import datetime
import config


class TTSPodcastGenerator:
    def __init__(self):
        # Google Cloud認証（環境変数またはサービスアカウントキー）
        # 無料枠: 月100万文字まで
        self.client = texttospeech.TextToSpeechClient()
        
        # 音声設定
        self.voice_config = {
            'host': {
                'language_code': 'ja-JP',
                'name': 'ja-JP-Neural2-B',  # 男性音声
                'ssml_gender': texttospeech.SsmlVoiceGender.MALE
            },
            'guest': {
                'language_code': 'ja-JP', 
                'name': 'ja-JP-Neural2-C',  # 女性音声
                'ssml_gender': texttospeech.SsmlVoiceGender.FEMALE
            }
        }
    
    def create_podcast_script(self, content_text):
        """ポッドキャスト対話スクリプトを生成"""
        
        # 簡単なスクリプト生成（実際は OpenAI API等でより高度に）
        script_parts = []
        
        # オープニング
        script_parts.append({
            'speaker': 'host',
            'text': f"""
            こんにちは！AI Auto Podcastへようこそ。
            今日は{datetime.now().strftime('%Y年%m月%d日')}のニュースをお届けします。
            それでは、今日の話題を見ていきましょう。
            """
        })
        
        # コンテンツを分割して対話形式に
        sections = content_text.split('\n\n')
        
        for i, section in enumerate(sections[:3]):  # 最大3セクション
            if section.strip():
                # ホストがニュースを紹介
                script_parts.append({
                    'speaker': 'host',
                    'text': f"では、{i+1}つ目の話題です。{section}"
                })
                
                # ゲストがコメント
                script_parts.append({
                    'speaker': 'guest', 
                    'text': f"なるほど、興味深いニュースですね。これについて詳しく教えてください。"
                })
        
        # クロージング
        script_parts.append({
            'speaker': 'host',
            'text': """
            今日のニュースは以上です。
            最新の情報をお届けしました。
            また次回もお楽しみに！
            """
        })
        
        return script_parts
    
    def generate_speech(self, text, voice_type='host'):
        """テキストを音声に変換"""
        
        # 音声設定
        voice = texttospeech.VoiceSelectionParams(
            language_code=self.voice_config[voice_type]['language_code'],
            name=self.voice_config[voice_type]['name'],
            ssml_gender=self.voice_config[voice_type]['ssml_gender']
        )
        
        # 音声合成設定
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.9,  # 少し遅め
            pitch=0.0,
            volume_gain_db=0.0
        )
        
        # SSML形式でより自然な音声に
        ssml_text = f"""
        <speak>
            <prosody rate="0.9" pitch="+0st">
                {text}
            </prosody>
            <break time="500ms"/>
        </speak>
        """
        
        # 音声合成リクエスト
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)
        
        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        return response.audio_content
    
    def create_podcast_episode(self, content_text, output_path):
        """完全なポッドキャストエピソードを作成"""
        try:
            print("ポッドキャストスクリプト生成中...")
            script_parts = self.create_podcast_script(content_text)
            
            print("音声ファイル生成中...")
            audio_segments = []
            
            for i, part in enumerate(script_parts):
                print(f"  音声生成: {i+1}/{len(script_parts)} ({part['speaker']})")
                
                audio_content = self.generate_speech(
                    part['text'], 
                    part['speaker']
                )
                
                # 一時ファイルに保存
                temp_file = f"temp_audio_{i}.mp3"
                with open(temp_file, 'wb') as f:
                    f.write(audio_content)
                
                # AudioSegmentに読み込み
                segment = AudioSegment.from_mp3(temp_file)
                
                # 話者間に短い無音を追加
                silence = AudioSegment.silent(duration=800)  # 800ms
                
                audio_segments.append(segment)
                audio_segments.append(silence)
                
                # 一時ファイル削除
                os.remove(temp_file)
            
            print("音声ファイル結合中...")
            
            # 全ての音声を結合
            final_audio = AudioSegment.empty()
            for segment in audio_segments:
                final_audio += segment
            
            # 音質調整
            final_audio = final_audio.normalize()  # 音量正規化
            
            # MP3として出力
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            final_audio.export(output_path, format="mp3", bitrate="128k")
            
            print(f"ポッドキャスト生成完了: {output_path}")
            
            return {
                'success': True,
                'output_path': output_path,
                'duration_seconds': len(final_audio) / 1000,
                'file_size': os.path.getsize(output_path)
            }
            
        except Exception as e:
            print(f"ポッドキャスト生成エラー: {e}")
            return {'success': False, 'error': str(e)}
    
    def estimate_cost(self, text):
        """Google TTS API使用料金を概算"""
        character_count = len(text)
        
        # Neural2音声の料金（2024年現在）
        # $16.00 per 1M characters
        cost_per_char = 16.00 / 1_000_000
        estimated_cost = character_count * cost_per_char
        
        return {
            'characters': character_count,
            'estimated_cost_usd': round(estimated_cost, 4),
            'free_tier_remaining': max(0, 100_000 - character_count)  # 月10万文字無料
        }


# OpenAI APIを使った高度なスクリプト生成（オプション）
class AIScriptGenerator:
    def __init__(self):
        # OpenAI API（無料枠あり）
        import openai
        openai.api_key = os.getenv('OPENAI_API_KEY')
    
    def generate_podcast_dialogue(self, content_text):
        """AIで自然な対話スクリプトを生成"""
        prompt = f"""
以下のニュース内容を基に、2人のホスト（田中さん：男性、佐藤さん：女性）による
自然なポッドキャスト対話を作成してください。

要件:
- 10-15分程度の長さ
- 親しみやすい会話調
- 専門用語は分かりやすく説明
- 聞き手との距離感を大切に
- 自然な相槌や反応を含める

ニュース内容:
{content_text}

出力形式:
田中: こんにちは！
佐藤: こんにちは！今日はどんな話題でしょうか？
田中: ...
"""

        try:
            import openai
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.7
            )
            
            dialogue = response.choices[0].message.content
            return self.parse_dialogue(dialogue)
            
        except Exception as e:
            print(f"AI対話生成エラー: {e}")
            return None
    
    def parse_dialogue(self, dialogue_text):
        """対話テキストを構造化データに変換"""
        script_parts = []
        lines = dialogue_text.split('\n')
        
        for line in lines:
            if ':' in line:
                speaker_name, text = line.split(':', 1)
                speaker_name = speaker_name.strip()
                text = text.strip()
                
                # 話者名をvoice_typeに変換
                if '田中' in speaker_name or '男性' in speaker_name:
                    voice_type = 'host'
                else:
                    voice_type = 'guest'
                
                script_parts.append({
                    'speaker': voice_type,
                    'text': text
                })
        
        return script_parts


# 使用例
if __name__ == "__main__":
    # Google Cloud認証設定が必要
    # export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
    
    tts_generator = TTSPodcastGenerator()
    
    sample_content = """
今日のテクノロジーニュース:

記事1: AI技術の最新動向
人工知能技術が急速に発展し、様々な分野で活用されています。

記事2: 新しいプログラミング言語の発表
開発者向けの新しいプログラミング言語が発表されました。

記事3: クラウドサービスのアップデート
主要なクラウドプロバイダーが新機能を発表しました。
"""
    
    # 料金見積もり
    cost_info = tts_generator.estimate_cost(sample_content)
    print(f"料金見積もり: ${cost_info['estimated_cost_usd']} ({cost_info['characters']}文字)")
    
    # ポッドキャスト生成
    result = tts_generator.create_podcast_episode(
        sample_content,
        "./audio_files/tts_podcast_test.mp3"
    )
    
    if result['success']:
        print(f"生成成功: {result['duration_seconds']:.1f}秒")
    else:
        print(f"生成失敗: {result['error']}")