import React, { useState } from 'react';
import axios from 'axios';
import '../styles/components.css';

interface LyricsResult {
  theme: string;
  mood: string;
  style: string;
  lyrics: string;
  structure: {
    intro: string;
    verse1: string;
    chorus: string;
    verse2: string;
    chorus_repeat: string;
    bridge: string;
    final_chorus: string;
    outro: string;
  };
}

export default function LyricsGenerator() {
  const [theme, setTheme] = useState('');
  const [mood, setMood] = useState('감성');
  const [style, setStyle] = useState('랩');
  const [lyrics, setLyrics] = useState<LyricsResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const themes = [
    '밤거리', '도시의 외로움', '혼자의 시간',
    '위로', '희망', '변화',
    '활력', '열정', '도전',
    '반성', '성장', '다시시작'
  ];

  const moods = ['감성', '활력', '위로', '반성'];
  const styles = ['랩', '빠른속도', '서정적', '강렬한'];

  const handleGenerate = async () => {
    if (!theme) {
      setError('테마를 선택해주세요');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post(
        'http://localhost:8000/api/lyrics/generate',
        {
          theme,
          mood,
          style
        }
      );

      setLyrics(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || '가사 생성 실패');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (lyrics) {
      navigator.clipboard.writeText(lyrics.lyrics);
      alert('가사가 복사되었습니다!');
    }
  };

  return (
    <div className="component-container">
      <h2>✍️ AI 한국 가사 자동 생성</h2>

      <div className="control-section">
        <div className="control-group">
          <label>테마 선택</label>
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
          >
            <option value="">-- 테마 선택 --</option>
            {themes.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label>감성 선택</label>
          <select value={mood} onChange={(e) => setMood(e.target.value)}>
            {moods.map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label>스타일</label>
          <select value={style} onChange={(e) => setStyle(e.target.value)}>
            {styles.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        <button
          className="btn btn-primary"
          onClick={handleGenerate}
          disabled={loading || !theme}
        >
          {loading ? '⏳ 생성 중...' : '🎵 가사 생성'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {lyrics && (
        <div className="lyrics-result">
          <div className="lyrics-header">
            <div>
              <h3>생성된 가사 - {lyrics.theme}</h3>
              <p className="lyrics-meta">감성: {lyrics.mood} | 스타일: {lyrics.style}</p>
            </div>
            <button className="btn btn-secondary" onClick={copyToClipboard}>
              📋 복사
            </button>
          </div>

          <div className="lyrics-content">
            <pre>{lyrics.lyrics}</pre>
          </div>

          <div className="lyrics-structure">
            <h4>📊 가사 구조</h4>
            <div className="structure-grid">
              <div className="structure-item">
                <span className="label">Intro</span>
                <span className="preview">{lyrics.structure.intro.substring(0, 40)}...</span>
              </div>
              <div className="structure-item">
                <span className="label">Verse 1</span>
                <span className="preview">{lyrics.structure.verse1.substring(0, 40)}...</span>
              </div>
              <div className="structure-item">
                <span className="label">Chorus</span>
                <span className="preview">{lyrics.structure.chorus.substring(0, 40)}...</span>
              </div>
              <div className="structure-item">
                <span className="label">Bridge</span>
                <span className="preview">{lyrics.structure.bridge.substring(0, 40)}...</span>
              </div>
            </div>
          </div>

          <div className="tips-section">
            <h4>💡 팁</h4>
            <ul>
              <li>생성된 가사를 복사해서 Suno에 입력할 수 있습니다</li>
              <li>마음에 들지 않으면 다시 생성해보세요</li>
              <li>감정과 스타일을 변경하면 다른 가사가 생성됩니다</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
