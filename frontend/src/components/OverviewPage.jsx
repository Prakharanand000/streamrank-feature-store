const CARD = {
  background: '#1a1f2e', borderRadius: 12, padding: 24,
  border: '1px solid #1e2533'
}

const TABS_INFO = [
  {
    name: 'Skew Monitor',
    icon: '⚠',
    color: '#ef4444',
    summary: 'The showcase tab. Detects when features served live drift away from features used in training.',
    detail: 'Every metric you see compares offline training features against online (Redis) serving features. Skew % is the mean absolute deviation. PSI (Population Stability Index) is the industry standard drift score — anything above 0.2 signals a problem. When training and serving features diverge, the model silently degrades in production. This dashboard catches that before users notice.',
    metrics: [
      ['Overall Health',       'Aggregate status. HEALTHY if no features cross thresholds, DEGRADED otherwise.'],
      ['Flagged Features',     'Count of features over the 20% skew or 0.2 PSI threshold.'],
      ['Missing Feature Rate', '% of feature lookups returning no data — indicates pipeline gaps.'],
      ['Stale Feature Rate',   '% of features older than 30 minutes — indicates pipeline lag.'],
      ['Skew %',               'How far each feature drifted between offline and online stores.'],
      ['PSI',                  'Distribution drift score. >0.2 = significant drift.'],
    ]
  },
  {
    name: 'Latency',
    icon: '⚡',
    color: '#22c55e',
    summary: 'Real-time inference latency tracking. Production ranking systems target sub-50ms.',
    detail: 'P50/P95/P99 are the percentiles SRE teams actually use because mean latency hides outliers. The line chart shows your most recent 20 requests so you can spot regressions immediately. The 50ms reference line is the standard latency target for consumer recommendation APIs.',
    metrics: [
      ['Mean Latency', 'Average request time. Useful but hides tail latency.'],
      ['P50',          'Median — half of all requests finish faster than this.'],
      ['P95',          '95% of requests finish below this. Production SLO usually targets P95.'],
      ['P99',          '99% of requests finish below this. The "worst case for normal users" number.'],
    ]
  },
  {
    name: 'Rank Playground',
    icon: '🎯',
    color: '#6366f1',
    summary: 'Live demo of the ranking API. Type a user ID + candidate videos, see them ranked.',
    detail: 'This is what an actual YouTube/Meta backend request looks like — given a user and a pool of candidate videos, the API returns them ranked by predicted click probability. Optionally include the "shadow model" score to see what an alternative model would have predicted. Shadow deployment is how Google/Meta validate new models before swapping the production one.',
    metrics: [
      ['Score',        'Predicted click probability from the production model (0-1).'],
      ['Shadow Score', 'What an alternative challenger model predicted. Used for A/B comparison.'],
      ['Latency',      'End-to-end request time including feature lookup + model inference.'],
      ['Feature Lookup', 'Time spent fetching features from Redis. Should be <10ms.'],
    ]
  },
  {
    name: 'Model Metrics',
    icon: '📊',
    color: '#8b5cf6',
    summary: 'Evaluation metrics for the trained XGBoost ranking model.',
    detail: 'Shows how well the model actually learned to predict clicks. AUC measures discrimination — how well the model separates clicks from non-clicks. NDCG@10 measures ranking quality at the top of the list. Feature importance shows which signals the model relies on most, which is critical for explaining predictions to stakeholders.',
    metrics: [
      ['AUC',           'Area Under ROC Curve. 0.5 = random, 1.0 = perfect. Production targets >0.70.'],
      ['NDCG@10',       'Normalized Discounted Cumulative Gain. Measures ranking quality.'],
      ['Train N',       'Number of rows used for training.'],
      ['Test N',        'Number of rows held out for evaluation.'],
      ['Feature Importance', 'Which features the XGBoost model relies on most.'],
    ]
  },
]

