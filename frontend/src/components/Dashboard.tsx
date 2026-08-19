import React, { useState } from 'react';
import axios from 'axios';
import '../styles/components.css';

export default function Dashboard() {
  const [loading, setLoading] = useState(false);
  const [autoCompleteResult, setAutoCompleteResult] = useState<any>(null);
  const [error, setError] = useState('');

  const [projects, setProjects] = useState([
    {
      id: 1,
      title: '밤거리 드라이브',
      mood: '기본감성',
      status: '완료',
      date: '2026-08-19',
      progress: 100
    },
    {
      id: 2,
      title: '도시의 외로움',
      mood: '활력감성',
      status: '마스터링 중',
      date: '2026-08-19',
      progress: 50
    }
  ]);

  const stats = {
    totalSongs: 2,
    completed: 1,
    inProgress: 1,
    totalTime: '5:42'
  };

  const handleAutoComplete = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await axios.post('http://localhost:8000/api/auto-complete');
      setAutoCompleteResult(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || '자동 완성 실패');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="component-container">
      <h2>📊 프로젝트 대시보드</h2>

      {/* 원클릭 자동 완성 (Premium Feature 3) */}
      <div className="auto-complete-banner">
        <div className="banner-content">
          <h3>⚡ 원클릭 자동 완성</h3>
          <p>음악 생성부터 마스터링, 커버 이미지, 메타데이터까지 모든 것이 한 클릭으로 완성됩니다</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleAutoComplete}
          disabled={loading}
          style={{ minWidth: '200px' }}
        >
          {loading ? '⏳ 처리 중...' : '🚀 지금 시작'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {autoCompleteResult && (
        <div className="auto-complete-result">
          <h3>✅ 자동 완성 완료!</h3>
          <div className="completion-steps">
            {autoCompleteResult.steps.map((step: any) => (
              <div key={step.step} className="completion-step">
                <span className="step-badge">{step.step}</span>
                <div className="step-info">
                  <div className="step-name">{step.name}</div>
                  <div className="step-desc">{step.description}</div>
                </div>
                <span className="step-status">{step.status}</span>
              </div>
            ))}
          </div>
          <div className="summary-box">
            <h4>📊 처리 결과 요약</h4>
            <div className="summary-stats">
              <div className="summary-stat">
                <span>생성된 곡</span>
                <span className="value">{autoCompleteResult.results.summary.total_songs}곡</span>
              </div>
              <div className="summary-stat">
                <span>총 시간</span>
                <span className="value">{autoCompleteResult.results.summary.total_duration}</span>
              </div>
              <div className="summary-stat">
                <span>파일 크기</span>
                <span className="value">{autoCompleteResult.results.summary.file_size}</span>
              </div>
            </div>
            <p className="next-step">
              💡 다음 단계: {autoCompleteResult.results.summary.next_step}
            </p>
          </div>
        </div>
      )}

      {/* 통계 카드 */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-number">{stats.totalSongs}</div>
          <div className="stat-label">전체 곡</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{stats.completed}</div>
          <div className="stat-label">완료</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{stats.inProgress}</div>
          <div className="stat-label">진행 중</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{stats.totalTime}</div>
          <div className="stat-label">총 시간</div>
        </div>
      </div>

      {/* 빠른 시작 가이드 */}
      <div className="quick-guide">
        <h3>🚀 빠른 시작 가이드</h3>
        <div className="guide-steps">
          <div className="guide-step">
            <div className="step-number">1</div>
            <div className="step-content">
              <h4>배치 설계</h4>
              <p>감정을 선택하고 "배치 생성" 클릭. 10곡의 주제와 가사가 자동 생성됩니다.</p>
            </div>
          </div>
          <div className="guide-step">
            <div className="step-number">2</div>
            <div className="step-content">
              <h4>Suno 생성</h4>
              <p>생성된 Suno 프롬프트를 복사해서 Suno에 입력하고 음악을 생성합니다.</p>
            </div>
          </div>
          <div className="guide-step">
            <div className="step-number">3</div>
            <div className="step-content">
              <h4>마스터링</h4>
              <p>생성된 MP3를 업로드하고 프리셋을 선택한 후 마스터링을 시작합니다.</p>
            </div>
          </div>
          <div className="guide-step">
            <div className="step-number">4</div>
            <div className="step-content">
              <h4>완성</h4>
              <p>커버 이미지와 메타데이터를 생성해서 업로드 준비를 완료합니다.</p>
            </div>
          </div>
        </div>
      </div>

      {/* 최근 프로젝트 */}
      <div className="projects-section">
        <h3>📁 최근 프로젝트</h3>
        <div className="projects-table">
          <div className="table-header">
            <div className="col-title">곡 제목</div>
            <div className="col-mood">감성</div>
            <div className="col-status">상태</div>
            <div className="col-date">날짜</div>
            <div className="col-progress">진행도</div>
          </div>
          {projects.map(project => (
            <div key={project.id} className="table-row">
              <div className="col-title">{project.title}</div>
              <div className="col-mood">
                <span className="mood-badge">{project.mood}</span>
              </div>
              <div className="col-status">
                <span className={`status-badge status-${project.status.includes('완료') ? 'completed' : 'progress'}`}>
                  {project.status}
                </span>
              </div>
              <div className="col-date">{project.date}</div>
              <div className="col-progress">
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${project.progress}%` }}></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 팁 & 트릭 */}
      <div className="tips-section">
        <h3>💡 팁 & 트릭</h3>
        <div className="tips-grid">
          <div className="tip-card">
            <div className="tip-icon">🎵</div>
            <h4>최고의 결과를 위해</h4>
            <ul>
              <li>Suno에서 고음질(High quality)로 생성</li>
              <li>최소 2:30 이상 3:00 미만의 곡 길이</li>
              <li>보컬 프리셋으로 시작해서 결과에 따라 조정</li>
            </ul>
          </div>
          <div className="tip-card">
            <div className="tip-icon">🎚️</div>
            <h4>마스터링 선택하기</h4>
            <ul>
              <li><strong>감성힙합</strong>: 기본 추천</li>
              <li><strong>활력충전</strong>: 더 선명한 음질</li>
              <li><strong>보컬포커스</strong>: 래퍼가 있을 때</li>
            </ul>
          </div>
          <div className="tip-card">
            <div className="tip-icon">📤</div>
            <h4>업로드 전</h4>
            <ul>
              <li>마스터링 전후 오디오 비교</li>
              <li>메타데이터 정보 확인</li>
              <li>커버 이미지가 1080x1080인지 확인</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
