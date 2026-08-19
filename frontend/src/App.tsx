import React, { useState } from 'react';
import axios from 'axios';
import './App.css';
import BatchGenerator from './components/BatchGenerator';
import MasteringStudio from './components/MasteringStudio';
import CoverImageCreator from './components/CoverImageCreator';
import MetadataEditor from './components/MetadataEditor';

type TabType = 'batch' | 'mastering' | 'cover' | 'metadata';

function App() {
  const [activeTab, setActiveTab] = useState<TabType>('batch');
  const [batchData, setBatchData] = useState<any>(null);

  return (
    <div className="app">
      <header className="app-header">
        <h1>🌙 감성힙합 자동화 스튜디오</h1>
        <p>배치 설계 → 마스터링 → 커버 이미지 → 메타데이터 완벽 자동화</p>
      </header>

      <nav className="app-nav">
        <button
          className={`nav-btn ${activeTab === 'batch' ? 'active' : ''}`}
          onClick={() => setActiveTab('batch')}
        >
          📋 배치 설계
        </button>
        <button
          className={`nav-btn ${activeTab === 'mastering' ? 'active' : ''}`}
          onClick={() => setActiveTab('mastering')}
        >
          🎚️ 마스터링
        </button>
        <button
          className={`nav-btn ${activeTab === 'cover' ? 'active' : ''}`}
          onClick={() => setActiveTab('cover')}
        >
          🎨 커버 이미지
        </button>
        <button
          className={`nav-btn ${activeTab === 'metadata' ? 'active' : ''}`}
          onClick={() => setActiveTab('metadata')}
        >
          📝 메타데이터
        </button>
      </nav>

      <main className="app-content">
        {activeTab === 'batch' && <BatchGenerator onBatchGenerated={setBatchData} />}
        {activeTab === 'mastering' && <MasteringStudio />}
        {activeTab === 'cover' && <CoverImageCreator />}
        {activeTab === 'metadata' && <MetadataEditor />}
      </main>
    </div>
  );
}

export default App;
