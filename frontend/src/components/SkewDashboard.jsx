import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts'
import axios from 'axios'

const CARD = {
  background: '#1a1f2e', borderRadius: 12, padding: '20px',
  border: '1px solid #1e2533'
}

export default function SkewDashboard() {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  const fetchSkew = async () => {
    try {
      const r = await axios.get('/api/metrics/skew')
      setData(r.data)
      setError(null)
    } catch (e) {
      setError('API not reachable. Start the FastAPI server first.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchSkew(); const id = setInterval(fetchSkew, 10000); return () => clearInterval(id) }, [])

  if (loading) return <LoadingState />
  if (error)   return <ErrorState msg={error} />
  if (!data?.features) return <ErrorState msg="No skew data available. Run the pipeline first." />

  const features = Object.entries(data.features).map(([name, vals]) => ({
    name: name.replace(/_/g, ' ').replace('user ', 'usr_').replace('video ', 'vid_'),
    skew_pct: +(vals.skew_pct * 100).toFixed(1),
    psi: +vals.psi.toFixed(3),
    flagged: vals.flagged,
    offline_mean: vals.offline_mean,
    online_mean: vals.online_mean,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        <MetricCard label="Overall Health"
          value={data.overall_health}
          color={data.overall_health === 'HEALTHY' ? '#22c55e' : '#f59e0b'} />
        <MetricCard label="Flagged Features"
          value={`${data.n_flagged_features} / ${Object.keys(data.features).length}`}
          color={data.n_flagged_features > 0 ? '#f59e0b' : '#22c55e'} />
        <MetricCard label="Missing Feature Rate"
          value={`${(data.missing_rate * 100).toFixed(1)}%`}
          color={data.missing_rate > 0.05 ? '#ef4444' : '#22c55e'} />
        <MetricCard label="Stale Feature Rate"
          value={`${(data.stale_rate * 100).toFixed(1)}%`}
          color={data.stale_rate > 0.1 ? '#f59e0b' : '#22c55e'} />
      </div>

      {/* Skew bar chart */}
      <div style={CARD}>
        <h3 style={{ marginBottom: 16, color: '#f1f5f9', fontSize: 15 }}>
          Training-Serving Skew % per Feature
          <span style={{ marginLeft: 8, fontSize: 11, color: '#64748b' }}>
            (threshold: 20% · refreshes every 10s)
          </span>
        </h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={features} margin={{ top: 5, right: 20, bottom: 40, left: 0 }}>
            <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }}
              angle={-20} textAnchor="end" />
            <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }}
              tickFormatter={v => `${v}%`} />
            <Tooltip
              contentStyle={{ background: '#1e2533', border: '1px solid #334155', borderRadius: 8 }}
              formatter={(v) => [`${v}%`, 'Skew']}
            />
            <ReferenceLine y={20} stroke="#f59e0b" strokeDasharray="4 4"
              label={{ value: '20% threshold', fill: '#f59e0b', fontSize: 11 }} />
            <Bar dataKey="skew_pct" radius={[4, 4, 0, 0]}>
              {features.map((f, i) => (
                <Cell key={i} fill={f.flagged ? '#ef4444' : '#6366f1'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* PSI table */}
      <div style={CARD}>
        <h3 style={{ marginBottom: 16, color: '#f1f5f9', fontSize: 15 }}>
          PSI Drift Detection
          <span style={{ marginLeft: 8, fontSize: 11, color: '#64748b' }}>
            PSI &gt; 0.2 = significant drift
          </span>
        </h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr>
              {['Feature', 'Offline Mean', 'Online Mean', 'Skew %', 'PSI', 'Status'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '8px 12px',
                  borderBottom: '1px solid #1e2533', color: '#64748b', fontWeight: 500 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {features.map((f, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #1e2533' }}>
                <td style={{ padding: '10px 12px', color: '#e2e8f0' }}>{f.name}</td>
                <td style={{ padding: '10px 12px', color: '#94a3b8' }}>{f.offline_mean}</td>
                <td style={{ padding: '10px 12px', color: '#94a3b8' }}>{f.online_mean}</td>
                <td style={{ padding: '10px 12px', color: f.skew_pct > 20 ? '#ef4444' : '#22c55e',
                  fontWeight: 600 }}>{f.skew_pct}%</td>
                <td style={{ padding: '10px 12px', color: f.psi > 0.2 ? '#f59e0b' : '#94a3b8' }}>
                  {f.psi}
                </td>
                <td style={{ padding: '10px 12px' }}>
                  <span style={{
                    padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                    background: f.flagged ? '#ef444420' : '#22c55e20',
                    color: f.flagged ? '#ef4444' : '#22c55e'
                  }}>
                    {f.flagged ? '⚠ FLAGGED' : '✓ OK'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function MetricCard({ label, value, color }) {
  return (
    <div style={{ ...CARD, borderLeft: `3px solid ${color}` }}>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
    </div>
  )
}

function LoadingState() {
  return <div style={{ textAlign: 'center', padding: 60, color: '#64748b' }}>Loading skew metrics...</div>
}

function ErrorState({ msg }) {
  return (
    <div style={{ background: '#1a1f2e', borderRadius: 12, padding: 24,
      border: '1px solid #ef444440', color: '#ef4444' }}>
      ⚠ {msg}
    </div>
  )
}
