export default function Header() {
  return (
    <div style={{
      padding: '20px 24px', borderBottom: '1px solid #1e2533',
      display: 'flex', alignItems: 'center', gap: '12px',
      background: 'linear-gradient(135deg, #0f1117 0%, #1a1f2e 100%)'
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: 8,
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 18, fontWeight: 700, color: 'white'
      }}>S</div>
      <div>
        <h1 style={{ fontSize: '18px', fontWeight: 700, color: '#f1f5f9' }}>
          StreamRank
        </h1>
        <p style={{ fontSize: '12px', color: '#64748b' }}>
          Real-Time Feature Store · Training-Serving Skew Detection
        </p>
      </div>
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
        <StatusBadge label="Kafka" color="#22c55e" />
        <StatusBadge label="Redis" color="#22c55e" />
        <StatusBadge label="API"   color="#22c55e" />
      </div>
    </div>
  )
}

function StatusBadge({ label, color }) {
  return (
    <span style={{
      padding: '4px 10px', borderRadius: 20,
      background: color + '20', color, fontSize: 11,
      fontWeight: 600, display: 'flex', alignItems: 'center', gap: 5
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%', background: color,
        boxShadow: `0 0 6px ${color}`
      }} />
      {label}
    </span>
  )
}
