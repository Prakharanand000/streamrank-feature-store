import { useState } from 'react'
import axios from 'axios'

const CARD  = { background: '#1a1f2e', borderRadius: 12, padding: 20, border: '1px solid #1e2533' }
const INPUT = {
  background: '#0f1117', border: '1px solid #334155', borderRadius: 8,
  color: '#e2e8f0', padding: '10px 14px', fontSize: 13, width: '100%'
}
const BTN = {
  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
  border: 'none', borderRadius: 8, color: 'white',
  padding: '10px 24px', cursor: 'pointer', fontWeight: 600, fontSize: 14
}

export default function RankPlayground() {
  const [userId,   setUserId]   = useState('U0001')
  const [videos,   setVideos]   = useState('V00001,V00002,V00003,V00004,V00005')
  const [shadow,   setShadow]   = useState(false)
  const [result,   setResult]   = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState(null)

  const submit = async () => {
    setLoading(true); setError(null)
    try {
      const r = await axios.post('/api/rank', {
        user_id: userId.trim(),
        candidate_video_ids: videos.split(',').map(v => v.trim()).filter(Boolean),
        return_shadow: shadow,
      })
      setResult(r.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Request failed. Is the API running?')
    } finally { setLoading(false) }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={CARD}>
        <h3 style={{ color: '#f1f5f9', marginBottom: 16, fontSize: 15 }}>
          Real-Time Ranking  ·  POST /rank
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12, marginBottom: 16 }}>
          <div>
            <label style={{ fontSize: 12, color: '#64748b', display: 'block', marginBottom: 6 }}>
              User ID
            </label>
            <input style={INPUT} value={userId} onChange={e => setUserId(e.target.value)} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#64748b', display: 'block', marginBottom: 6 }}>
              Candidate Video IDs (comma-separated)
            </label>
            <input style={INPUT} value={videos} onChange={e => setVideos(e.target.value)} />
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <label style={{ fontSize: 13, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={shadow} onChange={e => setShadow(e.target.checked)} />
            Include shadow model scores
          </label>
        </div>
        <button style={BTN} onClick={submit} disabled={loading}>
          {loading ? 'Ranking...' : 'Run Ranking'}
        </button>
        {error && <div style={{ marginTop: 12, color: '#ef4444', fontSize: 13 }}>⚠ {error}</div>}
      </div>

      {result && (
        <div style={CARD}>
          <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
            <Chip label="User" value={result.user_id} />
            <Chip label="Latency" value={`${result.latency_ms}ms`}
              color={result.latency_ms < 50 ? '#22c55e' : '#f59e0b'} />
            <Chip label="Feature Lookup" value={`${result.feature_latency_ms}ms`} />
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {['Rank', 'Video ID', 'Score', shadow && 'Shadow Score'].filter(Boolean).map(h => (
                  <th key={h} style={{
                    textAlign: 'left', padding: '8px 12px',
                    borderBottom: '1px solid #1e2533', color: '#64748b'
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.ranked_videos.map((v, i) => (
                <tr key={v.video_id} style={{ borderBottom: '1px solid #1e2533' }}>
                  <td style={{ padding: '10px 12px', color: i === 0 ? '#6366f1' : '#64748b',
                    fontWeight: i === 0 ? 700 : 400 }}>#{i + 1}</td>
                  <td style={{ padding: '10px 12px', color: '#e2e8f0', fontFamily: 'monospace' }}>
                    {v.video_id}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <ScoreBar score={v.score} />
                  </td>
                  {shadow && (
                    <td style={{ padding: '10px 12px', color: '#8b5cf6' }}>
                      {v.shadow_score ?? '—'}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Chip({ label, value, color = '#6366f1' }) {
  return (
    <span style={{
      background: color + '20', color, borderRadius: 6,
      padding: '4px 10px', fontSize: 12, fontWeight: 600
    }}>
      {label}: {value}
    </span>
  )
}

function ScoreBar({ score }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 80, height: 6, background: '#1e2533', borderRadius: 3, overflow: 'hidden'
      }}>
        <div style={{
          width: `${score * 100}%`, height: '100%', borderRadius: 3,
          background: score > 0.7 ? '#22c55e' : score > 0.4 ? '#6366f1' : '#64748b'
        }} />
      </div>
      <span style={{ color: '#94a3b8', fontSize: 12 }}>{score.toFixed(3)}</span>
    </div>
  )
}
