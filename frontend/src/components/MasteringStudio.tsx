import React, { useState } from 'react';
import axios from 'axios';
import '../styles/components.css';

interface MasteringPreset {
  name: string;
  description: string;
  eq: { [key: string]: number };
  ratio: number;
  threshold: number;
}

export default function MasteringStudio() {
  const [file, setFile] = useState<File | null>(null);
  const [originalAudioUrl, setOriginalAudioUrl] = useState('');
  const [masteredAudioUrl, setMasteredAudioUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [fileId, setFileId] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [preset, setPreset] = useState('감성');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const presets: { [key: string]: MasteringPreset } = {
    감성: {
      name: '감성힙합',
      description: '따뜻하고 부드러운 톤',
      eq: { bass: 2, midlow: 1.5, mid: 2, high: 1 },
      ratio: 3,
      threshold: -20
    },
    활력: {
      name: '활력충전',
      description: '밝고 선명한 톤',
      eq: { bass: 1, midlow: 1, mid: 1.5, high: 2 },
      ratio: 2.5,
      threshold: -22
    },
    클래식: {
      name: '클래식마스터링',
      description: '프로페셔널 스튜디오 톤',
      eq: { bass: 0.5, midlow: 1, mid: 1, high: 0.5 },
      ratio: 2,
      threshold: -18
    },
    보컬: {
      name: '보컬포커스',
      description: '보컬 명확성 강조',
      eq: { bass: 0, midlow: 2, mid: 2, high: 1.5 },
      ratio: 4,
      threshold: -20
    },
    베이스: {
      name: '베이스부스트',
      description: '저음 강조',
      eq: { bass: 3, midlow: 2, mid: 1, high: 0.5 },
      ratio: 3.5,
      threshold: -22
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setOriginalAudioUrl(URL.createObjectURL(selectedFile));
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
    formData.append('preset', preset);

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
      setMasteredAudioUrl(`http://localhost:8000/api/mastering/download/${response.data.file_id}`);
      setSuccess('마스터링 완료!');
    } catch (err: any) {
      setError(err.response?.data?.detail || '마스터링 처리 실패');
    } finally {
      setLoading(false);
    }
  };

  const currentPreset = presets[preset];

  return (
    <div className="component-container">
      <h2>🎚️ 고급 마스터링 스튜디오</h2>

      <div className="mastering-wrapper">
        {/* 왼쪽: 파일 업로드 & 프리셋 */}
        <div className="mastering-left">
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

          <div className="preset-section">
            <h4>프리셋 선택</h4>
            <div className="preset-grid">
              {Object.entries(presets).map(([key, p]) => (
                <button
                  key={key}
                  className={`preset-btn ${preset === key ? 'active' : ''}`}
                  onClick={() => setPreset(key)}
                >
                  <div className="preset-name">{p.name}</div>
                  <div className="preset-desc">{p.description}</div>
                </button>
              ))}
            </div>
          </div>

          <button
            className="btn btn-primary"
            onClick={handleMastering}
            disabled={loading || !file}
            style={{ width: '100%' }}
          >
            {loading ? '⏳ 처리 중...' : '🚀 마스터링 시작'}
          </button>

          {error && <div className="error-message">{error}</div>}
          {success && <div className="success-message">{success}</div>}
        </div>

        {/* 오른쪽: 비포/애프터 비교 */}
        {(originalAudioUrl || masteredAudioUrl) && (
          <div className="mastering-right">
            <h4>Before / After 비교</h4>
            <div className="audio-comparison">
              {originalAudioUrl && (
                <div className="audio-player">
                  <div className="player-label">🔊 원본 오디오</div>
                  <audio
                    controls
                    src={originalAudioUrl}
                    style={{ width: '100%', marginBottom: '1rem' }}
                  />
                </div>
              )}

              {masteredAudioUrl && (
                <div className="audio-player">
                  <div className="player-label">✨ 마스터링 완료</div>
                  <audio
                    controls
                    src={masteredAudioUrl}
                    style={{ width: '100%', marginBottom: '1rem' }}
                  />
                  <button className="btn btn-secondary" style={{ width: '100%' }}>
                    📥 다운로드
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 마스터링 체인 정보 */}
      <div className="mastering-chain">
        <h4>📊 현재 설정: {currentPreset.name}</h4>
        <div className="chain-details">
          <div className="chain-item">
            <span>EQ 설정</span>
            <span>Bass: +{currentPreset.eq.bass}dB | Mid-Low: +{currentPreset.eq.midlow}dB | Mid: +{currentPreset.eq.mid}dB | High: +{currentPreset.eq.high}dB</span>
          </div>
          <div className="chain-item">
            <span>압축</span>
            <span>{currentPreset.ratio}:1 레시오 | {currentPreset.threshold}dB 임계값</span>
          </div>
          <div className="chain-item">
            <span>제한기</span>
            <span>-1.0dB</span>
          </div>
          <div className="chain-item">
            <span>정규화</span>
            <span>-14.0 LUFS</span>
          </div>
        </div>
      </div>

      {/* 고급 설정 */}
      <div className="advanced-section">
        <button
          className="advanced-toggle"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? '▼ 고급 설정 숨기기' : '▶ 고급 설정 펼치기'}
        </button>

        {showAdvanced && (
          <div className="advanced-controls">
            <h4>🎛️ 커스텀 마스터링</h4>
            <p className="hint">각 대역의 EQ를 조정하여 맞춤형 마스터링을 만들 수 있습니다</p>
            <div className="eq-sliders">
              {Object.entries(currentPreset.eq).map(([freq, value]) => (
                <div key={freq} className="slider-item">
                  <label>{freq === 'bass' ? '베이스 (100Hz)' : freq === 'midlow' ? '저중역 (500Hz)' : freq === 'mid' ? '중역 (2kHz)' : '고역 (8kHz)'}</label>
                  <input type="range" min="0" max="5" step="0.5" defaultValue={value} disabled />
                  <span>+{value}dB</span>
                </div>
              ))}
            </div>
            <p className="hint">💡 팁: 나중에 커스텀 저장 기능이 추가될 예정입니다</p>
          </div>
        )}
      </div>
    </div>
  );
}
