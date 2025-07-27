"""
ElevenLabs APIを使用した超高品質音声生成
Notebook LM並みの自然な音声でポッドキャスト作成
"""

import os
import requests
import json
from pydub import AudioSegment
from datetime import datetime
import config


class ElevenLabsPodcastGenerator:
    def __init__(self):
        self.api_key = os.getenv('ELEVENLABS_API_KEY')
        self.base_url = "https://api.elevenlabs.io/v1"
        
        # 無料枠: 月10,000文字
        # 有料: $5/月で30,000文字
        
        # 事前定義された高品質音声ID
        self.voices = {
            'host': 'pNInz6obpgDQGcFmaJgB',      # Adam (男性・英語)
            'guest': 'EXAVITQu4vr4xnSDxMaL',     # Bella (女性・英語) 
            'japanese_male': '2EiwWnXFnvU5JabPnv8n',   # 日本語対応音声
            'japanese_female': 'piTKgcLEGmPE4e6mEKli'  # 日本語対応音声
        }
    
    def get_available_voices(self):
        """利用可能な音声一覧を取得"""
        headers = {"xi-api-key": self.api_key}
        response = requests.get(f"{self.base_url}/voices", headers=headers)
        
        if response.status_code == 200:
            return response.json()['voices']
        else:
            print(f"音声一覧取得エラー: {response.status_code}")
            return []
    
    def generate_speech(self, text, voice_id, voice_settings=None):
        """テキストを音声に変換"""
        
        if not voice_settings:
            voice_settings = {
                "stability": 0.75,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        
        data = {
            "text": text,
            "voice_settings": voice_settings,
            "model_id": "eleven_multilingual_v2"  # 多言語対応
        }
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{self.base_url}/text-to-speech/{voice_id}",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            return response.content
        else:
            print(f"音声生成エラー: {response.status_code}")
            print(response.text)
            return None
    
    def create_natural_podcast_script(self, content_text):
        """より自然なポッドキャストスクリプトを作成"""
        
        script_parts = []
        
        # 自然なオープニング
        script_parts.append({
            'speaker': 'host',
            'text': """Hey there! Welcome back to AI Auto Podcast. 
            I'm your host, and today we're diving into some fascinating tech news. 
            Let's see what's happening in the world of technology.""",
            'voice_id': self.voices['host']
        })
        
        script_parts.append({
            'speaker': 'guest',
            'text': """Hi everyone! I'm excited to discuss today's stories with you. 
            There's definitely some interesting developments we should talk about.""",
            'voice_id': self.voices['guest']
        })
        
        # コンテンツセクション
        sections = content_text.split('\n\n')
        
        for i, section in enumerate(sections[:3]):
            if section.strip():
                # ホストが紹介
                script_parts.append({
                    'speaker': 'host',
                    'text': f"""So, let's start with our {['first', 'second', 'third'][i]} story today. 
                    {section}
                    What do you think about this?""",
                    'voice_id': self.voices['host']
                })
                
                # ゲストが反応
                responses = [
                    "That's really interesting! This could have significant implications.",
                    "Wow, I didn't expect that development. Let me share my thoughts.",
                    "This is fascinating stuff. There are definitely some key points to consider."
                ]
                
                script_parts.append({
                    'speaker': 'guest',
                    'text': responses[i % len(responses)],
                    'voice_id': self.voices['guest']
                })
        
        # 自然なクロージング
        script_parts.append({
            'speaker': 'host',
            'text': """That wraps up today's tech news discussion. 
            Thanks for tuning in to AI Auto Podcast.""",
            'voice_id': self.voices['host']
        })
        
        script_parts.append({
            'speaker': 'guest',
            'text': """Thanks for having me! 
            Don't forget to subscribe for more tech updates.""",
            'voice_id': self.voices['guest']
        })
        
        return script_parts
    
    def create_podcast_episode(self, content_text, output_path):
        """完全なポッドキャストエピソードを作成"""
        try:
            print("ElevenLabs APIでポッドキャスト生成開始...")
            
            # スクリプト生成
            script_parts = self.create_natural_podcast_script(content_text)
            
            audio_segments = []
            total_chars = 0
            
            for i, part in enumerate(script_parts):
                print(f"音声生成: {i+1}/{len(script_parts)} ({part['speaker']})")
                
                # 文字数カウント
                total_chars += len(part['text'])
                
                # 音声生成
                audio_content = self.generate_speech(
                    part['text'],
                    part['voice_id']
                )
                
                if audio_content:
                    # 一時ファイル保存
                    temp_file = f"temp_eleven_{i}.mp3"
                    with open(temp_file, 'wb') as f:
                        f.write(audio_content)
                    
                    # AudioSegment読み込み
                    segment = AudioSegment.from_mp3(temp_file)
                    
                    # 適切な間隔追加
                    silence = AudioSegment.silent(duration=1000)  # 1秒
                    
                    audio_segments.append(segment)
                    audio_segments.append(silence)
                    
                    # 一時ファイル削除
                    os.remove(temp_file)
                else:
                    print(f"音声生成失敗: パート {i}")
            
            # 音声結合
            print("音声ファイル結合中...")
            final_audio = AudioSegment.empty()
            for segment in audio_segments:
                final_audio += segment
            
            # 音質調整
            final_audio = final_audio.normalize()
            
            # 出力
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            final_audio.export(output_path, format="mp3", bitrate="128k")
            
            print(f"ElevenLabsポッドキャスト生成完了: {output_path}")
            
            return {
                'success': True,
                'output_path': output_path,
                'duration_seconds': len(final_audio) / 1000,
                'total_characters': total_chars,
                'estimated_cost': self.estimate_cost(total_chars)
            }
            
        except Exception as e:
            print(f"ElevenLabsポッドキャスト生成エラー: {e}")
            return {'success': False, 'error': str(e)}
    
    def estimate_cost(self, character_count):
        """ElevenLabs使用料金概算"""
        
        # 2024年料金体系
        if character_count <= 10000:  # 無料枠
            return 0.0
        else:
            # $5/月で30,000文字 = $0.000167/文字
            excess_chars = character_count - 10000
            return round(excess_chars * 0.000167, 4)
    
    def check_quota(self):
        """現在の使用量確認"""
        headers = {"xi-api-key": self.api_key}
        response = requests.get(f"{self.base_url}/user", headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            return {
                'character_count': user_data.get('character_count', 0),
                'character_limit': user_data.get('character_limit', 10000),
                'can_extend': user_data.get('can_extend', False)
            }
        else:
            return None


# 使用例
if __name__ == "__main__":
    # ElevenLabs API Key設定が必要
    # export ELEVENLABS_API_KEY="your_api_key_here"
    
    generator = ElevenLabsPodcastGenerator()
    
    # 使用量確認
    quota = generator.check_quota()
    if quota:
        print(f"使用量: {quota['character_count']}/{quota['character_limit']}")
    
    sample_content = """
AI Technology Update:

Article 1: Latest developments in artificial intelligence
The field of AI continues to evolve rapidly with new breakthroughs in machine learning.

Article 2: New programming languages announced
Developers are getting access to innovative programming tools and languages.

Article 3: Cloud service updates
Major cloud providers have announced significant updates to their platforms.
"""
    
    # ポッドキャスト生成
    result = generator.create_podcast_episode(
        sample_content,
        "./audio_files/elevenlabs_podcast.mp3"
    )
    
    if result['success']:
        print(f"生成成功!")
        print(f"再生時間: {result['duration_seconds']:.1f}秒")
        print(f"使用文字数: {result['total_characters']}")
        print(f"推定コスト: ${result['estimated_cost']}")
    else:
        print(f"生成失敗: {result['error']}")