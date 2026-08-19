import React, { useState } from 'react';
import '../styles/components.css';

export default function Dashboard() {
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

  return (
    <div className="component-container">
      <h2>📊 프로젝트 대시보드</h2>

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
