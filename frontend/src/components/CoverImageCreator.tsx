import React, { useState } from 'react';
import axios from 'axios';
import '../styles/components.css';

export default function CoverImageCreator() {
  const [title, setTitle] = useState('');
  const [artist, setArtist] = useState('새벽공기');
  const [mood, setMood] = useState('감성');
  const [loading, setLoading] = useState(false);
  const [imageId, setImageId] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [error, setError] = useState('');

  const moods = ['감성', '활력', '위로', '반성'];

  const handleGenerate = async () => {
    if (!title) {
      setError('곡 제목을 입력해주세요');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post('http://localhost:8000/api/image/generate', {
        title,
        artist,
        mood
      });

      setImageId(response.data.image_id);
      setImageUrl(`http://localhost:8000/api/image/download/${response.data.image_id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || '이미지 생성 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!imageId) return;
    window.open(`http://localhost:8000/api/image/download/${imageId}`);
  };

  return (
    <div className="component-container">
      <h2>🎨 커버 이미지 생성</h2>

      <div className="control-section">
        <div className="control-group">
          <label>곡 제목</label>
          <input
            type="text"
            placeholder="예: 밤거리 드라이브"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div className="control-group">
          <label>아티스트</label>
          <input
            type="text"
            placeholder="기본값: 새벽공기"
            value={artist}
            onChange={(e) => setArtist(e.target.value)}
          />
        </div>

        <div className="control-group">
          <label>감성 선택</label>
          <select value={mood} onChange={(e) => setMood(e.target.value)}>
            {moods.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <button
          className="btn btn-primary"
          onClick={handleGenerate}
          disabled={loading}
        >
          {loading ? '생성 중...' : '🚀 이미지 생성'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {imageUrl && (
        <div className="result-section">
          <h3>✅ 커버 이미지 생성 완료</h3>
          <div className="image-preview">
            <img src={imageUrl} alt={title} />
          </div>
          <button className="btn btn-secondary" onClick={handleDownload}>
            📥 이미지 다운로드
          </button>
        </div>
      )}
    </div>
  );
}
