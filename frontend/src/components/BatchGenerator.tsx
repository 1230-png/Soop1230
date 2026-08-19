import React, { useState } from 'react';
import axios from 'axios';
import '../styles/components.css';

interface BatchGeneratorProps {
  onBatchGenerated?: (data: any) => void;
}

export default function BatchGenerator({ onBatchGenerated }: BatchGeneratorProps) {
  const [mood, setMood] = useState('기본감성');
  const [count, setCount] = useState(10);
  const [loading, setLoading] = useState(false);
  const [batchData, setBatchData] = useState<any>(null);
  const [error, setError] = useState('');

  const moods = ['기본감성', '활력감성', '위로감성', '반성감성'];

  const handleGenerate = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await axios.post('http://localhost:8000/api/batch/generate', {
        mood,
        count
      });

      setBatchData(response.data);
      onBatchGenerated?.(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || '배치 생성에 실패했습니다');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadMarkdown = () => {
    if (!batchData) return;

    let content = `# ${batchData.mood} 배치\n\n`;
    content += `생성 시간: ${new Date().toLocaleString()}\n\n`;

    batchData.songs.forEach((song: any, idx: number) => {
      content += `## 곡 ${idx + 1}: ${song.title}\n\n`;
      content += `**주제**: ${song.theme}\n`;
      content += `**BPM 목표**: ${song.bpm_target}\n`;
      content += `**보컬 톤**: ${song.vocal_tone}\n\n`;

      content += `### 가사 아웃라인\n${song.lyrics_outline}\n\n`;

      content += `### Suno 스타일\n\`\`\`\n${song.suno_style}\n\`\`\`\n\n`;

      content += `### Suno 제외 요소\n\`\`\`\n${song.suno_exclude}\n\`\`\`\n\n`;
    });

    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `batch_${batchData.batch_id}.md`;
    a.click();
  };

  return (
    <div className="component-container">
      <h2>📋 배치 자동 생성</h2>

      <div className="control-section">
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

        <div className="control-group">
          <label>곡 개수</label>
          <input
            type="number"
            min="1"
            max="50"
            value={count}
            onChange={(e) => setCount(parseInt(e.target.value))}
          />
        </div>

        <button
          className="btn btn-primary"
          onClick={handleGenerate}
          disabled={loading}
        >
          {loading ? '생성 중...' : '🚀 배치 생성'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {batchData && (
        <div className="batch-result">
          <div className="batch-header">
            <h3>✅ {batchData.mood} 배치 완성</h3>
            <p>총 {batchData.songs.length}곡</p>
          </div>

          <div className="songs-list">
            {batchData.songs.map((song: any, idx: number) => (
              <div key={idx} className="song-card">
                <div className="song-number">{idx + 1}</div>
                <div className="song-info">
                  <h4>{song.title}</h4>
                  <p className="song-theme">{song.theme}</p>
                  <p className="song-meta">
                    BPM: {song.bpm_target} | {song.vocal_tone}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <button className="btn btn-secondary" onClick={handleDownloadMarkdown}>
            📥 마크다운 다운로드
          </button>
        </div>
      )}
    </div>
  );
}
