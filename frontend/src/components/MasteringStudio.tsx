import React, { useState } from 'react';
import axios from 'axios';
import '../styles/components.css';

export default function MasteringStudio() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [fileId, setFileId] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError('');
    }
  };

  const handleMastering = async () => {
    if (!file) {
      setError('파일을 선택해주세요');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(
        'http://localhost:8000/api/mastering/process',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        }
      );

      setFileId(response.data.file_id);
      setSuccess('마스터링 완료!');
      setFile(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || '마스터링 처리 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!fileId) return;
    window.open(`http://localhost:8000/api/mastering/download/${fileId}`);
  };

  return (
    <div className="component-container">
      <h2>🎚️ 고급 마스터링</h2>

      <div className="mastering-info">
        <p>✨ 적용되는 마스터링 체인:</p>
        <ul>
          <li>소프트 클리핑 (클립핑 방지)</li>
          <li>4밴드 멀티밴드 EQ (100Hz, 500Hz, 2kHz, 8kHz)</li>
          <li>동적 범위 압축 (3:1 레시오)</li>
          <li>스테레오 공간감 강화</li>
          <li>제한기 (-1.0dB)</li>
          <li>LUFS 정규화 (-14.0 LUFS)</li>
        </ul>
      </div>

      <div className="control-section">
        <div className="file-upload">
          <input
            type="file"
            accept="audio/wav,audio/mp3,audio/mpeg"
            onChange={handleFileSelect}
            id="audio-input"
          />
          <label htmlFor="audio-input" className="file-label">
            {file ? `📁 ${file.name}` : '🎵 오디오 파일 선택 (WAV/MP3)'}
          </label>
        </div>

        <button
          className="btn btn-primary"
          onClick={handleMastering}
          disabled={loading || !file}
        >
          {loading ? '처리 중...' : '🚀 마스터링 시작'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{success}</div>}

      {fileId && (
        <div className="result-section">
          <h3>✅ 마스터링 완료</h3>
          <p>File ID: <code>{fileId}</code></p>
          <button className="btn btn-secondary" onClick={handleDownload}>
            📥 마스터링된 파일 다운로드
          </button>
        </div>
      )}
    </div>
  );
}
