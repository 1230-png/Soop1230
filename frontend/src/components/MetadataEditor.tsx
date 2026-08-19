import React, { useState } from 'react';
import axios from 'axios';
import '../styles/components.css';

export default function MetadataEditor() {
  const [title, setTitle] = useState('');
  const [mood, setMood] = useState('감성');
  const [bpm, setBpm] = useState(90);
  const [metadata, setMetadata] = useState<any>(null);
  const [loading, setLoading] = useState(false);
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
      const response = await axios.post('http://localhost:8000/api/metadata/generate', {
        title,
        mood,
        bpm
      });

      setMetadata(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || '메타데이터 생성 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('복사되었습니다!');
  };

  const handleDownloadJson = () => {
    if (!metadata) return;

    const dataStr = JSON.stringify(metadata, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `metadata_${metadata.title}.json`;
    a.click();
  };

  return (
    <div className="component-container">
      <h2>📝 메타데이터 자동 생성</h2>

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
          <label>감성</label>
          <select value={mood} onChange={(e) => setMood(e.target.value)}>
            {moods.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label>BPM</label>
          <input
            type="number"
            min="60"
            max="180"
            value={bpm}
            onChange={(e) => setBpm(parseInt(e.target.value))}
          />
        </div>

        <button
          className="btn btn-primary"
          onClick={handleGenerate}
          disabled={loading}
        >
          {loading ? '생성 중...' : '🚀 메타데이터 생성'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {metadata && (
        <div className="metadata-result">
          <h3>✅ 메타데이터 생성 완료</h3>

          <div className="metadata-section">
            <h4>기본 정보</h4>
            <div className="metadata-field">
              <label>제목:</label>
              <input type="text" value={metadata.title} readOnly />
              <button
                className="copy-btn"
                onClick={() => handleCopyToClipboard(metadata.title)}
              >
                📋
              </button>
            </div>
            <div className="metadata-field">
              <label>아티스트:</label>
              <input type="text" value={metadata.artist} readOnly />
            </div>
            <div className="metadata-field">
              <label>BPM:</label>
              <input type="text" value={metadata.bpm} readOnly />
            </div>
          </div>

          <div className="metadata-section">
            <h4>설명</h4>
            <textarea value={metadata.description} readOnly rows={5}></textarea>
            <button
              className="copy-btn"
              onClick={() => handleCopyToClipboard(metadata.description)}
            >
              📋 복사
            </button>
          </div>

          <div className="metadata-section">
            <h4>YouTube 제목</h4>
            <input type="text" value={metadata.youtube_title} readOnly />
            <button
              className="copy-btn"
              onClick={() => handleCopyToClipboard(metadata.youtube_title)}
            >
              📋 복사
            </button>
          </div>

          <div className="metadata-section">
            <h4>YouTube 설명</h4>
            <textarea value={metadata.youtube_description} readOnly rows={8}></textarea>
            <button
              className="copy-btn"
              onClick={() => handleCopyToClipboard(metadata.youtube_description)}
            >
              📋 복사
            </button>
          </div>

          <div className="metadata-section">
            <h4>태그 & 키워드</h4>
            <p><strong>태그:</strong> {metadata.tags.join(', ')}</p>
            <p><strong>키워드:</strong> {metadata.keywords}</p>
          </div>

          <button className="btn btn-secondary" onClick={handleDownloadJson}>
            📥 JSON 다운로드
          </button>
        </div>
      )}
    </div>
  );
}
