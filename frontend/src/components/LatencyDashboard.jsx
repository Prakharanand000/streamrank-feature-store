import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import axios from 'axios'

const CARD = { background: '#1a1f2e', borderRadius: 12, padding: 20, border: '1px solid #1e2533' }

export default function LatencyDashboard() {
  const [data, setData]   = useState(null)
  const [error, setError] = useState(null)

  const fetch = async () => {
    try {
      const r = await axios.get('/api/metrics/latency')
      setData(r.data)
    } catch { setError('API not reachable.') }
  }

  useEffect(() => { fetch(); const id = setInterval(fetch, 3000); return () => clearInterval(id) }, [])

  if (error) return <div style={{ color: '#ef4444', padding: 20 }}>⚠ {error}</div>
  if (!data || data.message) return (
    <div style={{ ...CARD, color: '#64748b' }}>
      No latency data yet. Send requests via Rank Playground.
    </div>
  )

  const recent = (data.recent || []).map((r, i) => ({
    i, latency: r.latency_ms, user: r.user_id, candidates: r.n_candidates
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        {[
          { label: 'Mean Latency', value: `${data.mean_ms}ms`, ok: data.mean_ms < 50 },
          { label: 'P50', value: `${data.p50_ms}ms`, ok: data.p50_ms < 50 },
          { label: 'P95', value: `${data.p95_ms}ms`, ok: data.p95_ms < 100 },
          { label: 'P99', value: `${data.p99_ms}ms`, ok: data.p99_ms < 200 },
        ].map(({ label, value, ok }) => (
          <div key={label} style={{ ...CARD, borderLeft: `3px solid ${ok ? '#22c55e' : '#ef4444'}` }}>
            <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>{label}</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: ok ? '#22c55e' : '#ef4444' }}>{value}</div>
          </div>
        ))}
      </div>

      <div style={CARD}>
        <h3 style={{ marginBottom: 16, color: '#f1f5f9', fontSize: 15 }}>
          Inference Latency — Last 20 Requests
        </h3>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={recent}>
            <XAxis dataKey="i" tick={{ fill: '#94a3b8', fontSize: 11 }} />
            <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `${v}ms`} />
            <Tooltip
              contentStyle={{ background: '#1e2533', border: '1px solid #334155', borderRadius: 8 }}
              formatter={(v) => [`${v}ms`, 'Latency']}
            />
            <ReferenceLine y={50} stroke="#f59e0b" strokeDasharray="4 4"
              label={{ value: '50ms target', fill: '#f59e0b', fontSize: 11 }} />
            <Line type="monotone" dataKey="latency" stroke="#6366f1"
              strokeWidth={2} dot={{ fill: '#6366f1', r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div style={{ ...CARD, color: '#64748b', fontSize: 13 }}>
        Total requests tracked: <strong style={{ color: '#e2e8f0' }}>{data.n_requests}</strong>
        &nbsp;·&nbsp; Target: &lt;50ms inference latency
        &nbsp;·&nbsp; Refreshes every 3s
      </div>
    </div>
  )
}
