import os
import subprocess
import json
from pathlib import Path
from config import MASTERING_CONFIG, ANTI_CONTENT_ID

class AudioProcessor:
    """오디오 마스터링 및 처리"""

    def __init__(self):
        self.mastering_config = MASTERING_CONFIG
        self.anti_content_id = ANTI_CONTENT_ID

    def mastering(self, input_file, output_file, preset='standard'):
        """
        마스터링 처리
        preset: 'standard', 'loud', 'safe'
        """
        try:
            if preset == 'standard':
                # 표준 마스터링
                cmd = [
                    'ffmpeg',
                    '-i', input_file,
                    '-af', 'loudnorm=I=-23:TP=-1.5:LRA=11',  # 음량 정규화
                    '-acodec', 'aac',
                    '-q:a', '5',
                    '-y',
                    output_file
                ]
            elif preset == 'loud':
                # 큰 음량
                cmd = [
                    'ffmpeg',
                    '-i', input_file,
                    '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',
                    '-acodec', 'aac',
                    '-q:a', '5',
                    '-y',
                    output_file
                ]
            elif preset == 'safe':
                # Content ID 회피용 (안전한 음량)
                cmd = [
                    'ffmpeg',
                    '-i', input_file,
                    '-af', 'loudnorm=I=-25:TP=-2:LRA=14',
                    '-acodec', 'aac',
                    '-q:a', '5',
                    '-y',
                    output_file
                ]

            subprocess.run(cmd, check=True, capture_output=True)
            return {'success': True, 'message': '마스터링 완료'}

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def anti_content_id_processing(self, input_file, output_file):
        """
        YouTube Content ID 회피 처리
        - 살짝의 EQ 조정
        - 약간의 속도 변화
        - 음질 최적화
        """
        try:
            # 복잡한 오디오 필터 체인
            audio_filters = (
                "loudnorm=I=-25:TP=-2,"  # 음량 정규화 (안전함)
                "acompressor=threshold=-20dB:ratio=3,"  # 컴프레션
                "equalizer=f=100:t=q:w=1.5:g=2,"  # 저음 약간 부스트
                "equalizer=f=4000:t=q:w=1:g=-1.5,"  # 중고음 살짝 컷
                "atempo=0.99"  # 1% 느려짐 (거의 안들림)
            )

            cmd = [
                'ffmpeg',
                '-i', input_file,
                '-af', audio_filters,
                '-acodec', 'aac',
                '-q:a', '5',
                '-y',
                output_file
            ]

            subprocess.run(cmd, check=True, capture_output=True)
            return {'success': True, 'message': 'Content ID 회피 처리 완료'}

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def generate_video(self, audio_file, image_file, output_file, duration=None):
        """
        음악 + 이미지로 영상 생성 (YouTube용)
        """
        try:
            cmd = [
                'ffmpeg',
                '-loop', '1',
                '-i', image_file,
                '-i', audio_file,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-pix_fmt', 'yuv420p',
                '-shortest',
                '-y',
                output_file
            ]

            subprocess.run(cmd, check=True, capture_output=True)
            return {'success': True, 'message': '영상 생성 완료'}

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def get_audio_info(self, audio_file):
        """오디오 파일 정보 조회"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_format',
                '-of', 'json',
                audio_file
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)

            return {
                'duration': float(info['format']['duration']),
                'bit_rate': info['format']['bit_rate'],
                'format_name': info['format']['format_name']
            }
        except Exception as e:
            return None
