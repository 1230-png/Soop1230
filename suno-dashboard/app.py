from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
import os
import json
from functools import wraps
from datetime import datetime

from config import *
from mastering.audio_processor import AudioProcessor
from youtube.uploader import YouTubeUploader
from suno.importer import SunoImporter

# Flask 앱 초기화
app = Flask(__name__)
app.config.from_object('config')
Session(app)

# 모듈 초기화
audio_processor = AudioProcessor()
youtube_uploader = YouTubeUploader()
suno_importer = SunoImporter()

# 로그인 필수 데코레이터
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== 로그인 ====================

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == LOGIN_PASSWORD:
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='비밀번호가 잘못되었습니다')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==================== 대시보드 ====================

@app.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'total_songs': len(suno_importer.get_all_songs()),
        'youtube_accounts': len(youtube_uploader.list_accounts()),
        'imported_today': len([s for s in suno_importer.get_all_songs()
                             if s['imported_date'].startswith(datetime.now().date().isoformat())])
    }
    return render_template('dashboard.html', stats=stats)

# ==================== Suno 곡 관리 ====================

@app.route('/api/suno/scan')
@login_required
def suno_scan():
    """Suno 폴더에서 새 곡 스캔"""
    result = suno_importer.scan_download_folder()
    return jsonify(result)

@app.route('/api/suno/songs')
@login_required
def suno_songs():
    """모든 곡 목록 조회"""
    songs = suno_importer.get_all_songs()
    return jsonify(songs)

@app.route('/api/suno/song/<song_id>')
@login_required
def suno_song(song_id):
    """특정 곡 정보 조회"""
    song = suno_importer.get_song(song_id)
    if song:
        return jsonify(song)
    return jsonify({'error': '곡을 찾을 수 없습니다'}), 404

@app.route('/api/suno/update/<song_id>', methods=['POST'])
@login_required
def suno_update(song_id):
    """곡 메타데이터 업데이트"""
    data = request.json
    result = suno_importer.update_song_metadata(
        song_id,
        data.get('title'),
        data.get('description'),
        data.get('artist', 'Suno AI'),
        data.get('album', '')
    )
    return jsonify(result)

@app.route('/api/suno/mastering/<song_id>', methods=['POST'])
@login_required
def suno_mastering(song_id):
    """곡 마스터링"""
    data = request.json
    preset = data.get('preset', 'standard')

    song = suno_importer.get_song(song_id)
    if not song:
        return jsonify({'success': False, 'message': '곡을 찾을 수 없습니다'}), 404

    # 마스터링 처리
    input_file = song['filepath']
    output_file = input_file.replace('.', f'_mastered_{preset}.')

    if preset == 'anti-content-id':
        result = audio_processor.anti_content_id_processing(input_file, output_file)
    else:
        result = audio_processor.mastering(input_file, output_file, preset)

    if result['success']:
        # 라이브러리 업데이트
        suno_importer.set_mastering_preset(song_id, preset)
        song['mastered_file'] = output_file
        suno_importer.save_library()

    return jsonify(result)

# ==================== YouTube 계정 관리 ====================

@app.route('/api/youtube/accounts')
@login_required
def youtube_accounts():
    """저장된 YouTube 계정 목록"""
    accounts = youtube_uploader.list_accounts()
    return jsonify({'accounts': accounts})

@app.route('/api/youtube/authenticate', methods=['POST'])
@login_required
def youtube_authenticate():
    """새로운 YouTube 계정 인증"""
    data = request.json
    account_name = data.get('account_name')
    client_id = data.get('client_id')
    client_secret = data.get('client_secret')

    if not all([account_name, client_id, client_secret]):
        return jsonify({'success': False, 'message': '필수 정보가 없습니다'}), 400

    result = youtube_uploader.authenticate(account_name, client_id, client_secret)
    return jsonify(result)

@app.route('/api/youtube/delete/<account_name>', methods=['DELETE'])
@login_required
def youtube_delete(account_name):
    """YouTube 계정 삭제"""
    result = youtube_uploader.delete_account(account_name)
    return jsonify(result)

# ==================== 업로드 ====================

@app.route('/api/upload/video', methods=['POST'])
@login_required
def upload_video():
    """YouTube에 영상 업로드"""
    data = request.json
    account_name = data.get('account_name')
    video_file = data.get('video_file')
    title = data.get('title')
    description = data.get('description')
    tags = data.get('tags', [])

    if not os.path.exists(video_file):
        return jsonify({'success': False, 'message': '파일을 찾을 수 없습니다'}), 404

    result = youtube_uploader.upload_video(
        account_name,
        video_file,
        title,
        description,
        tags
    )
    return jsonify(result)

# ==================== 설정 ====================

@app.route('/settings')
@login_required
def settings():
    """설정 페이지"""
    config_data = {
        'suno_folder': SUNO_DOWNLOAD_FOLDER,
        'youtube_accounts': youtube_uploader.list_accounts(),
        'login_password': '****' # 보안상 표시하지 않음
    }
    return render_template('settings.html', config=config_data)

@app.route('/api/settings/update', methods=['POST'])
@login_required
def update_settings():
    """설정 업데이트"""
    data = request.json
    # TODO: config.py 파일 업데이트 로직
    return jsonify({'success': True, 'message': '설정이 업데이트되었습니다'})

# ==================== 에러 핸들러 ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', message='페이지를 찾을 수 없습니다'), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('error.html', message='서버 오류가 발생했습니다'), 500

# ==================== 앱 실행 ====================

if __name__ == '__main__':
    print("=" * 50)
    print("🎵 Suno AI 마스터링 대시보드")
    print("=" * 50)
    print(f"📁 Suno 폴더: {SUNO_DOWNLOAD_FOLDER}")
    print(f"🔑 로그인 비밀번호: {LOGIN_PASSWORD}")
    print(f"🌐 웹사이트: http://localhost:5000")
    print("=" * 50)
    print("Ctrl+C를 눌러 종료합니다.")
    print("=" * 50)

    app.run(debug=True, host='localhost', port=5000)
