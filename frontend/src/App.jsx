import { useState } from 'react'
import Header from './components/Header.jsx'
import OverviewPage from './components/OverviewPage.jsx'
import SkewDashboard from './components/SkewDashboard.jsx'
import LatencyDashboard from './components/LatencyDashboard.jsx'
import RankPlayground from './components/RankPlayground.jsx'
import ModelMetrics from './components/ModelMetrics.jsx'

const TABS = ['Overview', 'Skew Monitor', 'Latency', 'Rank Playground', 'Model Metrics']

export default function App() {
  const [tab, setTab] = useState('Overview')

  return (
    <div style={{ minHeight: '100vh', background: '#0f1117' }}>
      <Header />
      <div style={{
        display: 'flex', gap: '4px', padding: '0 24px',
        borderBottom: '1px solid #1e2533', background: '#0f1117'
      }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '12px 20px', background: 'none', border: 'none',
            color: tab === t ? '#6366f1' : '#64748b',
            borderBottom: tab === t ? '2px solid #6366f1' : '2px solid transparent',
            cursor: 'pointer', fontSize: '14px', fontWeight: tab === t ? 600 : 400,
            transition: 'all 0.15s'
          }}>
            {t}
          </button>
        ))}
      </div>

      <div style={{ padding: '24px' }}>
        {tab === 'Overview'        && <OverviewPage />}
        {tab === 'Skew Monitor'    && <SkewDashboard />}
        {tab === 'Latency'         && <LatencyDashboard />}
        {tab === 'Rank Playground' && <RankPlayground />}
        {tab === 'Model Metrics'   && <ModelMetrics />}
      </div>
    </div>
  )
}
