import { useEffect, useState } from 'react'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'
import axios from 'axios'

const CARD = { background: '#1a1f2e', borderRadius: 12, padding: 20, border: '1px solid #1e2533' }

export default function ModelMetrics() {
  const [data, setData]   = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    axios.get('/api/metrics/model')
      .then(r => setData(r.data))
      .catch(() => setError('API not reachable or model not trained yet.'))
  }, [])

  if (error) return <div style={{ color: '#ef4444', padding: 20 }}>⚠ {error}</div>
  if (!data || data.message) return (
    <div style={{ ...CARD, color: '#64748b' }}>
      Run the pipeline first: <code>python run_pipeline.py</code>
    </div>
  )

  const importanceData = Object.entries(data.importance || {}).map(([k, v]) => ({
    feature: k.replace(/_/g, ' ').replace('user ', '').replace('video ', ''),
    value: +(v * 100).toFixed(1)
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        <MetricCard label="AUC"     value={data.auc}         good={data.auc > 0.7} />
        <MetricCard label="NDCG@10" value={data.ndcg_at_10}  good={data.ndcg_at_10 > 0.5} />
        <MetricCard label="Train N" value={data.n_train?.toLocaleString()} good />
        <MetricCard label="Test N"  value={data.n_test?.toLocaleString()}  good />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <div style={CARD}>
          <h3 style={{ color: '#f1f5f9', fontSize: 15, marginBottom: 16 }}>
            Feature Importance (XGBoost)
          </h3>
          {importanceData.map(({ feature, value }) => (
            <div key={feature} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between',
                marginBottom: 4, fontSize: 12 }}>
                <span style={{ color: '#94a3b8' }}>{feature}</span>
                <span style={{ color: '#6366f1', fontWeight: 600 }}>{value}%</span>
              </div>
              <div style={{ height: 6, background: '#1e2533', borderRadius: 3 }}>
                <div style={{
                  width: `${value}%`, height: '100%', borderRadius: 3,
                  background: 'linear-gradient(90deg, #6366f1, #8b5cf6)'
                }} />
              </div>
            </div>
          ))}
        </div>

        <div style={CARD}>
          <h3 style={{ color: '#f1f5f9', fontSize: 15, marginBottom: 8 }}>
            Feature Radar
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={importanceData}>
              <PolarGrid stroke="#1e2533" />
              <PolarAngleAxis dataKey="feature" tick={{ fill: '#94a3b8', fontSize: 10 }} />
              <Radar dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.3} />
              <Tooltip
                contentStyle={{ background: '#1e2533', border: '1px solid #334155', borderRadius: 8 }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ ...CARD, fontSize: 13, color: '#64748b' }}>
        Model: <strong style={{ color: '#e2e8f0' }}>XGBoost Binary Classifier</strong>
        &nbsp;·&nbsp; Task: Click probability prediction
        &nbsp;·&nbsp; Features: {data.features?.length}
        &nbsp;·&nbsp; Shadow model: trained separately with reduced capacity for A/B comparison
      </div>
    </div>
  )
}

function MetricCard({ label, value, good }) {
  const color = good ? '#22c55e' : '#f59e0b'
  return (
    <div style={{ ...CARD, borderLeft: `3px solid ${color}` }}>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
    </div>
  )
}
