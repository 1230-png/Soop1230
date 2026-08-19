import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from config import SUNO_DOWNLOAD_FOLDER, DATA_FOLDER

class SunoImporter:
    """Suno 다운로드 폴더에서 곡 자동 임포트"""

    def __init__(self):
        self.download_folder = SUNO_DOWNLOAD_FOLDER
        self.library_file = os.path.join(DATA_FOLDER, 'suno_library.json')
        self.load_library()

    def load_library(self):
        """저장된 곡 목록 불러오기"""
        if os.path.exists(self.library_file):
            with open(self.library_file, 'r', encoding='utf-8') as f:
                self.library = json.load(f)
        else:
            self.library = {}

    def save_library(self):
        """곡 목록 저장"""
        with open(self.library_file, 'w', encoding='utf-8') as f:
            json.dump(self.library, f, indent=2, ensure_ascii=False)

    def scan_download_folder(self):
        """
        Suno 다운로드 폴더에서 새로운 곡 찾기
        """
        if not os.path.exists(self.download_folder):
            return {'success': False, 'message': f'폴더를 찾을 수 없습니다: {self.download_folder}'}

        try:
            new_songs = []
            audio_extensions = ['.mp3', '.wav', '.m4a', '.aac']

            for file in os.listdir(self.download_folder):
                file_path = os.path.join(self.download_folder, file)

                # 오디오 파일만 처리
                if not any(file.endswith(ext) for ext in audio_extensions):
                    continue

                # 이미 라이브러리에 있으면 패스
                if file_path in self.library:
                    continue

                # 새로운 곡 추가
                song_info = {
                    'filename': file,
                    'filepath': file_path,
                    'imported_date': datetime.now().isoformat(),
                    'title': file.replace(os.path.splitext(file)[1], ''),
                    'status': 'imported',
                    'mastering_preset': 'standard',
                    'metadata': {
                        'artist': 'Suno AI',
                        'album': '',
                        'description': ''
                    }
                }

                self.library[file_path] = song_info
                new_songs.append(song_info)

            self.save_library()

            return {
                'success': True,
                'new_songs_count': len(new_songs),
                'songs': new_songs
            }

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def get_song(self, song_id):
        """특정 곡 정보 조회"""
        if song_id in self.library:
            return self.library[song_id]
        return None

    def update_song_metadata(self, song_id, title, description, artist='Suno AI', album=''):
        """곡의 메타데이터 업데이트"""
        if song_id not in self.library:
            return {'success': False, 'message': '곡을 찾을 수 없습니다'}

        song = self.library[song_id]
        song['title'] = title
        song['metadata']['description'] = description
        song['metadata']['artist'] = artist
        song['metadata']['album'] = album

        self.save_library()
        return {'success': True, 'message': '메타데이터 업데이트 완료'}

    def set_mastering_preset(self, song_id, preset):
        """곡의 마스터링 프리셋 설정"""
        if song_id not in self.library:
            return {'success': False, 'message': '곡을 찾을 수 없습니다'}

        if preset not in ['standard', 'loud', 'safe', 'anti-content-id']:
            return {'success': False, 'message': '잘못된 프리셋'}

        self.library[song_id]['mastering_preset'] = preset
        self.save_library()
        return {'success': True, 'message': f'마스터링 프리셋 설정: {preset}'}

    def get_all_songs(self):
        """모든 곡 목록 반환"""
        return list(self.library.values())

    def get_songs_by_status(self, status):
        """특정 상태의 곡들 조회"""
        return [song for song in self.library.values() if song['status'] == status]

    def update_song_status(self, song_id, status):
        """곡 상태 업데이트"""
        if song_id not in self.library:
            return {'success': False, 'message': '곡을 찾을 수 없습니다'}

        self.library[song_id]['status'] = status
        self.save_library()
        return {'success': True, 'message': f'상태 변경: {status}'}

    def delete_song(self, song_id):
        """라이브러리에서 곡 삭제"""
        if song_id not in self.library:
            return {'success': False, 'message': '곡을 찾을 수 없습니다'}

        del self.library[song_id]
        self.save_library()
        return {'success': True, 'message': '곡이 라이브러리에서 제거됨'}
