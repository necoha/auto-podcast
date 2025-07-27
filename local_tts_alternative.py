"""
完全無料のローカル音声生成
外部API不要、認証問題なし
"""

import os
import subprocess
from pydub import AudioSegment
from datetime import datetime
import tempfile


class LocalTTSGenerator:
    def __init__(self):
        self.setup_tts_engines()
    
    def setup_tts_engines(self):
        """利用可能なTTSエンジンを確認"""
        self.available_engines = []
        
        # macOS: say コマンド
        if self.check_command('say'):
            self.available_engines.append('macos_say')
        
        # Linux: espeak
        if self.check_command('espeak'):
            self.available_engines.append('espeak')
        
        # Windows: PowerShell SAPI
        if os.name == 'nt':
            self.available_engines.append('windows_sapi')
        
        # Python TTS ライブラリ
        try:
            import pyttsx3
            self.available_engines.append('pyttsx3')
        except ImportError:
            pass
        
        print(f"利用可能なTTSエンジン: {self.available_engines}")
    
    def check_command(self, command):
        """コマンドが利用可能かチェック"""
        try:
            subprocess.run([command, '--help'], 
                         capture_output=True, 
                         check=False)
            return True
        except FileNotFoundError:
            return False
    
    def generate_speech_macos(self, text, voice='Kyoko', rate=200):
        """macOSのsayコマンドで音声生成"""
        with tempfile.NamedTemporaryFile(suffix='.aiff', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            cmd = [
                'say',
                '-v', voice,  # Kyoko(日本語女性), Otoya(日本語男性)
                '-r', str(rate),  # 読み上げ速度
                '-o', temp_path,
                text
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            # AIFFをMP3に変換
            audio = AudioSegment.from_file(temp_path, format="aiff")
            
            # 一時ファイル削除
            os.unlink(temp_path)
            
            return audio
            
        except subprocess.CalledProcessError as e:
            print(f"macOS TTS エラー: {e}")
            return None
    
    def generate_speech_espeak(self, text, voice='mb-jp1', speed=150):
        """eSpeakで音声生成（Linux）"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            cmd = [
                'espeak',
                '-v', voice,  # mb-jp1(日本語)
                '-s', str(speed),  # 速度
                '-w', temp_path,  # 出力ファイル
                text
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            audio = AudioSegment.from_wav(temp_path)
            os.unlink(temp_path)
            
            return audio
            
        except subprocess.CalledProcessError as e:
            print(f"eSpeak エラー: {e}")
            return None
    
    def generate_speech_pyttsx3(self, text, voice_index=0, rate=150):
        """pyttsx3で音声生成"""
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            
            # 音声設定
            voices = engine.getProperty('voices')
            if voices and voice_index < len(voices):
                engine.setProperty('voice', voices[voice_index].id)
            
            engine.setProperty('rate', rate)
            engine.setProperty('volume', 0.8)
            
            # 一時ファイルに保存
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            engine.save_to_file(text, temp_path)
            engine.runAndWait()
            
            # AudioSegmentで読み込み
            audio = AudioSegment.from_wav(temp_path)
            os.unlink(temp_path)
            
            return audio
            
        except Exception as e:
            print(f"pyttsx3 エラー: {e}")
            return None
    
    def generate_speech(self, text, speaker='host'):
        """最適なエンジンで音声生成"""
        
        # 話者別設定
        voice_configs = {
            'host': {
                'macos_say': {'voice': 'Otoya', 'rate': 180},  # 男性
                'espeak': {'voice': 'mb-jp1', 'speed': 150},
                'pyttsx3': {'voice_index': 0, 'rate': 150}
            },
            'guest': {
                'macos_say': {'voice': 'Kyoko', 'rate': 190},  # 女性
                'espeak': {'voice': 'mb-jp1+f3', 'speed': 160},
                'pyttsx3': {'voice_index': 1, 'rate': 160}
            }
        }
        
        config = voice_configs.get(speaker, voice_configs['host'])
        
        # 利用可能なエンジンで順次試行
        for engine in self.available_engines:
            try:
                if engine == 'macos_say':
                    return self.generate_speech_macos(text, **config['macos_say'])
                elif engine == 'espeak':
                    return self.generate_speech_espeak(text, **config['espeak'])
                elif engine == 'pyttsx3':
                    return self.generate_speech_pyttsx3(text, **config['pyttsx3'])
            except Exception as e:
                print(f"{engine} で失敗、次のエンジンを試行: {e}")
                continue
        
        print("すべてのTTSエンジンで失敗")
        return None
    
    def create_podcast_script(self, content_text):
        """ポッドキャストスクリプト生成"""
        script_parts = []
        
        # オープニング
        script_parts.append({
            'speaker': 'host',
            'text': f"""
            こんにちは、AI自動ポッドキャストです。
            本日、{datetime.now().strftime('%Y年%m月%d日')}のニュースをお届けします。
            """
        })
        
        # コンテンツ
        sections = content_text.split('\n\n')
        for i, section in enumerate(sections[:3]):
            if section.strip():
                script_parts.append({
                    'speaker': 'host',
                    'text': f"それでは、{i+1}番目のニュースです。{section}"
                })
                
                script_parts.append({
                    'speaker': 'guest',
                    'text': "興味深いニュースですね。詳しく見てみましょう。"
                })
        
        # エンディング
        script_parts.append({
            'speaker': 'host',
            'text': "本日のニュースは以上です。またお聞きください。"
        })
        
        return script_parts
    
    def create_podcast_episode(self, content_text, output_path):
        """完全なポッドキャストエピソード作成"""
        try:
            print("ローカルTTSでポッドキャスト生成開始...")
            
            script_parts = self.create_podcast_script(content_text)
            audio_segments = []
            
            for i, part in enumerate(script_parts):
                print(f"音声生成: {i+1}/{len(script_parts)} ({part['speaker']})")
                
                audio_segment = self.generate_speech(
                    part['text'], 
                    part['speaker']
                )
                
                if audio_segment:
                    audio_segments.append(audio_segment)
                    
                    # 話者間の間隔
                    silence = AudioSegment.silent(duration=800)
                    audio_segments.append(silence)
                else:
                    print(f"音声生成失敗: パート {i}")
            
            if not audio_segments:
                return {'success': False, 'error': '音声生成に完全に失敗'}
            
            # 音声結合
            print("音声結合中...")
            final_audio = AudioSegment.empty()
            for segment in audio_segments:
                final_audio += segment
            
            # 音質調整
            final_audio = final_audio.normalize()
            
            # 出力
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            final_audio.export(output_path, format="mp3", bitrate="128k")
            
            print(f"ローカルTTSポッドキャスト完成: {output_path}")
            
            return {
                'success': True,
                'output_path': output_path,
                'duration_seconds': len(final_audio) / 1000,
                'file_size': os.path.getsize(output_path),
                'engines_used': self.available_engines
            }
            
        except Exception as e:
            print(f"ローカルTTS生成エラー: {e}")
            return {'success': False, 'error': str(e)}


# Coqui TTSを使った高品質ローカル生成（追加インストール必要）
class CoquiTTSGenerator:
    def __init__(self):
        self.setup_coqui()
    
    def setup_coqui(self):
        """Coqui TTSセットアップ"""
        try:
            from TTS.api import TTS
            
            # 日本語対応モデル
            self.tts = TTS(model_name="tts_models/ja/kokoro/tacotron2-DDC")
            self.available = True
            print("Coqui TTS 初期化完了")
            
        except ImportError:
            print("Coqui TTSがインストールされていません")
            print("pip install TTS でインストールしてください")
            self.available = False
        except Exception as e:
            print(f"Coqui TTS 初期化エラー: {e}")
            self.available = False
    
    def generate_speech(self, text, output_path):
        """高品質音声生成"""
        if not self.available:
            return False
        
        try:
            self.tts.tts_to_file(text=text, file_path=output_path)
            return True
        except Exception as e:
            print(f"Coqui TTS エラー: {e}")
            return False


# 使用例
if __name__ == "__main__":
    generator = LocalTTSGenerator()
    
    sample_content = """
今日のテクノロジーニュース

記事1: AI技術の進歩
人工知能がさらに発展しています。

記事2: 新しいプログラミング言語
開発者向けの新言語が発表されました。
"""
    
    result = generator.create_podcast_episode(
        sample_content,
        "./audio_files/local_tts_podcast.mp3"
    )
    
    if result['success']:
        print(f"生成成功: {result['duration_seconds']:.1f}秒")
        print(f"使用エンジン: {result['engines_used']}")
    else:
        print(f"生成失敗: {result['error']}")