export default function OverviewPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 1100 }}>

      {/* Hero */}
      <div style={{
        background: 'linear-gradient(135deg, #1a1f2e 0%, #2a1f3e 100%)',
        borderRadius: 16, padding: '32px 36px',
        border: '1px solid #2d3748'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
          <span style={{
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            padding: '4px 12px', borderRadius: 20,
            fontSize: 11, fontWeight: 700, color: 'white', letterSpacing: 0.5,
          }}>
            REAL-TIME ML INFRASTRUCTURE
          </span>
        </div>
        <h1 style={{ fontSize: 28, color: '#f1f5f9', marginBottom: 12, lineHeight: 1.2 }}>
          A miniature version of the recommendation infrastructure powering<br />
          <span style={{
            background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
          }}>
            YouTube, Meta Feed, and Google Ads
          </span>
        </h1>
        <p style={{ color: '#94a3b8', fontSize: 14, lineHeight: 1.6, marginBottom: 8 }}>
          StreamRank simulates the end-to-end ranking pipeline used by consumer-scale platforms.
          User events flow through Kafka, get processed into features in both an offline store (Parquet)
          and an online store (Redis), train an XGBoost ranking model, and serve real-time predictions
          via FastAPI - all monitored for the #1 silent killer of production ML: training-serving skew.
        </p>
      </div>

      {/* The problem this solves */}
      <div style={CARD}>
        <h2 style={{ color: '#f1f5f9', fontSize: 17, marginBottom: 10 }}>
          The problem this solves
        </h2>
        <p style={{ color: '#94a3b8', fontSize: 13.5, lineHeight: 1.7 }}>
          At YouTube and Meta scale, ML teams don't just train models. They run two parallel
          feature pipelines: one for training (offline, batch) and one for live serving (online,
          real-time). When these two pipelines drift apart, the model starts making bad predictions
          in production even though it tested well offline. This is called <strong style={{ color: '#e2e8f0' }}>
          training-serving skew</strong>, and it's the leading cause of silent ML failures.
          StreamRank demonstrates the full loop and surfaces drift the moment it happens.
        </p>
      </div>

      {/* Architecture */}
      <div style={CARD}>
        <h2 style={{ color: '#f1f5f9', fontSize: 17, marginBottom: 16 }}>
          Architecture
        </h2>
        <pre style={{
          background: '#0f1117', padding: 20, borderRadius: 8, overflow: 'auto',
          color: '#94a3b8', fontSize: 12, lineHeight: 1.6,
          fontFamily: 'Menlo, Monaco, Consolas, monospace',
          border: '1px solid #1e2533'
        }}>
{`Synthetic Event Generator (Kafka Producer)
        │  delayed / duplicate / out-of-order events
        ▼
  Kafka Topic: user-events
        │
        ▼
 Kafka Consumer ──► Redis Online Store
 (rolling features)   user:U001:features
                      video:V001:features
        │
        ▼
 Offline Feature Store (Parquet)
 Point-in-time correct joins
        │
        ▼
 XGBoost Ranking Model (Production + Shadow)
        │
        ▼
 FastAPI /rank endpoint  (<50ms target)
        │
        ▼
 React Dashboard
 ├── Skew Monitor   (PSI drift detection)
 ├── Latency        (P50 / P95 / P99)
 ├── Rank Playground (live API demo)
 └── Model Metrics   (AUC, NDCG, importance)`}
        </pre>
      </div>

      {/* Tab guide */}
      <div style={CARD}>
        <h2 style={{ color: '#f1f5f9', fontSize: 17, marginBottom: 16 }}>
          Dashboard guide
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {TABS_INFO.map(tab => (
            <div key={tab.name} style={{
              background: '#0f1117', borderRadius: 10, padding: 18,
              borderLeft: `3px solid ${tab.color}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <span style={{ fontSize: 18 }}>{tab.icon}</span>
                <h3 style={{ color: tab.color, fontSize: 15, fontWeight: 700 }}>
                  {tab.name}
                </h3>
              </div>
              <p style={{ color: '#cbd5e1', fontSize: 13, lineHeight: 1.6, marginBottom: 10 }}>
                <strong>{tab.summary}</strong>
              </p>
              <p style={{ color: '#94a3b8', fontSize: 12.5, lineHeight: 1.7, marginBottom: 12 }}>
                {tab.detail}
              </p>
              <div style={{
                background: '#1a1f2e', borderRadius: 6, padding: '10px 14px',
                fontSize: 11.5
              }}>
                <div style={{ color: '#64748b', marginBottom: 6, fontSize: 11,
                  textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Metrics on this tab
                </div>
                {tab.metrics.map(([k, v]) => (
                  <div key={k} style={{ marginBottom: 4, display: 'flex', gap: 8 }}>
                    <strong style={{ color: '#e2e8f0', minWidth: 140 }}>{k}:</strong>
                    <span style={{ color: '#94a3b8' }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* How to use */}
      <div style={CARD}>
        <h2 style={{ color: '#f1f5f9', fontSize: 17, marginBottom: 16 }}>
          How to use it
        </h2>
        <ol style={{ color: '#94a3b8', fontSize: 13.5, lineHeight: 1.9,
          paddingLeft: 20, marginBottom: 0 }}>
          <li>
            <strong style={{ color: '#e2e8f0' }}>Skew Monitor:</strong> Open it
            first to see drift detection across 6 features. Red bars are flagged.
          </li>
          <li>
            <strong style={{ color: '#e2e8f0' }}>Rank Playground:</strong> Enter
            a user ID like <code style={codeStyle}>U0001</code> and candidate videos
            like <code style={codeStyle}>V00001,V00002,V00003</code>. Click Run Ranking.
            Toggle "Include shadow model" to see A/B comparison.
          </li>
          <li>
            <strong style={{ color: '#e2e8f0' }}>Latency:</strong> After running
            several rankings, see P50/P95/P99 percentiles populate.
          </li>
          <li>
            <strong style={{ color: '#e2e8f0' }}>Model Metrics:</strong> Inspect
            AUC, NDCG@10, and feature importance from XGBoost training.
          </li>
        </ol>
      </div>

      {/* Tech stack */}
      <div style={CARD}>
        <h2 style={{ color: '#f1f5f9', fontSize: 17, marginBottom: 16 }}>
          Tech stack
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
          {[
            ['Event streaming',      'Kafka (Confluent) + Docker'],
            ['Online feature store', 'Redis 7'],
            ['Offline feature store', 'Parquet via PyArrow'],
            ['Ranking model',        'XGBoost binary classifier'],
            ['Inference API',        'FastAPI + Uvicorn'],
            ['Frontend',             'React + Recharts + Vite'],
            ['Skew metric',          'PSI + mean abs deviation'],
            ['Anomaly simulation',   'Delays, duplicates, missing fields'],
          ].map(([k, v]) => (
            <div key={k} style={{
              background: '#0f1117', padding: '10px 14px', borderRadius: 8,
              border: '1px solid #1e2533', fontSize: 12.5
            }}>
              <div style={{ color: '#64748b', fontSize: 11,
                textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
                {k}
              </div>
              <div style={{ color: '#e2e8f0', fontWeight: 600 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

const codeStyle = {
  background: '#0f1117', padding: '2px 6px', borderRadius: 4,
  fontFamily: 'Menlo, Monaco, Consolas, monospace',
  color: '#a78bfa', fontSize: 12
}
